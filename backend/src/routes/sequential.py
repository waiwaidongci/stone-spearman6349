from fastapi import APIRouter,Depends
from src.config.database import get_db
from src.middlewares.auth import current_user,writer
from src.schemas.sequential import SequentialSessionInput,MeasurementInput
from src.services import sequential
router=APIRouter()

@router.get('/sequential')
def list_sessions(db=Depends(get_db),user=Depends(current_user)): return sequential.list_sessions(db)

@router.post('/sequential')
def create(data:SequentialSessionInput,db=Depends(get_db),user=Depends(writer)): return sequential.create(db,data,user)

@router.get('/sequential/{id}')
def detail(id:int,db=Depends(get_db),user=Depends(current_user)): return sequential.detail(db,id)

@router.post('/sequential/{id}/measure')
def measure(id:int,data:MeasurementInput,db=Depends(get_db),user=Depends(writer)): return sequential.measure(db,id,data,user)

@router.post('/sequential/{id}/ingest')
def ingest(id:int,db=Depends(get_db),user=Depends(writer)): return sequential.ingest(db,id,user)
