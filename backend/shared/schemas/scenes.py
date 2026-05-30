from datetime import datetime

from pydantic import BaseModel, ConfigDict

from shared.schemas.assets import AssetOut


class SceneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    scene_number: int
    narration_script: str | None
    image_generation_prompt: str | None
    camera_movement_suggestion: str | None
    estimated_duration_seconds: int | None
    status: str
    created_at: datetime
    updated_at: datetime
    assets: list[AssetOut]

