from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="HealthResponse")


@_attrs_define
class HealthResponse:
    """
    Attributes:
        status (str):
        version (str):
        device (str): auto / cpu / cuda
        available_engines (list[str]):
        noncommercial_enabled (bool):
        enabled_engines (list[str] | Unset):
        loaded_engine (None | str | Unset): Currently resident engine slug, or null if none loaded.
    """

    status: str
    version: str
    device: str
    available_engines: list[str]
    noncommercial_enabled: bool
    enabled_engines: list[str] | Unset = UNSET
    loaded_engine: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        status = self.status

        version = self.version

        device = self.device

        available_engines = self.available_engines

        noncommercial_enabled = self.noncommercial_enabled

        enabled_engines: list[str] | Unset = UNSET
        if not isinstance(self.enabled_engines, Unset):
            enabled_engines = self.enabled_engines

        loaded_engine: None | str | Unset
        if isinstance(self.loaded_engine, Unset):
            loaded_engine = UNSET
        else:
            loaded_engine = self.loaded_engine

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "status": status,
                "version": version,
                "device": device,
                "available_engines": available_engines,
                "noncommercial_enabled": noncommercial_enabled,
            }
        )
        if enabled_engines is not UNSET:
            field_dict["enabled_engines"] = enabled_engines
        if loaded_engine is not UNSET:
            field_dict["loaded_engine"] = loaded_engine

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        status = d.pop("status")

        version = d.pop("version")

        device = d.pop("device")

        available_engines = cast(list[str], d.pop("available_engines"))

        noncommercial_enabled = d.pop("noncommercial_enabled")

        enabled_engines = cast(list[str], d.pop("enabled_engines", UNSET))

        def _parse_loaded_engine(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        loaded_engine = _parse_loaded_engine(d.pop("loaded_engine", UNSET))

        health_response = cls(
            status=status,
            version=version,
            device=device,
            available_engines=available_engines,
            noncommercial_enabled=noncommercial_enabled,
            enabled_engines=enabled_engines,
            loaded_engine=loaded_engine,
        )

        health_response.additional_properties = d
        return health_response

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
