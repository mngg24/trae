from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    scene_id: str | None
    asset_type: str
    provider: str | None
    uri: str
    metadata_json: dict | None
    created_at: datetime


class ProjectResultOut(BaseModel):
    mp4_url: str | None = None
    hls_master_url: str | None = None

