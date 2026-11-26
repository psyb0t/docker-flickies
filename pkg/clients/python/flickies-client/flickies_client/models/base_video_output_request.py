from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.base_video_output_request_output_format import BaseVideoOutputRequestOutputFormat
from ..types import UNSET, Unset

T = TypeVar("T", bound="BaseVideoOutputRequest")


@_attrs_define
class BaseVideoOutputRequest:
    """Exactly one of output_path / output_url required in sync mode; both optional in async mode (auto-staged).

    Attributes:
        output_path (Union[None, Unset, str]): Relative staging path where the server should write the result.
        output_url (Union[None, Unset, str]): HTTP(S) URL that accepts a PUT of the result.
        async_job (Union[Unset, bool]): Schedule work in the background and return a job ID. Use the job result's path
            to retrieve the output. Default: False.
        webhook_url (Union[None, Unset, str]): Notify URL on async completion (HMAC-signed).
        output_format (Union[Unset, BaseVideoOutputRequestOutputFormat]): Container format for the output video.
            Default: BaseVideoOutputRequestOutputFormat.MP4.
    """

    output_path: Union[None, Unset, str] = UNSET
    output_url: Union[None, Unset, str] = UNSET
    async_job: Union[Unset, bool] = False
    webhook_url: Union[None, Unset, str] = UNSET
    output_format: Union[Unset, BaseVideoOutputRequestOutputFormat] = BaseVideoOutputRequestOutputFormat.MP4
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

        output_format: Union[Unset, str] = UNSET
        if not isinstance(self.output_format, Unset):
            output_format = self.output_format.value

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
        if output_format is not UNSET:
            field_dict["output_format"] = output_format

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
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

        _output_format = d.pop("output_format", UNSET)
        output_format: Union[Unset, BaseVideoOutputRequestOutputFormat]
        if isinstance(_output_format, Unset):
            output_format = UNSET
        else:
            output_format = BaseVideoOutputRequestOutputFormat(_output_format)

        base_video_output_request = cls(
            output_path=output_path,
            output_url=output_url,
            async_job=async_job,
            webhook_url=webhook_url,
            output_format=output_format,
        )

        base_video_output_request.additional_properties = d
        return base_video_output_request

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
