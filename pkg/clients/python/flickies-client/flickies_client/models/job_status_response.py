from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.job_status_response_status import JobStatusResponseStatus
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.job_status_response_error_type_0 import JobStatusResponseErrorType0
    from ..models.job_status_response_result_type_0 import JobStatusResponseResultType0


T = TypeVar("T", bound="JobStatusResponse")


@_attrs_define
class JobStatusResponse:
    """
    Attributes:
        job_id (UUID):
        status (JobStatusResponseStatus):
        result (JobStatusResponseResultType0 | None | Unset):
        error (JobStatusResponseErrorType0 | None | Unset):
    """

    job_id: UUID
    status: JobStatusResponseStatus
    result: JobStatusResponseResultType0 | None | Unset = UNSET
    error: JobStatusResponseErrorType0 | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.job_status_response_error_type_0 import JobStatusResponseErrorType0
        from ..models.job_status_response_result_type_0 import JobStatusResponseResultType0

        job_id = str(self.job_id)

        status = self.status.value

        result: dict[str, Any] | None | Unset
        if isinstance(self.result, Unset):
            result = UNSET
        elif isinstance(self.result, JobStatusResponseResultType0):
            result = self.result.to_dict()
        else:
            result = self.result

        error: dict[str, Any] | None | Unset
        if isinstance(self.error, Unset):
            error = UNSET
        elif isinstance(self.error, JobStatusResponseErrorType0):
            error = self.error.to_dict()
        else:
            error = self.error

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "job_id": job_id,
                "status": status,
            }
        )
        if result is not UNSET:
            field_dict["result"] = result
        if error is not UNSET:
            field_dict["error"] = error

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.job_status_response_error_type_0 import JobStatusResponseErrorType0
        from ..models.job_status_response_result_type_0 import JobStatusResponseResultType0

        d = dict(src_dict)
        job_id = UUID(d.pop("job_id"))

        status = JobStatusResponseStatus(d.pop("status"))

        def _parse_result(data: object) -> JobStatusResponseResultType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                result_type_0 = JobStatusResponseResultType0.from_dict(data)

                return result_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(JobStatusResponseResultType0 | None | Unset, data)

        result = _parse_result(d.pop("result", UNSET))

        def _parse_error(data: object) -> JobStatusResponseErrorType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                error_type_0 = JobStatusResponseErrorType0.from_dict(data)

                return error_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(JobStatusResponseErrorType0 | None | Unset, data)

        error = _parse_error(d.pop("error", UNSET))

        job_status_response = cls(
            job_id=job_id,
            status=status,
            result=result,
            error=error,
        )

        job_status_response.additional_properties = d
        return job_status_response

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
