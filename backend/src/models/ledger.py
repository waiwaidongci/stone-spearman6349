from sqlalchemy import Column,Integer,String,Float,JSON,ForeignKey,UniqueConstraint
from src.config.database import Base

class LedgerEntry(Base):
    """按登记次序追加的入账证据；(session_id, seq) 与 (session_id, pair_id) 唯一，重试不会重复累计同一对。"""
    __tablename__='ledger_entries'
    __table_args__=(UniqueConstraint('session_id','seq'),UniqueConstraint('session_id','pair_id'))
    id=Column(Integer,primary_key=True)
    session_id=Column(Integer,ForeignKey('sequential_sessions.id'),nullable=False)
    pair_id=Column(Integer,ForeignKey('specimen_pairs.id'),nullable=False)
    seq=Column(Integer,nullable=False)
    label=Column(String(120),nullable=False,default='')
    source_key_a=Column(String(100),nullable=False)
    source_key_b=Column(String(100),nullable=False)
    values_a=Column(JSON,nullable=False)
    values_b=Column(JSON,nullable=False)
    outcome=Column(String(20),nullable=False)
    concordant=Column(Integer,default=0)
    discordant=Column(Integer,default=0)
    skipped=Column(Integer,default=0)
    log_e=Column(Float,nullable=False)
    e_value=Column(Float,nullable=False)
    created_at=Column(String(40),nullable=False)
