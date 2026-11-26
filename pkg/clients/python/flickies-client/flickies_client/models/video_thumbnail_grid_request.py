from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.video_thumbnail_grid_request_layout import VideoThumbnailGridRequestLayout
from ..types import UNSET, Unset

T = TypeVar("T", bound="VideoThumbnailGridRequest")


@_attrs_define
class VideoThumbnailGridRequest:
    """
    Attributes:
        rows (int):
        cols (int):
        file_path (Union[None, Unset, str]): Staged input path. Provide exactly one input.
        file_url (Union[None, Unset, str]): HTTP(S) input URL.
        output_path (Union[None, Unset, str]): Staged output path in synchronous mode.
        output_url (Union[None, Unset, str]): Presigned PUT URL in synchronous mode.
        async_job (Union[Unset, bool]): Schedule the job and stage the result under jobs/. Default: False.
        webhook_url (Union[None, Unset, str]): Callback URL for asynchronous completion.
        timestamps (Union[Unset, bool]):  Default: False.
        layout (Union[Unset, VideoThumbnailGridRequestLayout]):  Default: VideoThumbnailGridRequestLayout.TIGHT.
        cell_width (Union[Unset, int]):  Default: 320.
        cell_height (Union[Unset, int]):  Default: 180.
    """

    rows: int
    cols: int
    file_path: Union[None, Unset, str] = UNSET
    file_url: Union[None, Unset, str] = UNSET
    output_path: Union[None, Unset, str] = UNSET
    output_url: Union[None, Unset, str] = UNSET
    async_job: Union[Unset, bool] = False
    webhook_url: Union[None, Unset, str] = UNSET
    timestamps: Union[Unset, bool] = False
    layout: Union[Unset, VideoThumbnailGridRequestLayout] = VideoThumbnailGridRequestLayout.TIGHT
    cell_width: Union[Unset, int] = 320
    cell_height: Union[Unset, int] = 180
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        rows = self.rows

        cols = self.cols

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

        timestamps = self.timestamps

        layout: Union[Unset, str] = UNSET
        if not isinstance(self.layout, Unset):
            layout = self.layout.value

        cell_width = self.cell_width

        cell_height = self.cell_height

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "rows": rows,
                "cols": cols,
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
        if timestamps is not UNSET:
            field_dict["timestamps"] = timestamps
        if layout is not UNSET:
            field_dict["layout"] = layout
        if cell_width is not UNSET:
            field_dict["cell_width"] = cell_width
        if cell_height is not UNSET:
            field_dict["cell_height"] = cell_height

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        rows = d.pop("rows")

        cols = d.pop("cols")

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

        timestamps = d.pop("timestamps", UNSET)

        _layout = d.pop("layout", UNSET)
        layout: Union[Unset, VideoThumbnailGridRequestLayout]
        if isinstance(_layout, Unset):
            layout = UNSET
        else:
            layout = VideoThumbnailGridRequestLayout(_layout)

        cell_width = d.pop("cell_width", UNSET)

        cell_height = d.pop("cell_height", UNSET)

        video_thumbnail_grid_request = cls(
            rows=rows,
            cols=cols,
            file_path=file_path,
            file_url=file_url,
            output_path=output_path,
            output_url=output_url,
            async_job=async_job,
            webhook_url=webhook_url,
            timestamps=timestamps,
            layout=layout,
            cell_width=cell_width,
            cell_height=cell_height,
        )

        video_thumbnail_grid_request.additional_properties = d
        return video_thumbnail_grid_request

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
