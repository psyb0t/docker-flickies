from enum import Enum


class VideoThumbnailGridRequestLayout(str, Enum):
    REVIEW = "review"
    TIGHT = "tight"

    def __str__(self) -> str:
        return str(self.value)
