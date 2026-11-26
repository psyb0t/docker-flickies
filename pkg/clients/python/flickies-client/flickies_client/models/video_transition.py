from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.video_transition_effect import VideoTransitionEffect

T = TypeVar("T", bound="VideoTransition")


@_attrs_define
class VideoTransition:
    """
    Attributes:
        effect (VideoTransitionEffect): Transition used between adjacent input clips.
        duration_sec (float): Duration in seconds.
    """

    effect: VideoTransitionEffect
    duration_sec: float
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        effect = self.effect.value

        duration_sec = self.duration_sec

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "effect": effect,
                "duration_sec": duration_sec,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        effect = VideoTransitionEffect(d.pop("effect"))

        duration_sec = d.pop("duration_sec")

        video_transition = cls(
            effect=effect,
            duration_sec=duration_sec,
        )

        video_transition.additional_properties = d
        return video_transition

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
