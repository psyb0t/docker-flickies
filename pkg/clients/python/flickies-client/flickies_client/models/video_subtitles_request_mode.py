from enum import Enum


class VideoSubtitlesRequestMode(str, Enum):
    BURN = "burn"
    EMBED = "embed"

    def __str__(self) -> str:
        return str(self.value)
