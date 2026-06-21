from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.engine_info import EngineInfo


T = TypeVar("T", bound="EngineList")


@_attrs_define
class EngineList:
    """
    Attributes:
        engines (list[EngineInfo]):
    """

    engines: list[EngineInfo]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        engines = []
        for engines_item_data in self.engines:
            engines_item = engines_item_data.to_dict()
            engines.append(engines_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "engines": engines,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.engine_info import EngineInfo

        d = dict(src_dict)
        engines = []
        _engines = d.pop("engines")
        for engines_item_data in _engines:
            engines_item = EngineInfo.from_dict(engines_item_data)

            engines.append(engines_item)

        engine_list = cls(
            engines=engines,
        )

        engine_list.additional_properties = d
        return engine_list

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
