from enum import Enum


class VideoRestoreRequestEngine(str, Enum):
    GFPGAN = "gfpgan"

    def __str__(self) -> str:
        return str(self.value)
