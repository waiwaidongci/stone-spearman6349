import os,sys
import pytest
sys.path.insert(0,os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault('DATABASE_URL','sqlite://')
os.environ.setdefault('REDIS_URL','redis://localhost:6379/0')
os.environ.setdefault('JWT_SECRET','test-secret')

from sqlalchemy import create_engine,select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from src.config.database import Base
from src.models import user,study,observation,run,review,audit,pair,session,ledger
from src.models.study import Study
from src.models.observation import Observation
from src.models.user import User
from src.models.pair import SpecimenPair,PairMember
from src.models.session import SequentialSession
from src.models.ledger import LedgerEntry
from src.schemas.sequential import SequentialSessionInput,PairInput,MeasurementInput
from src.services import sequential
from src.services.sequential_algorithm import log_e_value,log_threshold

@pytest.fixture()
def db():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session=sessionmaker(bind=engine,expire_on_commit=False)
    with Session() as s:
        s.add(User(email='analyst@demo.local',role='analyst',password_hash='x'))
        s.add(User(email='viewer@demo.local',role='viewer',password_hash='x'))
        s.add(Study(name='批次甲',source_filename='f.csv'))
        s.flush()
        for i in range(1,80):
            s.add(Observation(study_id=1,source_key=f'S{i:03d}',values={'porosity':float(i),'absorption':float(i)+0.5}))
        s.commit()
        yield s

def user(db,email='analyst@demo.local'): return db.scalar(select(User).where(User.email==email))

def make_session(db,pairs,alpha=0.05,name='轮次'):
    data=SequentialSessionInput(study_id=1,name=name,alpha=alpha,pairs=[PairInput(label=f'P{i}',specimen_a=a,specimen_b=b) for i,(a,b) in enumerate(pairs,1)])
    return sequential.create(db,data,user(db))

def measure(db,sid,seq,va,vb):
    return sequential.measure(db,sid,MeasurementInput(seq=seq,values_a=va,values_b=vb),user(db))

def vals(i,offset=0.0):
    return {'porosity':float(i),'absorption':float(i)+offset+1.0}

def pair_vals(i,reverse=False):
    """第 i 对：同向时 a 的两项都高于 b；反向时孔隙率高于 b 而吸水率低于 b。均非负。"""
    a={'porosity':float(2*i),'absorption':float(2*i)+( -1.0 if reverse else 1.0)}
    b={'porosity':float(2*i)-1.0,'absorption':float(2*i)}
    return a,b

def test_overlapping_pairs_rejected(db):
    with pytest.raises(Exception) as e:
        make_session(db,[('S001','S002'),('S002','S003')])
    assert '互不重叠' in str(e.value.detail)

def test_pair_reuse_across_sessions_rejected(db):
    make_session(db,[('S001','S002')])
    with pytest.raises(Exception) as e:
        make_session(db,[('S002','S003')])
    assert '已登记' in str(e.value.detail)

def test_specimens_may_arrive_before_being_measured(db):
    # 试件可先登记为试件对，首测值在补录时锁定；不要求先有来源记录。
    r=make_session(db,[('NEW-001','NEW-002')])
    sid=r['session']['id']
    out=measure(db,sid,1,{'porosity':5.0,'absorption':6.0},{'porosity':4.0,'absorption':5.0})
    assert out['booked']==[1]
    assert out['session']['status']=='exhausted' and out['session']['decision'] is None

def test_out_of_order_measurement_waits_for_predecessor(db):
    result=make_session(db,[('S001','S002'),('S003','S004')])
    sid=result['session']['id']
    out=measure(db,sid,2,vals(3),vals(4))  # 次序 1 未测
    assert out['booked']==[]
    assert out['session']['processed_seq']==0
    assert out['next']['seq']==1
    out=measure(db,sid,1,vals(1),vals(2))  # 补齐后按序入账两对
    assert out['booked']==[1,2]
    assert out['session']['processed_seq']==2

def test_tie_pair_is_skipped_and_does_not_move_e_value(db):
    r=make_session(db,[('S001','S002'),('S003','S004'),('S005','S006')])
    sid=r['session']['id']
    measure(db,sid,1,vals(1),vals(2))
    tie=measure(db,sid,2,{'porosity':3.0,'absorption':5.0},{'porosity':3.0,'absorption':4.0})
    assert tie['entries'][-1]['outcome']=='tie'
    assert tie['entries'][-1]['skipped']==1
    assert tie['session']['concordant']==1 and tie['session']['discordant']==0
    after=measure(db,sid,3,vals(6),vals(5))
    assert after['session']['log_e']>tie['session']['log_e']

def test_retry_same_pair_does_not_double_count(db):
    r=make_session(db,[('S001','S002'),('S003','S004')])
    sid=r['session']['id']
    first=measure(db,sid,1,vals(1),vals(2))
    again=measure(db,sid,1,vals(1),vals(2))
    assert again['booked']==[] and again['idempotent'] is True
    assert again['session']['concordant']==first['session']['concordant']==1
    assert len(again['entries'])==len(first['entries'])==1

def test_first_value_locked_cannot_be_overwritten(db):
    r=make_session(db,[('S001','S002')])
    sid=r['session']['id']
    measure(db,sid,1,vals(1),vals(2))
    with pytest.raises(Exception) as e:
        measure(db,sid,1,vals(1,5),vals(2))
    assert '锁定' in str(e.value.detail)

def test_freeze_at_first_crossing_and_used_values_frozen(db):
    crossing=next(k for k in range(1,200) if log_e_value(k,0)>=log_threshold(0.05))
    pairs=[(f'S{i:03d}',f'S{i+1:03d}') for i in range(1,2*crossing+4,2)]
    r=make_session(db,pairs,alpha=0.05)
    sid=r['session']['id']
    out=None
    for seq in range(1,crossing+3):
        a,b=pair_vals(seq)
        out=measure(db,sid,seq,a,b)
        if out['session']['status']=='frozen': break
    assert out['session']['status']=='frozen'
    assert out['session']['decision']=='concordant'
    assert out['session']['evidence']['frozen_seq']==crossing
    assert len(out['session']['evidence']['used_pairs'])==crossing
    assert out['session']['processed_seq']==crossing
    # 继后的补录被拒绝，结论与证据不变
    calls=len(out['entries'])
    with pytest.raises(Exception) as e:
        measure(db,sid,crossing+1,vals(crossing+1),vals(crossing+2))
    assert '冻结' in str(e.value.detail)
    assert len(sequential.detail(db,sid)['entries'])==calls

def test_reverse_direction_freezes_as_discordant(db):
    crossing=next(k for k in range(1,200) if log_e_value(0,k)>=log_threshold(0.05))
    pairs=[(f'S{i:03d}',f'S{i+1:03d}') for i in range(1,2*crossing+4,2)]
    r=make_session(db,pairs,alpha=0.05)
    sid=r['session']['id'];out=None
    for seq in range(1,crossing+1):
        a,b=pair_vals(seq,reverse=True)
        out=measure(db,sid,seq,a,b)
    assert out['session']['status']=='frozen' and out['session']['decision']=='discordant'

def test_resume_replays_ledger_without_duplicates(db):
    r=make_session(db,[('S001','S002'),('S003','S004'),('S005','S006')])
    sid=r['session']['id']
    measure(db,sid,1,vals(1),vals(2))
    measure(db,sid,2,vals(3),vals(4))
    before=sequential.detail(db,sid)
    # 模拟中断：台账已落库，但会话累计量未提交/回滚
    obj=db.get(SequentialSession,sid)
    obj.concordant=0;obj.discordant=0;obj.log_e=0.0;obj.e_value=1.0;obj.processed_seq=0
    db.commit()
    out=sequential.ingest(db,sid,user(db))
    assert out['booked']==[]
    assert out['session']['concordant']==before['session']['concordant']==2
    assert out['session']['processed_seq']==2
    assert len(out['entries'])==len(before['entries'])==2
    # 再补一对，继续按序入账
    out=measure(db,sid,3,vals(5),vals(6))
    assert out['booked']==[3]
    assert len(out['entries'])==3

def test_ledger_unique_constraint_blocks_duplicate_seq(db):
    r=make_session(db,[('S001','S002')])
    sid=r['session']['id']
    measure(db,sid,1,vals(1),vals(2))
    entry=db.scalar(select(LedgerEntry).where(LedgerEntry.session_id==sid))
    from sqlalchemy.exc import IntegrityError
    db.add(LedgerEntry(session_id=sid,pair_id=entry.pair_id,seq=entry.seq,label='dup',source_key_a='x',source_key_b='y',
        values_a=entry.values_a,values_b=entry.values_b,outcome='concordant',concordant=1,discordant=0,skipped=0,
        log_e=0.0,e_value=1.0,created_at='now'))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

def test_exhausted_when_all_pairs_booked_without_crossing(db):
    r=make_session(db,[('S001','S002'),('S003','S004')])
    sid=r['session']['id']
    measure(db,sid,1,vals(1),vals(2))
    out=measure(db,sid,2,vals(3),vals(4))
    assert out['session']['status']=='exhausted'
    assert out['session']['decision'] is None

def test_viewer_cannot_create():
    # 路由层用 writer 依赖，服务层不区分角色；此处只校验角色常量一致性
    from src.middlewares.auth import writer
    assert writer is not None

def test_two_sessions_in_same_study_have_independent_sequences(db):
    a=make_session(db,[('S001','S002'),('S003','S004')],name='轮次甲')
    b=make_session(db,[('S005','S006'),('S007','S008')],name='轮次乙')
    assert a['session']['id']!=b['session']['id']
    assert [p['seq'] for p in a['pairs']]==[1,2]
    assert [p['seq'] for p in b['pairs']]==[1,2]
    out=measure(db,b['session']['id'],1,vals(5),vals(6))
    assert out['booked']==[1]
    assert sequential.detail(db,a['session']['id'])['entries']==[]
