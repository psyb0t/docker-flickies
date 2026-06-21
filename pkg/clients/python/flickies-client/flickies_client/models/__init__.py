"""Contains all the data models used in inputs/outputs"""

from .base_video_input_request import BaseVideoInputRequest
from .base_video_output_request import BaseVideoOutputRequest
from .base_video_output_request_output_format import BaseVideoOutputRequestOutputFormat
from .engine_info import EngineInfo
from .engine_list import EngineList
from .error_body import ErrorBody
from .error_body_details import ErrorBodyDetails
from .health_response import HealthResponse
from .job_accepted_response import JobAcceptedResponse
from .job_status_response import JobStatusResponse
from .job_status_response_error_type_0 import JobStatusResponseErrorType0
from .job_status_response_result_type_0 import JobStatusResponseResultType0
from .job_status_response_status import JobStatusResponseStatus
from .staged_output_response import StagedOutputResponse
from .url_output_response import UrlOutputResponse
from .video_info_response import VideoInfoResponse
from .video_restore_request import VideoRestoreRequest
from .video_restore_request_engine import VideoRestoreRequestEngine
from .video_scale_request import VideoScaleRequest
from .video_transcode_request import VideoTranscodeRequest
from .video_transcode_request_gif_options_type_0 import VideoTranscodeRequestGifOptionsType0
from .video_transcode_request_gif_options_type_0_palette_mode import VideoTranscodeRequestGifOptionsType0PaletteMode
from .video_trim_request import VideoTrimRequest

__all__ = (
    "BaseVideoInputRequest",
    "BaseVideoOutputRequest",
    "BaseVideoOutputRequestOutputFormat",
    "EngineInfo",
    "EngineList",
    "ErrorBody",
    "ErrorBodyDetails",
    "HealthResponse",
    "JobAcceptedResponse",
    "JobStatusResponse",
    "JobStatusResponseErrorType0",
    "JobStatusResponseResultType0",
    "JobStatusResponseStatus",
    "StagedOutputResponse",
    "UrlOutputResponse",
    "VideoInfoResponse",
    "VideoRestoreRequest",
    "VideoRestoreRequestEngine",
    "VideoScaleRequest",
    "VideoTranscodeRequest",
    "VideoTranscodeRequestGifOptionsType0",
    "VideoTranscodeRequestGifOptionsType0PaletteMode",
    "VideoTrimRequest",
)
