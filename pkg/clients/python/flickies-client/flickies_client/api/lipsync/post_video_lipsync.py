from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.base_video_output_request import BaseVideoOutputRequest
from ...models.error_body import ErrorBody
from ...models.job_accepted_response import JobAcceptedResponse
from ...models.staged_output_response import StagedOutputResponse
from ...models.url_output_response import UrlOutputResponse
from ...types import Response


def _get_kwargs(
    *,
    body: BaseVideoOutputRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/video/lipsync",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorBody | JobAcceptedResponse | StagedOutputResponse | UrlOutputResponse | None:
    if response.status_code == 200:

        def _parse_response_200(data: object) -> StagedOutputResponse | UrlOutputResponse:
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                response_200_type_0 = StagedOutputResponse.from_dict(data)

                return response_200_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
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

    if response.status_code == 403:
        response_403 = ErrorBody.from_dict(response.json())

        return response_403

    if response.status_code == 422:
        response_422 = ErrorBody.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorBody | JobAcceptedResponse | StagedOutputResponse | UrlOutputResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: BaseVideoOutputRequest,
) -> Response[ErrorBody | JobAcceptedResponse | StagedOutputResponse | UrlOutputResponse]:
    """Drive a face from an audio track.

    Args:
        body (BaseVideoOutputRequest): Exactly one of output_path / output_url required in sync
            mode; both optional in async mode (auto-staged).

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorBody | JobAcceptedResponse | StagedOutputResponse | UrlOutputResponse]
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
    body: BaseVideoOutputRequest,
) -> ErrorBody | JobAcceptedResponse | StagedOutputResponse | UrlOutputResponse | None:
    """Drive a face from an audio track.

    Args:
        body (BaseVideoOutputRequest): Exactly one of output_path / output_url required in sync
            mode; both optional in async mode (auto-staged).

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorBody | JobAcceptedResponse | StagedOutputResponse | UrlOutputResponse
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: BaseVideoOutputRequest,
) -> Response[ErrorBody | JobAcceptedResponse | StagedOutputResponse | UrlOutputResponse]:
    """Drive a face from an audio track.

    Args:
        body (BaseVideoOutputRequest): Exactly one of output_path / output_url required in sync
            mode; both optional in async mode (auto-staged).

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorBody | JobAcceptedResponse | StagedOutputResponse | UrlOutputResponse]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: BaseVideoOutputRequest,
) -> ErrorBody | JobAcceptedResponse | StagedOutputResponse | UrlOutputResponse | None:
    """Drive a face from an audio track.

    Args:
        body (BaseVideoOutputRequest): Exactly one of output_path / output_url required in sync
            mode; both optional in async mode (auto-staged).

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorBody | JobAcceptedResponse | StagedOutputResponse | UrlOutputResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
