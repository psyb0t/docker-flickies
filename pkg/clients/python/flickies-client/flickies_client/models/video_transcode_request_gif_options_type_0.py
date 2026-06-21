from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.video_transcode_request_gif_options_type_0_palette_mode import (
    VideoTranscodeRequestGifOptionsType0PaletteMode,
)
from ..types import UNSET, Unset

T = TypeVar("T", bound="VideoTranscodeRequestGifOptionsType0")


@_attrs_define
class VideoTranscodeRequestGifOptionsType0:
    """Only consulted when output_format=gif.

    Attributes:
        width (int | None | Unset):
        loop (int | Unset): 0 = infinite Default: 0.
        palette_mode (VideoTranscodeRequestGifOptionsType0PaletteMode | Unset):  Default:
            VideoTranscodeRequestGifOptionsType0PaletteMode.FULL.
    """

    width: int | None | Unset = UNSET
    loop: int | Unset = 0
    palette_mode: VideoTranscodeRequestGifOptionsType0PaletteMode | Unset = (
        VideoTranscodeRequestGifOptionsType0PaletteMode.FULL
    )
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        width: int | None | Unset
        if isinstance(self.width, Unset):
            width = UNSET
        else:
            width = self.width

        loop = self.loop

        palette_mode: str | Unset = UNSET
        if not isinstance(self.palette_mode, Unset):
            palette_mode = self.palette_mode.value

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if width is not UNSET:
            field_dict["width"] = width
        if loop is not UNSET:
            field_dict["loop"] = loop
        if palette_mode is not UNSET:
            field_dict["palette_mode"] = palette_mode

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_width(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        width = _parse_width(d.pop("width", UNSET))

        loop = d.pop("loop", UNSET)

        _palette_mode = d.pop("palette_mode", UNSET)
        palette_mode: VideoTranscodeRequestGifOptionsType0PaletteMode | Unset
        if isinstance(_palette_mode, Unset):
            palette_mode = UNSET
        else:
            palette_mode = VideoTranscodeRequestGifOptionsType0PaletteMode(_palette_mode)

        video_transcode_request_gif_options_type_0 = cls(
            width=width,
            loop=loop,
            palette_mode=palette_mode,
        )

        video_transcode_request_gif_options_type_0.additional_properties = d
        return video_transcode_request_gif_options_type_0

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
