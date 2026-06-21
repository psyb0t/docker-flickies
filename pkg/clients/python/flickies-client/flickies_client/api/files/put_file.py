from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_body import ErrorBody
from ...models.staged_output_response import StagedOutputResponse
from ...types import File, Response


def _get_kwargs(
    path: str,
    *,
    body: File,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "put",
        "url": "/v1/files/{path}".format(
            path=quote(str(path), safe=""),
        ),
    }

    _kwargs["content"] = body.payload
    headers["Content-Type"] = "application/octet-stream"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorBody | StagedOutputResponse | None:
    if response.status_code == 201:
        response_201 = StagedOutputResponse.from_dict(response.json())

        return response_201

    if response.status_code == 401:
        response_401 = ErrorBody.from_dict(response.json())

        return response_401

    if response.status_code == 413:
        response_413 = ErrorBody.from_dict(response.json())

        return response_413

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorBody | StagedOutputResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    path: str,
    *,
    client: AuthenticatedClient | Client,
    body: File,
) -> Response[ErrorBody | StagedOutputResponse]:
    """Upload a video/audio file to the local staging area.

    Args:
        path (str):
        body (File):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorBody | StagedOutputResponse]
    """

    kwargs = _get_kwargs(
        path=path,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    path: str,
    *,
    client: AuthenticatedClient | Client,
    body: File,
) -> ErrorBody | StagedOutputResponse | None:
    """Upload a video/audio file to the local staging area.

    Args:
        path (str):
        body (File):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorBody | StagedOutputResponse
    """

    return sync_detailed(
        path=path,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    path: str,
    *,
    client: AuthenticatedClient | Client,
    body: File,
) -> Response[ErrorBody | StagedOutputResponse]:
    """Upload a video/audio file to the local staging area.

    Args:
        path (str):
        body (File):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorBody | StagedOutputResponse]
    """

    kwargs = _get_kwargs(
        path=path,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    path: str,
    *,
    client: AuthenticatedClient | Client,
    body: File,
) -> ErrorBody | StagedOutputResponse | None:
    """Upload a video/audio file to the local staging area.

    Args:
        path (str):
        body (File):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorBody | StagedOutputResponse
    """

    return (
        await asyncio_detailed(
            path=path,
            client=client,
            body=body,
        )
    ).parsed
