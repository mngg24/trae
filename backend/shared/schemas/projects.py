from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    topic: str = Field(min_length=1, max_length=512)
    target_duration_seconds: int = Field(gt=0)


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    topic: str
    target_duration_seconds: int
    state: str
    blueprint_present: bool
    created_at: datetime
    updated_at: datetime

