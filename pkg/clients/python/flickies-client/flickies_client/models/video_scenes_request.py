from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.video_scenes_request_artifacts import VideoScenesRequestArtifacts
from ..types import UNSET, Unset

T = TypeVar("T", bound="VideoScenesRequest")


@_attrs_define
class VideoScenesRequest:
    """Detect scene cuts and write a JSON manifest or a ZIP with the manifest and preview frames or trimmed clips.

    Attributes:
        file_path (Union[None, Unset, str]): Staged input path. Provide exactly one input.
        file_url (Union[None, Unset, str]): HTTP(S) input URL.
        output_path (Union[None, Unset, str]): Staged output path in synchronous mode.
        output_url (Union[None, Unset, str]): Presigned PUT URL in synchronous mode.
        async_job (Union[Unset, bool]): Schedule the job and stage the result under jobs/. Default: False.
        webhook_url (Union[None, Unset, str]): Callback URL for asynchronous completion.
        threshold (Union[Unset, float]):  Default: 10.0.
        artifacts (Union[Unset, VideoScenesRequestArtifacts]):  Default: VideoScenesRequestArtifacts.NONE.
        max_scenes (Union[Unset, int]):  Default: 50.
    """

    file_path: Union[None, Unset, str] = UNSET
    file_url: Union[None, Unset, str] = UNSET
    output_path: Union[None, Unset, str] = UNSET
    output_url: Union[None, Unset, str] = UNSET
    async_job: Union[Unset, bool] = False
    webhook_url: Union[None, Unset, str] = UNSET
    threshold: Union[Unset, float] = 10.0
    artifacts: Union[Unset, VideoScenesRequestArtifacts] = VideoScenesRequestArtifacts.NONE
    max_scenes: Union[Unset, int] = 50
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        file_path: Union[None, Unset, str]
        if isinstance(self.file_path, Unset):
            file_path = UNSET
        else:
            file_path = self.file_path

        file_url: Union[None, Unset, str]
        if isinstance(self.file_url, Unset):
            file_url = UNSET
        else:
            file_url = self.file_url

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

        threshold = self.threshold

        artifacts: Union[Unset, str] = UNSET
        if not isinstance(self.artifacts, Unset):
            artifacts = self.artifacts.value

        max_scenes = self.max_scenes

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if file_path is not UNSET:
            field_dict["file_path"] = file_path
        if file_url is not UNSET:
            field_dict["file_url"] = file_url
        if output_path is not UNSET:
            field_dict["output_path"] = output_path
        if output_url is not UNSET:
            field_dict["output_url"] = output_url
        if async_job is not UNSET:
            field_dict["async_job"] = async_job
        if webhook_url is not UNSET:
            field_dict["webhook_url"] = webhook_url
        if threshold is not UNSET:
            field_dict["threshold"] = threshold
        if artifacts is not UNSET:
            field_dict["artifacts"] = artifacts
        if max_scenes is not UNSET:
            field_dict["max_scenes"] = max_scenes

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_file_path(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        file_path = _parse_file_path(d.pop("file_path", UNSET))

        def _parse_file_url(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        file_url = _parse_file_url(d.pop("file_url", UNSET))

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

        threshold = d.pop("threshold", UNSET)

        _artifacts = d.pop("artifacts", UNSET)
        artifacts: Union[Unset, VideoScenesRequestArtifacts]
        if isinstance(_artifacts, Unset):
            artifacts = UNSET
        else:
            artifacts = VideoScenesRequestArtifacts(_artifacts)

        max_scenes = d.pop("max_scenes", UNSET)

        video_scenes_request = cls(
            file_path=file_path,
            file_url=file_url,
            output_path=output_path,
            output_url=output_url,
            async_job=async_job,
            webhook_url=webhook_url,
            threshold=threshold,
            artifacts=artifacts,
            max_scenes=max_scenes,
        )

        video_scenes_request.additional_properties = d
        return video_scenes_request

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
