import os,sys
import pytest
sys.path.insert(0,os.path.dirname(os.path.dirname(__file__)))
os.environ['DATABASE_URL']='sqlite://'
os.environ['REDIS_URL']='redis://localhost:6379/0'
os.environ['JWT_SECRET']='test-secret'

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from src.config.database import Base,get_db
from src.models import user,study,observation,run,review,audit,pair,session,ledger
from src.models.user import User
from src.models.study import Study
from src.models.observation import Observation
from src.utils.security import hash_password
import src.main as main
from src.middlewares import rate_limit

@pytest.fixture()
def client(monkeypatch):
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session=sessionmaker(bind=engine,expire_on_commit=False)
    with Session() as s:
        for role in ('admin','analyst','viewer'):
            s.add(User(email=role+'@demo.local',role=role,password_hash=hash_password('Research2026!')))
        s.add(Study(name='批次乙',source_filename='f.csv'));s.flush()
        for i in range(1,40):
            s.add(Observation(study_id=1,source_key=f'T{i:03d}',values={'porosity':float(i),'absorption':float(i)+1.0}))
        s.commit()
    def override():
        with Session() as s: yield s
    main.app.dependency_overrides[get_db]=override
    monkeypatch.setattr(rate_limit.redis,'incr',lambda *a,**k:1)
    monkeypatch.setattr(rate_limit.redis,'expire',lambda *a,**k:True)
    with TestClient(main.app) as c: yield c
    main.app.dependency_overrides.clear()

def token(client,who='analyst'):
    r=client.post('/auth/login',json={'email':f'{who}@demo.local','password':'Research2026!'})
    assert r.status_code==200,r.text
    return {'Authorization':'Bearer '+r.json()['token']}

def payload(pairs,alpha=0.05):
    return {'study_id':1,'name':'API 序贯轮次','alpha':alpha,'pairs':[{'label':f'P{i}','specimen_a':a,'specimen_b':b} for i,(a,b) in enumerate(pairs,1)]}

def test_login_and_roundtrip(client):
    h=token(client)
    r=client.post('/sequential',json=payload([('T001','T002'),('T003','T004')]),headers=h)
    assert r.status_code==200,r.text
    sid=r.json()['session']['id']
    assert r.json()['session']['pair_count']==2
    r=client.get(f'/sequential/{sid}',headers=h);assert r.status_code==200
    r=client.post(f'/sequential/{sid}/measure',json={'seq':2,'values_a':{'porosity':3.0,'absorption':4.0},'values_b':{'porosity':2.0,'absorption':3.0}},headers=h)
    assert r.status_code==200 and r.json()['booked']==[]
    assert r.json()['next']['seq']==1
    r=client.post(f'/sequential/{sid}/measure',json={'seq':1,'values_a':{'porosity':1.0,'absorption':2.0},'values_b':{'porosity':0.5,'absorption':1.0}},headers=h)
    assert r.json()['booked']==[1,2]

def test_viewer_read_only(client):
    h=token(client)
    r=client.post('/sequential',json=payload([('T001','T002')]),headers=h)
    sid=r.json()['session']['id']
    hv=token(client,'viewer')
    assert client.get(f'/sequential/{sid}',headers=hv).status_code==200
    assert client.post('/sequential',json=payload([('T003','T004')]),headers=hv).status_code==403
    assert client.post(f'/sequential/{sid}/ingest',headers=hv).status_code==403

def test_unauthenticated_rejected(client):
    assert client.get('/sequential').status_code==401
    assert client.post('/sequential',json=payload([('T001','T002')])).status_code==401

def test_invalid_alpha_and_pairs_rejected(client):
    h=token(client)
    assert client.post('/sequential',json=payload([('T001','T002')],alpha=0.5),headers=h).status_code==422
    assert client.post('/sequential',json={'study_id':1,'name':'x','alpha':0.05,'pairs':[]},headers=h).status_code==422
    bad=payload([('T001','T002')]);bad['pairs'][0]['specimen_b']='T001'
    assert client.post('/sequential',json=bad,headers=h).status_code==422

def test_ingest_retry_is_idempotent(client):
    h=token(client)
    r=client.post('/sequential',json=payload([('T001','T002')]),headers=h);sid=r.json()['session']['id']
    body={'seq':1,'values_a':{'porosity':5.0,'absorption':6.0},'values_b':{'porosity':4.0,'absorption':5.0}}
    first=client.post(f'/sequential/{sid}/measure',json=body,headers=h)
    assert first.json()['booked']==[1]
    second=client.post(f'/sequential/{sid}/measure',json=body,headers=h)
    assert second.status_code==200 and second.json()['booked']==[] and second.json()['idempotent'] is True
    third=client.post(f'/sequential/{sid}/ingest',headers=h)
    assert third.json()['booked']==[] and len(third.json()['entries'])==1
