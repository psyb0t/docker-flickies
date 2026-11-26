from enum import Enum


class VideoTransitionEffect(str, Enum):
    CUT = "cut"
    DISSOLVE = "dissolve"
    FADE = "fade"
    SLIDELEFT = "slideleft"
    SLIDERIGHT = "slideright"
    WIPELEFT = "wipeleft"
    WIPERIGHT = "wiperight"

    def __str__(self) -> str:
        return str(self.value)
