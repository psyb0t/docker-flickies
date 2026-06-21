from enum import Enum


class VideoTranscodeRequestGifOptionsType0PaletteMode(str, Enum):
    DIFF = "diff"
    FULL = "full"
    SINGLE = "single"

    def __str__(self) -> str:
        return str(self.value)
