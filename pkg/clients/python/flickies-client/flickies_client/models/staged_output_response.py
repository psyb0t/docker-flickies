from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="StagedOutputResponse")


@_attrs_define
class StagedOutputResponse:
    """
    Attributes:
        path (str): Relative staging path to the output file.
        size (int): Size of the output in bytes.
        sha256 (Union[None, Unset, str]): SHA-256 checksum of the output bytes.
        duration_sec (Union[None, Unset, float]): Duration in seconds.
        width (Union[None, Unset, int]): Width in pixels.
        height (Union[None, Unset, int]): Height in pixels.
    """

    path: str
    size: int
    sha256: Union[None, Unset, str] = UNSET
    duration_sec: Union[None, Unset, float] = UNSET
    width: Union[None, Unset, int] = UNSET
    height: Union[None, Unset, int] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        path = self.path

        size = self.size

        sha256: Union[None, Unset, str]
        if isinstance(self.sha256, Unset):
            sha256 = UNSET
        else:
            sha256 = self.sha256

        duration_sec: Union[None, Unset, float]
        if isinstance(self.duration_sec, Unset):
            duration_sec = UNSET
        else:
            duration_sec = self.duration_sec

        width: Union[None, Unset, int]
        if isinstance(self.width, Unset):
            width = UNSET
        else:
            width = self.width

        height: Union[None, Unset, int]
        if isinstance(self.height, Unset):
            height = UNSET
        else:
            height = self.height

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "path": path,
                "size": size,
            }
        )
        if sha256 is not UNSET:
            field_dict["sha256"] = sha256
        if duration_sec is not UNSET:
            field_dict["duration_sec"] = duration_sec
        if width is not UNSET:
            field_dict["width"] = width
        if height is not UNSET:
            field_dict["height"] = height

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        path = d.pop("path")

        size = d.pop("size")

        def _parse_sha256(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        sha256 = _parse_sha256(d.pop("sha256", UNSET))

        def _parse_duration_sec(data: object) -> Union[None, Unset, float]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, float], data)

        duration_sec = _parse_duration_sec(d.pop("duration_sec", UNSET))

        def _parse_width(data: object) -> Union[None, Unset, int]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, int], data)

        width = _parse_width(d.pop("width", UNSET))

        def _parse_height(data: object) -> Union[None, Unset, int]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, int], data)

        height = _parse_height(d.pop("height", UNSET))

        staged_output_response = cls(
            path=path,
            size=size,
            sha256=sha256,
            duration_sec=duration_sec,
            width=width,
            height=height,
        )

        staged_output_response.additional_properties = d
        return staged_output_response

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
