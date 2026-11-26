from enum import Enum


class VideoTranscodeRequestOutputFormat(str, Enum):
    GIF = "gif"
    MKV = "mkv"
    MOV = "mov"
    MP4 = "mp4"
    WEBM = "webm"

    def __str__(self) -> str:
        return str(self.value)
