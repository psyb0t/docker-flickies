from enum import Enum


class VideoComposeRequestAudio(str, Enum):
    FIRST = "first"
    NONE = "none"
    SECOND = "second"

    def __str__(self) -> str:
        return str(self.value)
