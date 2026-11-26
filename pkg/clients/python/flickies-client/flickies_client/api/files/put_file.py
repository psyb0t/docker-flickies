from http import HTTPStatus
from typing import Any, Optional, Union

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
        "url": f"/v1/files/{path}",
    }

    _kwargs["content"] = body.payload

    headers["Content-Type"] = "application/octet-stream"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[Union[ErrorBody, StagedOutputResponse]]:
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
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Response[Union[ErrorBody, StagedOutputResponse]]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    path: str,
    *,
    client: Union[AuthenticatedClient, Client],
    body: File,
) -> Response[Union[ErrorBody, StagedOutputResponse]]:
    """Upload a video/audio file to the local staging area.

    Args:
        path (str):
        body (File):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Union[ErrorBody, StagedOutputResponse]]
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
    client: Union[AuthenticatedClient, Client],
    body: File,
) -> Optional[Union[ErrorBody, StagedOutputResponse]]:
    """Upload a video/audio file to the local staging area.

    Args:
        path (str):
        body (File):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Union[ErrorBody, StagedOutputResponse]
    """

    return sync_detailed(
        path=path,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    path: str,
    *,
    client: Union[AuthenticatedClient, Client],
    body: File,
) -> Response[Union[ErrorBody, StagedOutputResponse]]:
    """Upload a video/audio file to the local staging area.

    Args:
        path (str):
        body (File):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Union[ErrorBody, StagedOutputResponse]]
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
    client: Union[AuthenticatedClient, Client],
    body: File,
) -> Optional[Union[ErrorBody, StagedOutputResponse]]:
    """Upload a video/audio file to the local staging area.

    Args:
        path (str):
        body (File):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Union[ErrorBody, StagedOutputResponse]
    """

    return (
        await asyncio_detailed(
            path=path,
            client=client,
            body=body,
        )
    ).parsed
