from enum import Enum


class VideoScenesRequestArtifacts(str, Enum):
    CLIPS = "clips"
    FRAMES = "frames"
    NONE = "none"

    def __str__(self) -> str:
        return str(self.value)
