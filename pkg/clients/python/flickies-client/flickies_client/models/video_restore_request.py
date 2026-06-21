from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.base_video_output_request_output_format import BaseVideoOutputRequestOutputFormat
from ..models.video_restore_request_engine import VideoRestoreRequestEngine
from ..types import UNSET, Unset

T = TypeVar("T", bound="VideoRestoreRequest")


@_attrs_define
class VideoRestoreRequest:
    """
    Attributes:
        file_path (None | str | Unset): FILES_DIR-relative path of an already-uploaded video.
        file_url (None | str | Unset): HTTP(S) URL the server fetches.
        output_path (None | str | Unset):
        output_url (None | str | Unset):
        async_job (bool | Unset):  Default: False.
        webhook_url (None | str | Unset): Notify URL on async completion (HMAC-signed).
        output_format (BaseVideoOutputRequestOutputFormat | Unset):  Default: BaseVideoOutputRequestOutputFormat.MP4.
        engine (VideoRestoreRequestEngine | Unset):  Default: VideoRestoreRequestEngine.GFPGAN.
    """

    file_path: None | str | Unset = UNSET
    file_url: None | str | Unset = UNSET
    output_path: None | str | Unset = UNSET
    output_url: None | str | Unset = UNSET
    async_job: bool | Unset = False
    webhook_url: None | str | Unset = UNSET
    output_format: BaseVideoOutputRequestOutputFormat | Unset = BaseVideoOutputRequestOutputFormat.MP4
    engine: VideoRestoreRequestEngine | Unset = VideoRestoreRequestEngine.GFPGAN
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        file_path: None | str | Unset
        if isinstance(self.file_path, Unset):
            file_path = UNSET
        else:
            file_path = self.file_path

        file_url: None | str | Unset
        if isinstance(self.file_url, Unset):
            file_url = UNSET
        else:
            file_url = self.file_url

        output_path: None | str | Unset
        if isinstance(self.output_path, Unset):
            output_path = UNSET
        else:
            output_path = self.output_path

        output_url: None | str | Unset
        if isinstance(self.output_url, Unset):
            output_url = UNSET
        else:
            output_url = self.output_url

        async_job = self.async_job

        webhook_url: None | str | Unset
        if isinstance(self.webhook_url, Unset):
            webhook_url = UNSET
        else:
            webhook_url = self.webhook_url

        output_format: str | Unset = UNSET
        if not isinstance(self.output_format, Unset):
            output_format = self.output_format.value

        engine: str | Unset = UNSET
        if not isinstance(self.engine, Unset):
            engine = self.engine.value

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
        if output_format is not UNSET:
            field_dict["output_format"] = output_format
        if engine is not UNSET:
            field_dict["engine"] = engine

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_file_path(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        file_path = _parse_file_path(d.pop("file_path", UNSET))

        def _parse_file_url(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        file_url = _parse_file_url(d.pop("file_url", UNSET))

        def _parse_output_path(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        output_path = _parse_output_path(d.pop("output_path", UNSET))

        def _parse_output_url(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        output_url = _parse_output_url(d.pop("output_url", UNSET))

        async_job = d.pop("async_job", UNSET)

        def _parse_webhook_url(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        webhook_url = _parse_webhook_url(d.pop("webhook_url", UNSET))

        _output_format = d.pop("output_format", UNSET)
        output_format: BaseVideoOutputRequestOutputFormat | Unset
        if isinstance(_output_format, Unset):
            output_format = UNSET
        else:
            output_format = BaseVideoOutputRequestOutputFormat(_output_format)

        _engine = d.pop("engine", UNSET)
        engine: VideoRestoreRequestEngine | Unset
        if isinstance(_engine, Unset):
            engine = UNSET
        else:
            engine = VideoRestoreRequestEngine(_engine)

        video_restore_request = cls(
            file_path=file_path,
            file_url=file_url,
            output_path=output_path,
            output_url=output_url,
            async_job=async_job,
            webhook_url=webhook_url,
            output_format=output_format,
            engine=engine,
        )

        video_restore_request.additional_properties = d
        return video_restore_request

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
