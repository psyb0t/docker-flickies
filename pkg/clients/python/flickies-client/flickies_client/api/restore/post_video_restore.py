from http import HTTPStatus
from typing import Any, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_body import ErrorBody
from ...models.job_accepted_response import JobAcceptedResponse
from ...models.staged_output_response import StagedOutputResponse
from ...models.url_output_response import UrlOutputResponse
from ...models.video_restore_request import VideoRestoreRequest
from ...types import Response


def _get_kwargs(
    *,
    body: VideoRestoreRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/video/restore",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[Union[ErrorBody, JobAcceptedResponse, Union["StagedOutputResponse", "UrlOutputResponse"]]]:
    if response.status_code == 200:

        def _parse_response_200(data: object) -> Union["StagedOutputResponse", "UrlOutputResponse"]:
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                response_200_type_0 = StagedOutputResponse.from_dict(data)

                return response_200_type_0
            except:  # noqa: E722
                pass
            if not isinstance(data, dict):
                raise TypeError()
            response_200_type_1 = UrlOutputResponse.from_dict(data)

            return response_200_type_1

        response_200 = _parse_response_200(response.json())

        return response_200
    if response.status_code == 202:
        response_202 = JobAcceptedResponse.from_dict(response.json())

        return response_202
    if response.status_code == 400:
        response_400 = ErrorBody.from_dict(response.json())

        return response_400
    if response.status_code == 401:
        response_401 = ErrorBody.from_dict(response.json())

        return response_401
    if response.status_code == 422:
        response_422 = ErrorBody.from_dict(response.json())

        return response_422
    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Response[Union[ErrorBody, JobAcceptedResponse, Union["StagedOutputResponse", "UrlOutputResponse"]]]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: Union[AuthenticatedClient, Client],
    body: VideoRestoreRequest,
) -> Response[Union[ErrorBody, JobAcceptedResponse, Union["StagedOutputResponse", "UrlOutputResponse"]]]:
    """
    Args:
        body (VideoRestoreRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Union[ErrorBody, JobAcceptedResponse, Union['StagedOutputResponse', 'UrlOutputResponse']]]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: Union[AuthenticatedClient, Client],
    body: VideoRestoreRequest,
) -> Optional[Union[ErrorBody, JobAcceptedResponse, Union["StagedOutputResponse", "UrlOutputResponse"]]]:
    """
    Args:
        body (VideoRestoreRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Union[ErrorBody, JobAcceptedResponse, Union['StagedOutputResponse', 'UrlOutputResponse']]
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: Union[AuthenticatedClient, Client],
    body: VideoRestoreRequest,
) -> Response[Union[ErrorBody, JobAcceptedResponse, Union["StagedOutputResponse", "UrlOutputResponse"]]]:
    """
    Args:
        body (VideoRestoreRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Union[ErrorBody, JobAcceptedResponse, Union['StagedOutputResponse', 'UrlOutputResponse']]]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: Union[AuthenticatedClient, Client],
    body: VideoRestoreRequest,
) -> Optional[Union[ErrorBody, JobAcceptedResponse, Union["StagedOutputResponse", "UrlOutputResponse"]]]:
    """
    Args:
        body (VideoRestoreRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Union[ErrorBody, JobAcceptedResponse, Union['StagedOutputResponse', 'UrlOutputResponse']]
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
