from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.base_video_input_request import BaseVideoInputRequest
from ...models.error_body import ErrorBody
from ...models.video_info_response import VideoInfoResponse
from ...types import Response


def _get_kwargs(
    *,
    body: BaseVideoInputRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/video/info",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorBody | VideoInfoResponse | None:
    if response.status_code == 200:
        response_200 = VideoInfoResponse.from_dict(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = ErrorBody.from_dict(response.json())

        return response_400

    if response.status_code == 401:
        response_401 = ErrorBody.from_dict(response.json())

        return response_401

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorBody | VideoInfoResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: BaseVideoInputRequest,
) -> Response[ErrorBody | VideoInfoResponse]:
    """All metadata for a video — duration, codecs, fps, dimensions, bitrate.

    Args:
        body (BaseVideoInputRequest): Exactly one of file_path / file_url MUST be provided.
            Enforced at handler boundary.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorBody | VideoInfoResponse]
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
    client: AuthenticatedClient | Client,
    body: BaseVideoInputRequest,
) -> ErrorBody | VideoInfoResponse | None:
    """All metadata for a video — duration, codecs, fps, dimensions, bitrate.

    Args:
        body (BaseVideoInputRequest): Exactly one of file_path / file_url MUST be provided.
            Enforced at handler boundary.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorBody | VideoInfoResponse
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: BaseVideoInputRequest,
) -> Response[ErrorBody | VideoInfoResponse]:
    """All metadata for a video — duration, codecs, fps, dimensions, bitrate.

    Args:
        body (BaseVideoInputRequest): Exactly one of file_path / file_url MUST be provided.
            Enforced at handler boundary.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorBody | VideoInfoResponse]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: BaseVideoInputRequest,
) -> ErrorBody | VideoInfoResponse | None:
    """All metadata for a video — duration, codecs, fps, dimensions, bitrate.

    Args:
        body (BaseVideoInputRequest): Exactly one of file_path / file_url MUST be provided.
            Enforced at handler boundary.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorBody | VideoInfoResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
