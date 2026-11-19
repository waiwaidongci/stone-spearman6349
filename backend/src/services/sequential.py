from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from src.models.pair import SpecimenPair,PairMember
from src.models.session import SequentialSession
from src.models.ledger import LedgerEntry
from src.models.study import Study
from src.services import studies
from src.services.domain_validation import validate_values
from src.services.sequential_algorithm import (PRIOR_LABEL,direction_outcome,log_e_value,log_threshold,safe_exp,threshold)
from src.services.audits import log
from src.utils.serializers import record,now,checksum

RUNNING,FROZEN,EXHAUSTED='running','frozen','exhausted'
OUTCOME_LABELS={'concordant':'同向','discordant':'反向','tie':'并列跳过'}

def _session(db,id,lock=False):
    query=select(SequentialSession).where(SequentialSession.id==id)
    obj=db.scalar(query.with_for_update() if lock else query)
    if not obj: raise HTTPException(404,'序贯监测轮次不存在')
    return obj

def _pairs(db,id):
    return list(db.scalars(select(SpecimenPair).where(SpecimenPair.session_id==id).order_by(SpecimenPair.seq)))

def _members(db,pair_id):
    return {m.side:m for m in db.scalars(select(PairMember).where(PairMember.pair_id==pair_id))}

def _signature(pairs):
    """已持久化的试件对签名；任何改动都会让续跑拒绝入账，避免次序被悄悄篡改。"""
    return checksum([{'seq':p.seq,'label':p.label,'a':p.source_key_a,'b':p.source_key_b} for p in pairs])

def _input_signature(pairs):
    return checksum([{'seq':i,'label':p.label,'a':p.specimen_a,'b':p.specimen_b} for i,p in enumerate(pairs,1)])

def _measurement_values(supplied):
    try: return validate_values(supplied)
    except (ValueError,TypeError) as e: raise HTTPException(422,str(e))

def create(db,data,user):
    studies.require(db,data.study_id)
    pairs=data.pairs
    keys=[k for p in pairs for k in (p.specimen_a,p.specimen_b)]
    for p in pairs:
        if p.specimen_a==p.specimen_b: raise HTTPException(422,'一对试件不能是同一试件')
    if len(set(keys))!=len(keys): raise HTTPException(422,'试件在同一轮内重复登记，试件对必须互不重叠')
    owned=set(db.scalars(select(PairMember.source_key).where(PairMember.study_id==data.study_id,PairMember.source_key.in_(keys))))
    if owned: raise HTTPException(409,'试件已登记在其它试件对：'+'、'.join(sorted(owned)))
    signature=_input_signature(pairs)
    obj=SequentialSession(study_id=data.study_id,name=data.name,alpha=float(data.alpha),status=RUNNING,pair_count=len(pairs),
        pairs_checksum=signature,concordant=0,discordant=0,skipped=0,processed_seq=0,log_e=0.0,e_value=1.0,peak_log_e=0.0,
        created_at=now(),created_by=user.email)
    db.add(obj)
    try:
        db.flush()
        for i,p in enumerate(pairs,1):
            pair=SpecimenPair(study_id=data.study_id,session_id=obj.id,seq=i,label=p.label,source_key_a=p.specimen_a,
                source_key_b=p.specimen_b,created_at=now(),created_by=user.email)
            db.add(pair);db.flush()
            db.add(PairMember(study_id=data.study_id,pair_id=pair.id,source_key=p.specimen_a,side='A'))
            db.add(PairMember(study_id=data.study_id,pair_id=pair.id,source_key=p.specimen_b,side='B'))
        log(db,user,'sequential.create',f'{obj.id}: {len(pairs)}对 · α={data.alpha}')
        db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'试件对与该批次已有登记冲突，请刷新后重试')
    return detail(db,obj.id)

def _locked(db,obj,pair):
    members=_members(db,pair.id)
    a,b=members.get('A'),members.get('B')
    return a,b,(a is not None and b is not None and a.locked_at is not None and b.locked_at is not None)

def measure(db,id,data,user):
    obj=_session(db,id,lock=True)
    pair=db.scalar(select(SpecimenPair).where(SpecimenPair.session_id==id,SpecimenPair.seq==data.seq))
    if not pair: raise HTTPException(404,'该次序没有登记试件对')
    a,b,ready=_locked(db,obj,pair)
    if not a or not b: raise HTTPException(409,'试件对登记不完整')
    if data.values_a is None and data.values_b is None: raise HTTPException(422,'至少提交一侧首测值')
    values={'A':_measurement_values(data.values_a) if data.values_a is not None else None,
            'B':_measurement_values(data.values_b) if data.values_b is not None else None}
    booked_entry=db.scalar(select(LedgerEntry).where(LedgerEntry.session_id==id,LedgerEntry.pair_id==pair.id))
    if booked_entry:
        # 同一对重试：数值与已入账证据一致则不重复累计，不一致则拒绝覆盖首测值。
        same=all(values[s] is None or values[s]==getattr(booked_entry,'values_'+s.lower()) for s in ('A','B'))
        if same:
            result=detail(db,id);result['booked']=[];result['idempotent']=True;return result
        raise HTTPException(409,'该对首测值已锁定入账，不能覆盖')
    if obj.status!=RUNNING: raise HTTPException(409,'本轮已冻结或结束，不能再补录')
    for side,member in (('A',a),('B',b)):
        if values[side] is None: continue
        if member.locked_at:
            if member.values!=values[side]: raise HTTPException(409,f'试件 {member.source_key} 的首测值已锁定，不能覆盖')
        else: member.values=values[side];member.locked_at=now()
    log(db,user,'sequential.measure',f'{id}/序号{data.seq}')
    booked=advance(db,obj,user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback();booked=[]
    result=detail(db,id);result['booked']=booked
    if not booked:
        result['idempotent']=db.scalar(select(LedgerEntry.id).where(LedgerEntry.session_id==id,LedgerEntry.pair_id==pair.id)) is not None
    return result

def ingest(db,id,user):
    obj=_session(db,id,lock=True)
    if obj.status!=RUNNING:
        result=detail(db,id);result['booked']=[];result['idempotent']=True;return result
    booked=advance(db,obj,user)
    log(db,user,'sequential.ingest',f'{id}: {booked}')
    try:
        db.commit()
    except IntegrityError:
        db.rollback();booked=[]
    result=detail(db,id);result['booked']=booked;return result

def _entries(db,id):
    return list(db.scalars(select(LedgerEntry).where(LedgerEntry.session_id==id).order_by(LedgerEntry.seq)))

def _replay(obj,entries):
    """从数据库中的入账证据重建累计量；已冻结时以首个达线证据为冻结点，中断重跑不会重复累计。"""
    concordant=discordant=skipped=0;log_e=0.0;cross=None;used=[]
    for entry in entries:
        if not entry.skipped:
            concordant+=entry.concordant;discordant+=entry.discordant
        skipped+=entry.skipped;log_e=entry.log_e;used.append(entry)
        if cross is None and log_e>=log_threshold(obj.alpha): cross=entry
    if cross is not None: return concordant,discordant,skipped,log_e,cross,used
    return concordant,discordant,skipped,log_e,None,used

def _apply(obj,concordant,discordant,skipped,log_e):
    obj.concordant,obj.discordant,obj.skipped=concordant,discordant,skipped
    obj.log_e,obj.e_value=log_e,safe_exp(log_e)
    obj.peak_log_e=max(float(obj.peak_log_e or 0.0),log_e)

def advance(db,obj,user):
    """严格按登记次序入账；前一对首测值未齐就等待，后续并列对跳过。返回本次新增入账的次序号。"""
    pairs=_pairs(db,obj.id)
    if _signature(pairs)!=obj.pairs_checksum: raise HTTPException(409,'登记次序校验失败，拒绝继续入账')
    entries=_entries(db,obj.id)
    concordant,discordant,skipped,log_e,cross,used=_replay(obj,entries)
    if cross is not None:
        _freeze(obj,cross,concordant,discordant,skipped,log_e,used)
        return []
    _apply(obj,concordant,discordant,skipped,log_e)
    obj.processed_seq=entries[-1].seq if entries else 0
    booked=[];by_seq={p.seq:p for p in pairs}
    while obj.processed_seq<obj.pair_count:
        pair=by_seq.get(obj.processed_seq+1)
        if not pair: break
        a,b,ready=_locked(db,obj,pair)
        if not ready: break
        outcome=direction_outcome(a.values,b.values)
        dc=1 if outcome=='concordant' else 0
        dd=1 if outcome=='discordant' else 0
        ds=1 if outcome=='tie' else 0
        new_log_e=log_e if ds else log_e_value(concordant+dc,discordant+dd)
        entry=LedgerEntry(session_id=obj.id,pair_id=pair.id,seq=pair.seq,label=pair.label,source_key_a=pair.source_key_a,
            source_key_b=pair.source_key_b,values_a=a.values,values_b=b.values,outcome=outcome,concordant=dc,discordant=dd,
            skipped=ds,log_e=new_log_e,e_value=safe_exp(new_log_e),created_at=now())
        db.add(entry);db.flush()
        concordant+=dc;discordant+=dd;log_e=new_log_e;skipped+=ds;obj.processed_seq=pair.seq
        booked.append(pair.seq);used=used+[entry]
        if log_e>=log_threshold(obj.alpha):
            _freeze(obj,entry,concordant,discordant,skipped,log_e,used)
            return booked
    _apply(obj,concordant,discordant,skipped,log_e)
    if obj.status==RUNNING and obj.processed_seq>=obj.pair_count: obj.status=EXHAUSTED
    return booked

def _freeze(obj,entry,concordant,discordant,skipped,log_e,used):
    decision='concordant' if concordant>discordant else 'discordant'
    obj.status=FROZEN;obj.decision=decision;obj.frozen_at=obj.frozen_at or now();obj.processed_seq=entry.seq
    _apply(obj,concordant,discordant,skipped,log_e)
    obj.evidence={
        'alpha':obj.alpha,'threshold':threshold(obj.alpha),'prior':PRIOR_LABEL,
        'decision':decision,'decision_label':OUTCOME_LABELS[decision],
        'frozen_seq':entry.seq,'frozen_at':obj.frozen_at,
        'concordant':concordant,'discordant':discordant,'skipped':skipped,
        'log_e':log_e,'e_value':safe_exp(log_e),
        'method':'均匀先验混合似然比 e 值 + Ville 不等式：任意时点反复查看，整轮双侧误报率 ≤ α；首次达线即冻结结论与所用测值',
        'used_pairs':[{'seq':e.seq,'label':e.label,'specimen_a':e.source_key_a,'specimen_b':e.source_key_b,
            'values_a':e.values_a,'values_b':e.values_b,'outcome':e.outcome,'outcome_label':OUTCOME_LABELS[e.outcome],
            'log_e':e.log_e,'e_value':e.e_value} for e in used]}

def detail(db,id):
    obj=_session(db,id)
    entries=_entries(db,id);pairs=_pairs(db,id)
    members={}
    for m in db.scalars(select(PairMember).where(PairMember.pair_id.in_([p.id for p in pairs]))):
        members.setdefault(m.pair_id,{})[m.side]=m
    pending=None
    if obj.status==RUNNING and obj.processed_seq<obj.pair_count:
        pair=next((p for p in pairs if p.seq==obj.processed_seq+1),None)
        if pair:
            got=members.get(pair.id,{})
            a,b=got.get('A'),got.get('B')
            pending={'seq':pair.seq,'label':pair.label,'specimens':[pair.source_key_a,pair.source_key_b],
                'missing':[m.source_key for m in (a,b) if m and not m.locked_at],
                'ready':bool(a and b and a.locked_at and b.locked_at)}
    study=db.get(Study,obj.study_id)
    return {'session':record(obj),'entries':[record(e) for e in entries],
        'pairs':[{'seq':p.seq,'label':p.label,'specimen_a':p.source_key_a,'specimen_b':p.source_key_b,
            'locked_a':bool(members.get(p.id,{}).get('A') and members[p.id]['A'].locked_at),
            'locked_b':bool(members.get(p.id,{}).get('B') and members[p.id]['B'].locked_at)} for p in pairs],
        'next':pending,'study_name':getattr(study,'name',None),
        'threshold':threshold(obj.alpha),'alpha':obj.alpha}

def list_sessions(db):
    rows=list(db.scalars(select(SequentialSession).order_by(SequentialSession.id.desc())))
    names={s.id:s.name for s in db.scalars(select(Study))}
    return [{**record(r),'study_name':names.get(r.study_id)} for r in rows]
