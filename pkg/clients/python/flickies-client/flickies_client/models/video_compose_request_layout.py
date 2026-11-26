from enum import Enum


class VideoComposeRequestLayout(str, Enum):
    HORIZONTAL = "horizontal"
    PIP = "pip"
    VERTICAL = "vertical"

    def __str__(self) -> str:
        return str(self.value)
