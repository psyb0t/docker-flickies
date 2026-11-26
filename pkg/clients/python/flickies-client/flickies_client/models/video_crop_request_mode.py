from enum import Enum


class VideoCropRequestMode(str, Enum):
    BLUR = "blur"
    CROP = "crop"
    PAD = "pad"

    def __str__(self) -> str:
        return str(self.value)
