from sqlalchemy import Column,Integer,String,JSON,ForeignKey,UniqueConstraint
from src.config.database import Base

class SpecimenPair(Base):
    """登记次序中的一对独立试件；试件对互不重叠，整对只属于一轮序贯监测。"""
    __tablename__='specimen_pairs'
    __table_args__=(UniqueConstraint('session_id','seq'),)
    id=Column(Integer,primary_key=True)
    study_id=Column(Integer,ForeignKey('studies.id'),nullable=False)
    session_id=Column(Integer,ForeignKey('sequential_sessions.id'),nullable=True)
    seq=Column(Integer,nullable=False)
    label=Column(String(120),nullable=False,default='')
    source_key_a=Column(String(100),nullable=False)
    source_key_b=Column(String(100),nullable=False)
    created_at=Column(String(40),nullable=False)
    created_by=Column(String(120),nullable=False)

class PairMember(Base):
    """试件与试件对的占用关系；(study_id, source_key) 唯一保证试件对互不重叠。"""
    __tablename__='pair_members'
    __table_args__=(UniqueConstraint('study_id','source_key'),UniqueConstraint('pair_id','side'))
    id=Column(Integer,primary_key=True)
    study_id=Column(Integer,ForeignKey('studies.id'),nullable=False)
    pair_id=Column(Integer,ForeignKey('specimen_pairs.id'),nullable=False)
    source_key=Column(String(100),nullable=False)
    side=Column(String(1),nullable=False)
    values=Column(JSON,nullable=True)
    locked_at=Column(String(40),nullable=True)
