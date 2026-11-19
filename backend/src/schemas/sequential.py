from pydantic import BaseModel,Field

class PairInput(BaseModel):
    label:str=Field(default='',max_length=120)
    specimen_a:str=Field(min_length=1,max_length=100)
    specimen_b:str=Field(min_length=1,max_length=100)

class SequentialSessionInput(BaseModel):
    study_id:int=Field(gt=0)
    name:str=Field(min_length=2,max_length=120)
    alpha:float=Field(default=0.05,ge=0.001,le=0.2)
    pairs:list[PairInput]=Field(min_length=1,max_length=500)

class MeasurementInput(BaseModel):
    seq:int=Field(ge=1)
    values_a:dict|None=None
    values_b:dict|None=None
