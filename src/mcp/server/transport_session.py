"""Abstract base class for transport sessions."""

import abc
from typing import Any

from pydantic import AnyUrl

import mcp.types as types


class TransportSession(abc.ABC):
    """Abstract base class for transport sessions.
    This abstract class needs to be implemented by all transport sessions on the server side.
    These APIs are exposed via the context object to the FastMCP server author.
    This is needed to send message from server to client via FastMCP context.
    The classes which inherit this abstract class are:
    1. ServerSession (for FastMCP server)
    2. GRPCSession (for gRPC server)

    They are embedded in the RequestContext class which is embedded in the
    mcp.server.lowlevel.server.py (lowlevel server) and
    mcp.server.grpc.py (gRPC server)

    """

    @abc.abstractmethod
    async def send_log_message(
        self,
        level: types.LoggingLevel,
        data: Any,
        logger: str | None = None,
        related_request_id: types.RequestId | None = None,
    ) -> None:
        """Send a log message notification."""
        raise NotImplementedError

    @abc.abstractmethod
    async def send_resource_updated(self, uri: AnyUrl) -> None:
        """Send a resource updated notification."""
        raise NotImplementedError

    @abc.abstractmethod
    async def list_roots(self) -> types.ListRootsResult:
        """Send a roots/list request."""
        raise NotImplementedError

    @abc.abstractmethod
    async def elicit(
        self,
        message: str,
        requestedSchema: types.ElicitRequestedSchema,
        related_request_id: types.RequestId | None = None,
    ) -> types.ElicitResult:
        """Send an elicitation/create request."""
        raise NotImplementedError

    @abc.abstractmethod
    async def send_ping(self) -> types.EmptyResult:
        """Send a ping request."""
        raise NotImplementedError

    @abc.abstractmethod
    async def send_progress_notification(
        self,
        progress_token: str | int,
        progress: float,
        total: float | None = None,
        message: str | None = None,
        related_request_id: str | None = None,
    ) -> None:
        """Send a progress notification."""
        raise NotImplementedError

    @abc.abstractmethod
    async def send_resource_list_changed(self) -> None:
        """Send a resource list changed notification."""
        raise NotImplementedError

    @abc.abstractmethod
    async def send_tool_list_changed(self) -> None:
        """Send a tool list changed notification."""
        raise NotImplementedError

    @abc.abstractmethod
    async def send_prompt_list_changed(self) -> None:
        """Send a prompt list changed notification."""
        raise NotImplementedError
