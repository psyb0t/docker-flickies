from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.video_subtitles_request_mode import VideoSubtitlesRequestMode
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.timed_word import TimedWord


T = TypeVar("T", bound="VideoSubtitlesRequest")


@_attrs_define
class VideoSubtitlesRequest:
    """Burn in an SRT or ASS file, embed a selectable track, or build karaoke captions from word timestamps.

    Attributes:
        file_path (Union[None, Unset, str]): Staged input path. Provide exactly one input.
        file_url (Union[None, Unset, str]): HTTP(S) input URL.
        output_path (Union[None, Unset, str]): Staged output path in synchronous mode.
        output_url (Union[None, Unset, str]): Presigned PUT URL in synchronous mode.
        async_job (Union[Unset, bool]): Schedule the job and stage the result under jobs/. Default: False.
        webhook_url (Union[None, Unset, str]): Callback URL for asynchronous completion.
        subtitle_path (Union[None, Unset, str]): Staged SRT or ASS path. Supply exactly one of subtitle_path and words.
        words (Union[None, Unset, list['TimedWord']]): Words and timestamps used to generate karaoke captions.
        mode (Union[Unset, VideoSubtitlesRequestMode]): Burn captions into the image or embed them as a selectable
            subtitle track. Default: VideoSubtitlesRequestMode.BURN.
        words_per_line (Union[Unset, int]): Maximum number of words grouped into each karaoke line. Default: 4.
        font_size (Union[Unset, int]): Font size for generated karaoke captions. Default: 56.
    """

    file_path: Union[None, Unset, str] = UNSET
    file_url: Union[None, Unset, str] = UNSET
    output_path: Union[None, Unset, str] = UNSET
    output_url: Union[None, Unset, str] = UNSET
    async_job: Union[Unset, bool] = False
    webhook_url: Union[None, Unset, str] = UNSET
    subtitle_path: Union[None, Unset, str] = UNSET
    words: Union[None, Unset, list["TimedWord"]] = UNSET
    mode: Union[Unset, VideoSubtitlesRequestMode] = VideoSubtitlesRequestMode.BURN
    words_per_line: Union[Unset, int] = 4
    font_size: Union[Unset, int] = 56
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

        subtitle_path: Union[None, Unset, str]
        if isinstance(self.subtitle_path, Unset):
            subtitle_path = UNSET
        else:
            subtitle_path = self.subtitle_path

        words: Union[None, Unset, list[dict[str, Any]]]
        if isinstance(self.words, Unset):
            words = UNSET
        elif isinstance(self.words, list):
            words = []
            for words_type_0_item_data in self.words:
                words_type_0_item = words_type_0_item_data.to_dict()
                words.append(words_type_0_item)

        else:
            words = self.words

        mode: Union[Unset, str] = UNSET
        if not isinstance(self.mode, Unset):
            mode = self.mode.value

        words_per_line = self.words_per_line

        font_size = self.font_size

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
        if subtitle_path is not UNSET:
            field_dict["subtitle_path"] = subtitle_path
        if words is not UNSET:
            field_dict["words"] = words
        if mode is not UNSET:
            field_dict["mode"] = mode
        if words_per_line is not UNSET:
            field_dict["words_per_line"] = words_per_line
        if font_size is not UNSET:
            field_dict["font_size"] = font_size

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.timed_word import TimedWord

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

        def _parse_subtitle_path(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        subtitle_path = _parse_subtitle_path(d.pop("subtitle_path", UNSET))

        def _parse_words(data: object) -> Union[None, Unset, list["TimedWord"]]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                words_type_0 = []
                _words_type_0 = data
                for words_type_0_item_data in _words_type_0:
                    words_type_0_item = TimedWord.from_dict(words_type_0_item_data)

                    words_type_0.append(words_type_0_item)

                return words_type_0
            except:  # noqa: E722
                pass
            return cast(Union[None, Unset, list["TimedWord"]], data)

        words = _parse_words(d.pop("words", UNSET))

        _mode = d.pop("mode", UNSET)
        mode: Union[Unset, VideoSubtitlesRequestMode]
        if isinstance(_mode, Unset):
            mode = UNSET
        else:
            mode = VideoSubtitlesRequestMode(_mode)

        words_per_line = d.pop("words_per_line", UNSET)

        font_size = d.pop("font_size", UNSET)

        video_subtitles_request = cls(
            file_path=file_path,
            file_url=file_url,
            output_path=output_path,
            output_url=output_url,
            async_job=async_job,
            webhook_url=webhook_url,
            subtitle_path=subtitle_path,
            words=words,
            mode=mode,
            words_per_line=words_per_line,
            font_size=font_size,
        )

        video_subtitles_request.additional_properties = d
        return video_subtitles_request

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
