from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="EngineInfo")


@_attrs_define
class EngineInfo:
    """
    Attributes:
        slug (str):
        executor (str):
        loaded (bool):
        noncommercial (bool):
        variant (None | str | Unset):
        cuda_only (bool | Unset):
        vram_gb_min (float | None | Unset):
        description (str | Unset):
        last_used_secs_ago (float | None | Unset): Seconds since this engine last served a request; null if never used.
    """

    slug: str
    executor: str
    loaded: bool
    noncommercial: bool
    variant: None | str | Unset = UNSET
    cuda_only: bool | Unset = UNSET
    vram_gb_min: float | None | Unset = UNSET
    description: str | Unset = UNSET
    last_used_secs_ago: float | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        slug = self.slug

        executor = self.executor

        loaded = self.loaded

        noncommercial = self.noncommercial

        variant: None | str | Unset
        if isinstance(self.variant, Unset):
            variant = UNSET
        else:
            variant = self.variant

        cuda_only = self.cuda_only

        vram_gb_min: float | None | Unset
        if isinstance(self.vram_gb_min, Unset):
            vram_gb_min = UNSET
        else:
            vram_gb_min = self.vram_gb_min

        description = self.description

        last_used_secs_ago: float | None | Unset
        if isinstance(self.last_used_secs_ago, Unset):
            last_used_secs_ago = UNSET
        else:
            last_used_secs_ago = self.last_used_secs_ago

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "slug": slug,
                "executor": executor,
                "loaded": loaded,
                "noncommercial": noncommercial,
            }
        )
        if variant is not UNSET:
            field_dict["variant"] = variant
        if cuda_only is not UNSET:
            field_dict["cuda_only"] = cuda_only
        if vram_gb_min is not UNSET:
            field_dict["vram_gb_min"] = vram_gb_min
        if description is not UNSET:
            field_dict["description"] = description
        if last_used_secs_ago is not UNSET:
            field_dict["last_used_secs_ago"] = last_used_secs_ago

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        slug = d.pop("slug")

        executor = d.pop("executor")

        loaded = d.pop("loaded")

        noncommercial = d.pop("noncommercial")

        def _parse_variant(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        variant = _parse_variant(d.pop("variant", UNSET))

        cuda_only = d.pop("cuda_only", UNSET)

        def _parse_vram_gb_min(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        vram_gb_min = _parse_vram_gb_min(d.pop("vram_gb_min", UNSET))

        description = d.pop("description", UNSET)

        def _parse_last_used_secs_ago(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        last_used_secs_ago = _parse_last_used_secs_ago(d.pop("last_used_secs_ago", UNSET))

        engine_info = cls(
            slug=slug,
            executor=executor,
            loaded=loaded,
            noncommercial=noncommercial,
            variant=variant,
            cuda_only=cuda_only,
            vram_gb_min=vram_gb_min,
            description=description,
            last_used_secs_ago=last_used_secs_ago,
        )

        engine_info.additional_properties = d
        return engine_info

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
