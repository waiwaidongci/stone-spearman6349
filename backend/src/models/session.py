from sqlalchemy import Column,Integer,String,Float,JSON,ForeignKey
from src.config.database import Base

class SequentialSession(Base):
    """一轮序贯监测：冻结登记次序，累计同向/反向/并列跳过证据，首次达线冻结结论。"""
    __tablename__='sequential_sessions'
    id=Column(Integer,primary_key=True)
    study_id=Column(Integer,ForeignKey('studies.id'),nullable=False)
    name=Column(String(120),nullable=False)
    alpha=Column(Float,nullable=False)
    status=Column(String(20),default='running')
    pair_count=Column(Integer,nullable=False)
    pairs_checksum=Column(String(64),nullable=False)
    concordant=Column(Integer,default=0)
    discordant=Column(Integer,default=0)
    skipped=Column(Integer,default=0)
    processed_seq=Column(Integer,default=0)
    log_e=Column(Float,default=0.0)
    e_value=Column(Float,default=1.0)
    peak_log_e=Column(Float,default=0.0)
    decision=Column(String(20),nullable=True)
    frozen_at=Column(String(40),nullable=True)
    evidence=Column(JSON,nullable=True)
    created_at=Column(String(40),nullable=False)
    created_by=Column(String(120),nullable=False)
