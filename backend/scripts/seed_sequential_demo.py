"""演示：一批 12 对试件按登记次序入账，一直看到达线冻结。"""
import json
from sqlalchemy import select
from src.config.database import Base,engine,Session
from src.config.domain import DOMAIN
from src.models.user import User
from src.models.study import Study
from src.models.observation import Observation
from src.services import sequential
from src.schemas.sequential import SequentialSessionInput,PairInput,MeasurementInput

def main():
    Base.metadata.create_all(engine)
    with Session() as db:
        user=db.scalar(select(User).where(User.role=='analyst'))
        study=db.scalar(select(Study).order_by(Study.id))
        if not user or not study: raise SystemExit('先运行 scripts.seed_demo')
        base=study.id
        keys=[f'SEQ-{i:03}' for i in range(1,25)]
        for i,k in enumerate(keys):
            if not db.scalar(select(Observation.id).where(Observation.study_id==base,Observation.source_key==k)):
                db.add(Observation(study_id=base,source_key=k,values={'porosity':float(10+i),'absorption':float(11+i)}))
        db.commit()
        pairs=[(keys[i],keys[i+1]) for i in range(0,24,2)]
        obj=sequential.create(db,SequentialSessionInput(study_id=base,name=DOMAIN['study_label']+' · 序贯演示',alpha=0.05,
            pairs=[PairInput(label=f'批次{i//2+1}',specimen_a=a,specimen_b=b) for i,(a,b) in enumerate(pairs)]),user)
        sid=obj['session']['id']
        for seq,(a,b) in enumerate(pairs,1):
            va={'porosity':float(2*seq+5),'absorption':float(2*seq+6)}
            vb={'porosity':float(2*seq+2),'absorption':float(2*seq+3)}
            out=sequential.measure(db,sid,MeasurementInput(seq=seq,values_a=va,values_b=vb),user)
            if out['session']['status']!='running': break
        s=sequential.detail(db,sid)['session']
        print(json.dumps({'session':sid,'status':s['status'],'decision':s['decision'],'e_value':s['e_value'],
            'frozen_seq':s['evidence']['frozen_seq'] if s['evidence'] else None},ensure_ascii=False))

if __name__=='__main__': main()
