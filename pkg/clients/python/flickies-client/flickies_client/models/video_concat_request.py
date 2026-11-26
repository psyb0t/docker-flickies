from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.video_transition import VideoTransition


T = TypeVar("T", bound="VideoConcatRequest")


@_attrs_define
class VideoConcatRequest:
    """Concatenate ≥2 videos in order. Exactly one of inputs_paths / inputs_urls must be provided.

    Attributes:
        output_path (Union[None, Unset, str]): Staged output path in synchronous mode.
        output_url (Union[None, Unset, str]): Presigned PUT URL in synchronous mode.
        async_job (Union[Unset, bool]): Schedule the job and stage the result under jobs/. Default: False.
        webhook_url (Union[None, Unset, str]): Callback URL for asynchronous completion.
        inputs_paths (Union[None, Unset, list[str]]): Relative staging paths for clips in playback order.
        inputs_urls (Union[None, Unset, list[str]]): HTTP(S) URLs for clips in playback order.
        transitions (Union[None, Unset, list['VideoTransition']]): One transition per join. Omit for the original concat
            behavior.
        precise (Union[Unset, bool]): When false (default), concat uses the concat demuxer with
            `-c copy` — fast, but requires all inputs to share identical
            codec / timebase / SAR (mixing different encoders corrupts or
            fails). When true, the concat demuxer re-encodes with uniform
            H.264 + AAC so mixed inputs join cleanly (slower; single-
            generation re-encode).
             Default: False.
    """

    output_path: Union[None, Unset, str] = UNSET
    output_url: Union[None, Unset, str] = UNSET
    async_job: Union[Unset, bool] = False
    webhook_url: Union[None, Unset, str] = UNSET
    inputs_paths: Union[None, Unset, list[str]] = UNSET
    inputs_urls: Union[None, Unset, list[str]] = UNSET
    transitions: Union[None, Unset, list["VideoTransition"]] = UNSET
    precise: Union[Unset, bool] = False
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        output_path: Union[None, Unset, str]
        if isinstance(self.output_path, Unset):
            output_path = UNSET
        else:
            output_path = self.output_path

        output_url: Union[None, Unset, str]
        if isinstance(self.output_url, Unset):
            output_url = UNSET
        else:
            output_url = self.output_url

        async_job = self.async_job

        webhook_url: Union[None, Unset, str]
        if isinstance(self.webhook_url, Unset):
            webhook_url = UNSET
        else:
            webhook_url = self.webhook_url

        inputs_paths: Union[None, Unset, list[str]]
        if isinstance(self.inputs_paths, Unset):
            inputs_paths = UNSET
        elif isinstance(self.inputs_paths, list):
            inputs_paths = self.inputs_paths

        else:
            inputs_paths = self.inputs_paths

        inputs_urls: Union[None, Unset, list[str]]
        if isinstance(self.inputs_urls, Unset):
            inputs_urls = UNSET
        elif isinstance(self.inputs_urls, list):
            inputs_urls = self.inputs_urls

        else:
            inputs_urls = self.inputs_urls

        transitions: Union[None, Unset, list[dict[str, Any]]]
        if isinstance(self.transitions, Unset):
            transitions = UNSET
        elif isinstance(self.transitions, list):
            transitions = []
            for transitions_type_0_item_data in self.transitions:
                transitions_type_0_item = transitions_type_0_item_data.to_dict()
                transitions.append(transitions_type_0_item)

        else:
            transitions = self.transitions

        precise = self.precise

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if output_path is not UNSET:
            field_dict["output_path"] = output_path
        if output_url is not UNSET:
            field_dict["output_url"] = output_url
        if async_job is not UNSET:
            field_dict["async_job"] = async_job
        if webhook_url is not UNSET:
            field_dict["webhook_url"] = webhook_url
        if inputs_paths is not UNSET:
            field_dict["inputs_paths"] = inputs_paths
        if inputs_urls is not UNSET:
            field_dict["inputs_urls"] = inputs_urls
        if transitions is not UNSET:
            field_dict["transitions"] = transitions
        if precise is not UNSET:
            field_dict["precise"] = precise

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.video_transition import VideoTransition

        d = dict(src_dict)

        def _parse_output_path(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        output_path = _parse_output_path(d.pop("output_path", UNSET))

        def _parse_output_url(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        output_url = _parse_output_url(d.pop("output_url", UNSET))

        async_job = d.pop("async_job", UNSET)

        def _parse_webhook_url(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        webhook_url = _parse_webhook_url(d.pop("webhook_url", UNSET))

        def _parse_inputs_paths(data: object) -> Union[None, Unset, list[str]]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                inputs_paths_type_0 = cast(list[str], data)

                return inputs_paths_type_0
            except:  # noqa: E722
                pass
            return cast(Union[None, Unset, list[str]], data)

        inputs_paths = _parse_inputs_paths(d.pop("inputs_paths", UNSET))

        def _parse_inputs_urls(data: object) -> Union[None, Unset, list[str]]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                inputs_urls_type_0 = cast(list[str], data)

                return inputs_urls_type_0
            except:  # noqa: E722
                pass
            return cast(Union[None, Unset, list[str]], data)

        inputs_urls = _parse_inputs_urls(d.pop("inputs_urls", UNSET))

        def _parse_transitions(data: object) -> Union[None, Unset, list["VideoTransition"]]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                transitions_type_0 = []
                _transitions_type_0 = data
                for transitions_type_0_item_data in _transitions_type_0:
                    transitions_type_0_item = VideoTransition.from_dict(transitions_type_0_item_data)

                    transitions_type_0.append(transitions_type_0_item)

                return transitions_type_0
            except:  # noqa: E722
                pass
            return cast(Union[None, Unset, list["VideoTransition"]], data)

        transitions = _parse_transitions(d.pop("transitions", UNSET))

        precise = d.pop("precise", UNSET)

        video_concat_request = cls(
            output_path=output_path,
            output_url=output_url,
            async_job=async_job,
            webhook_url=webhook_url,
            inputs_paths=inputs_paths,
            inputs_urls=inputs_urls,
            transitions=transitions,
            precise=precise,
        )

        video_concat_request.additional_properties = d
        return video_concat_request

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
