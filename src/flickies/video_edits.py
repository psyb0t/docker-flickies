from __future__ import annotations

import re
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, model_validator

Seconds = Annotated[float, Field(strict=True, ge=0, le=86400)]
Dimension = Annotated[int, Field(strict=True, ge=16, le=4096, multiple_of=2)]
Coordinate = Annotated[int, Field(strict=True, ge=0, le=16384)]


class Word(BaseModel):
    text: str = Field(min_length=1, max_length=128, pattern=r"^[^\\{}\r\n]+$")
    start_sec: Seconds
    end_sec: Seconds


class Subtitles(BaseModel):
    subtitle_path: str | None = None
    words: list[Word] | None = Field(default=None, min_length=1, max_length=12000)
    mode: Literal["burn", "embed"] = "burn"
    words_per_line: int = Field(default=4, ge=1, le=12)
    font_size: int = Field(default=56, ge=12, le=140)

    @model_validator(mode="after")
    def validate_source(self) -> Self:
        if bool(self.subtitle_path) == bool(self.words):
            raise ValueError("provide exactly one of subtitle_path or words")
        if self.words:
            if self.mode != "burn":
                raise ValueError("word highlighting requires burn mode")
            previous_end = 0.0
            for word in self.words:
                if word.start_sec < previous_end or word.end_sec <= word.start_sec:
                    raise ValueError("word timestamps must be ordered and non-overlapping")
                previous_end = word.end_sec
        return self


class Overlay(BaseModel):
    image_path: str | None = None
    text: str | None = Field(default=None, min_length=1, max_length=160, pattern=r"^[^@\r\n]+$")
    start_sec: Seconds = 0.0
    end_sec: Seconds
    x: Coordinate = 24
    y: Coordinate = 24

    @model_validator(mode="after")
    def validate_overlay(self) -> Self:
        if bool(self.image_path) == bool(self.text):
            raise ValueError("provide exactly one of image_path or text")
        if self.end_sec <= self.start_sec:
            raise ValueError("end_sec must exceed start_sec")
        return self


class Crop(BaseModel):
    width: Dimension
    height: Dimension
    mode: Literal["crop", "pad", "blur"] = "crop"
    x: Coordinate | None = None
    y: Coordinate | None = None

    @model_validator(mode="after")
    def validate_coordinates(self) -> Self:
        if (self.x is None) != (self.y is None) or (self.x is not None and self.mode != "crop"):
            raise ValueError("x and y must be given together in crop mode")
        return self


class Transition(BaseModel):
    effect: Literal["cut", "fade", "wipeleft", "wiperight", "slideleft", "slideright", "dissolve"]
    duration_sec: Annotated[float, Field(strict=True, ge=0, le=10)]

    @model_validator(mode="after")
    def validate_duration(self) -> Self:
        if (self.effect == "cut") != (self.duration_sec == 0):
            raise ValueError("cuts require zero duration and transitions require positive duration")
        return self


class Scenes(BaseModel):
    threshold: float = Field(default=10, strict=True, gt=0, le=100)
    artifacts: Literal["none", "frames", "clips"] = "none"
    max_scenes: int = Field(default=50, strict=True, ge=1, le=200)


class Compose(BaseModel):
    second_path: str = Field(min_length=1)
    layout: Literal["horizontal", "vertical", "pip"] = "horizontal"
    width: Dimension = 1280
    height: Dimension = 720
    audio: Literal["first", "second", "none"] = "first"

    @model_validator(mode="after")
    def validate_canvas(self) -> Self:
        if self.width % 8 or self.height % 8:
            raise ValueError("composition dimensions must be multiples of 8")
        return self


class QualityAnalysis(BaseModel):
    black_min_sec: float = Field(default=0.25, strict=True, ge=0.05, le=60)
    freeze_min_sec: float = Field(default=0.5, strict=True, ge=0.05, le=60)
    silence_min_sec: float = Field(default=0.5, strict=True, ge=0.05, le=60)
    silence_db: float = Field(default=-40, strict=True, ge=-90, le=-5)


class GridStyle(BaseModel):
    timestamps: bool = Field(default=False, strict=True)
    layout: Literal["tight", "review"] = "tight"


class SampleFrames(BaseModel):
    sample_interval_sec: float = Field(default=1.0, strict=True, ge=0.1, le=60)
    max_frames: int = Field(default=60, strict=True, ge=1, le=120)


def karaoke_ass(words: list[Word], words_per_line: int, font_size: int) -> str:
    def timestamp(ticks: int) -> str:
        seconds, cs = divmod(ticks, 100)
        minutes, sec = divmod(seconds, 60)
        hour, minute = divmod(minutes, 60)
        return f"{hour}:{minute:02}:{sec:02}.{cs:02}"

    groups: list[list[Word]] = []
    for word in words:
        if (
            not groups
            or len(groups[-1]) >= words_per_line
            or word.start_sec - groups[-1][-1].end_sec >= 0.45
            or re.search(r"[.!?]$", groups[-1][-1].text)
        ):
            groups.append([])
        groups[-1].append(word)

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,DejaVu Sans,{font_size},&H0000DDFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,2,48,48,120,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for group in groups:
        start = round(group[0].start_sec * 100)
        end = max(start + 1, round(group[-1].end_sec * 100))
        parts = []
        for index, word in enumerate(group):
            following = round(group[index + 1].start_sec * 100) if index + 1 < len(group) else end
            duration = following - round(word.start_sec * 100)
            parts.append(r"{\k" + str(max(0, duration)) + "}" + word.text)
        lines.append(
            f"Dialogue: 0,{timestamp(start)},{timestamp(end)},Default,,0,0,0,," + " ".join(parts)
        )
    return "\n".join(lines) + "\n"
