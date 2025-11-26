"""Defines the session object for gRPC tool calls."""

import asyncio
import logging
from typing import Any

from pydantic import AnyUrl

import mcp.types as types
from mcp.proto import mcp_pb2
from mcp.server.transport_session import TransportSession

logger = logging.getLogger(__name__)

class GrpcSession(TransportSession):
    """A session object for gRPC tool calls that uses a queue."""

    def __init__(self, response_queue: asyncio.Queue):
        self._response_queue = response_queue

    async def send_log_message(self, level, data, **kwargs):
        """Logs tool messages to the server console."""
        raise NotImplementedError

    async def send_resource_updated(self, uri: AnyUrl) -> None:
        """Send a resource updated notification."""
        raise NotImplementedError

    async def list_roots(self) -> types.ListRootsResult:
        """Send a roots/list request."""
        raise NotImplementedError

    async def elicit(
        self,
        message: str,
        requestedSchema: types.ElicitRequestedSchema,
        related_request_id: types.RequestId | None = None,
    ) -> types.ElicitResult:
        """Send an elicitation/create request."""
        raise NotImplementedError

    async def send_ping(self) -> types.EmptyResult:
        """This is not needed for gRPC."""
        raise NotImplementedError

    async def send_progress_notification(
        self, progress_token, progress, total, message,
        related_request_id: types.RequestId | None = None,
    ):
        """Puts a progress notification onto the response queue."""
        progress_proto = mcp_pb2.ProgressNotification(
            progress_token=str(progress_token),
            progress=progress,
        )
        if total is not None:
            progress_proto.total = total
        if message is not None:
            progress_proto.message = message

        response = mcp_pb2.CallToolResponse(
            common=mcp_pb2.ResponseFields(progress=progress_proto)
        )
        await self._response_queue.put(response)

    async def send_resource_list_changed(self) -> None:
        """This is not needed for gRPC, as we rely on TTL."""
        raise NotImplementedError

    async def send_tool_list_changed(self) -> None:
        """This is not needed for gRPC, as we rely on TTL."""
        raise NotImplementedError

    async def send_prompt_list_changed(self) -> None:
        """This is not needed for gRPC, as we rely on TTL."""
        raise NotImplementedError