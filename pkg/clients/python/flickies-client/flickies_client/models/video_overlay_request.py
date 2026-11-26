from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="VideoOverlayRequest")


@_attrs_define
class VideoOverlayRequest:
    """Draw a staged image (PNG, JPEG or WebP) or a text label during the specified interval.

    Attributes:
        end_sec (float): End time in seconds from the start of the source.
        file_path (Union[None, Unset, str]): Staged input path. Provide exactly one input.
        file_url (Union[None, Unset, str]): HTTP(S) input URL.
        output_path (Union[None, Unset, str]): Staged output path in synchronous mode.
        output_url (Union[None, Unset, str]): Presigned PUT URL in synchronous mode.
        async_job (Union[Unset, bool]): Schedule the job and stage the result under jobs/. Default: False.
        webhook_url (Union[None, Unset, str]): Callback URL for asynchronous completion.
        image_path (Union[None, Unset, str]): Staged image path. Supply exactly one of image_path and text.
        text (Union[None, Unset, str]): Text to render into the video.
        start_sec (Union[Unset, float]): Start time in seconds from the start of the source. Default: 0.0.
        x (Union[Unset, int]): Horizontal pixel offset measured from the left edge. Default: 24.
        y (Union[Unset, int]): Vertical pixel offset measured from the top edge. Default: 24.
    """

    end_sec: float
    file_path: Union[None, Unset, str] = UNSET
    file_url: Union[None, Unset, str] = UNSET
    output_path: Union[None, Unset, str] = UNSET
    output_url: Union[None, Unset, str] = UNSET
    async_job: Union[Unset, bool] = False
    webhook_url: Union[None, Unset, str] = UNSET
    image_path: Union[None, Unset, str] = UNSET
    text: Union[None, Unset, str] = UNSET
    start_sec: Union[Unset, float] = 0.0
    x: Union[Unset, int] = 24
    y: Union[Unset, int] = 24
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        end_sec = self.end_sec

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

        image_path: Union[None, Unset, str]
        if isinstance(self.image_path, Unset):
            image_path = UNSET
        else:
            image_path = self.image_path

        text: Union[None, Unset, str]
        if isinstance(self.text, Unset):
            text = UNSET
        else:
            text = self.text

        start_sec = self.start_sec

        x = self.x

        y = self.y

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "end_sec": end_sec,
            }
        )
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
        if image_path is not UNSET:
            field_dict["image_path"] = image_path
        if text is not UNSET:
            field_dict["text"] = text
        if start_sec is not UNSET:
            field_dict["start_sec"] = start_sec
        if x is not UNSET:
            field_dict["x"] = x
        if y is not UNSET:
            field_dict["y"] = y

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        end_sec = d.pop("end_sec")

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

        def _parse_image_path(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        image_path = _parse_image_path(d.pop("image_path", UNSET))

        def _parse_text(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        text = _parse_text(d.pop("text", UNSET))

        start_sec = d.pop("start_sec", UNSET)

        x = d.pop("x", UNSET)

        y = d.pop("y", UNSET)

        video_overlay_request = cls(
            end_sec=end_sec,
            file_path=file_path,
            file_url=file_url,
            output_path=output_path,
            output_url=output_url,
            async_job=async_job,
            webhook_url=webhook_url,
            image_path=image_path,
            text=text,
            start_sec=start_sec,
            x=x,
            y=y,
        )

        video_overlay_request.additional_properties = d
        return video_overlay_request

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
