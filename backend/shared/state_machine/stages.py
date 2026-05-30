try:
    from enum import StrEnum
except ImportError:
    from enum import Enum

    class StrEnum(str, Enum):
        pass


class PipelineStage(StrEnum):
    GENERATE_BLUEPRINT = "GENERATE_BLUEPRINT"
    GENERATE_ASSETS = "GENERATE_ASSETS"
    RENDER_ASSEMBLE = "RENDER_ASSEMBLE"
