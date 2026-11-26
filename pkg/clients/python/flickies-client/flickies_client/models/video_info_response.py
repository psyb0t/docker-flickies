from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="VideoInfoResponse")


@_attrs_define
class VideoInfoResponse:
    """
    Attributes:
        duration_sec (Union[Unset, float]): Duration in seconds.
        width (Union[Unset, int]): Width in pixels.
        height (Union[Unset, int]): Height in pixels.
        fps (Union[Unset, float]): Video frames per second.
        video_codec (Union[Unset, str]): Video codec detected in the input.
        audio_codec (Union[None, Unset, str]): Audio codec detected in the input, or null for a silent video.
        bitrate (Union[None, Unset, int]): Overall stream bitrate in bits per second, when known.
        container_format (Union[None, Unset, str]): Container names reported by the probe.
        size_bytes (Union[Unset, int]): Input file size in bytes.
    """

    duration_sec: Union[Unset, float] = UNSET
    width: Union[Unset, int] = UNSET
    height: Union[Unset, int] = UNSET
    fps: Union[Unset, float] = UNSET
    video_codec: Union[Unset, str] = UNSET
    audio_codec: Union[None, Unset, str] = UNSET
    bitrate: Union[None, Unset, int] = UNSET
    container_format: Union[None, Unset, str] = UNSET
    size_bytes: Union[Unset, int] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        duration_sec = self.duration_sec

        width = self.width

        height = self.height

        fps = self.fps

        video_codec = self.video_codec

        audio_codec: Union[None, Unset, str]
        if isinstance(self.audio_codec, Unset):
            audio_codec = UNSET
        else:
            audio_codec = self.audio_codec

        bitrate: Union[None, Unset, int]
        if isinstance(self.bitrate, Unset):
            bitrate = UNSET
        else:
            bitrate = self.bitrate

        container_format: Union[None, Unset, str]
        if isinstance(self.container_format, Unset):
            container_format = UNSET
        else:
            container_format = self.container_format

        size_bytes = self.size_bytes

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if duration_sec is not UNSET:
            field_dict["duration_sec"] = duration_sec
        if width is not UNSET:
            field_dict["width"] = width
        if height is not UNSET:
            field_dict["height"] = height
        if fps is not UNSET:
            field_dict["fps"] = fps
        if video_codec is not UNSET:
            field_dict["video_codec"] = video_codec
        if audio_codec is not UNSET:
            field_dict["audio_codec"] = audio_codec
        if bitrate is not UNSET:
            field_dict["bitrate"] = bitrate
        if container_format is not UNSET:
            field_dict["container_format"] = container_format
        if size_bytes is not UNSET:
            field_dict["size_bytes"] = size_bytes

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        duration_sec = d.pop("duration_sec", UNSET)

        width = d.pop("width", UNSET)

        height = d.pop("height", UNSET)

        fps = d.pop("fps", UNSET)

        video_codec = d.pop("video_codec", UNSET)

        def _parse_audio_codec(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        audio_codec = _parse_audio_codec(d.pop("audio_codec", UNSET))

        def _parse_bitrate(data: object) -> Union[None, Unset, int]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, int], data)

        bitrate = _parse_bitrate(d.pop("bitrate", UNSET))

        def _parse_container_format(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        container_format = _parse_container_format(d.pop("container_format", UNSET))

        size_bytes = d.pop("size_bytes", UNSET)

        video_info_response = cls(
            duration_sec=duration_sec,
            width=width,
            height=height,
            fps=fps,
            video_codec=video_codec,
            audio_codec=audio_codec,
            bitrate=bitrate,
            container_format=container_format,
            size_bytes=size_bytes,
        )

        video_info_response.additional_properties = d
        return video_info_response

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
