from pydantic import BaseModel, Field, model_validator


class BlueprintProjectMeta(BaseModel):
    topic: str = Field(min_length=1, max_length=512)
    target_duration_seconds: int = Field(gt=0)
    estimated_scene_count: int = Field(gt=0, le=50)


class BlueprintScene(BaseModel):
    scene_number: int = Field(gt=0, le=200)
    narration_script: str = Field(min_length=1)
    image_generation_prompt: str = Field(min_length=1)
    camera_movement_suggestion: str = Field(min_length=1)
    estimated_duration_seconds: int = Field(gt=0)


class Blueprint(BaseModel):
    project_meta: BlueprintProjectMeta
    scenes: list[BlueprintScene] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_shape(self) -> "Blueprint":
        if self.project_meta.estimated_scene_count != len(self.scenes):
            raise ValueError("project_meta.estimated_scene_count must match len(scenes)")

        scene_numbers = [s.scene_number for s in self.scenes]
        if len(set(scene_numbers)) != len(scene_numbers):
            raise ValueError("scenes.scene_number must be unique")

        expected = list(range(1, len(self.scenes) + 1))
        if sorted(scene_numbers) != expected:
            raise ValueError("scenes.scene_number must start at 1 and be contiguous")

        total_duration = sum(s.estimated_duration_seconds for s in self.scenes)
        if total_duration <= 0:
            raise ValueError("sum(scenes[].estimated_duration_seconds) must be > 0")

        return self

