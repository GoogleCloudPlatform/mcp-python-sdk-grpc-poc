from typing import TYPE_CHECKING, Any, Protocol

from jsonschema import SchemaError, ValidationError
from jsonschema.validators import validate

import mcp.types as types
from mcp.shared.context import RequestContext
from mcp.shared.session import RequestResponder

if TYPE_CHECKING:
    from mcp.client.session import ClientSession


class SamplingFnT(Protocol):
    async def __call__(
        self,
        context: RequestContext["ClientSession", Any],
        params: types.CreateMessageRequestParams,
    ) -> types.CreateMessageResult | types.ErrorData: ...


class ElicitationFnT(Protocol):
    async def __call__(
        self,
        context: RequestContext["ClientSession", Any],
        params: types.ElicitRequestParams,
    ) -> types.ElicitResult | types.ErrorData: ...


class ListRootsFnT(Protocol):
    async def __call__(
        self, context: RequestContext["ClientSession", Any]
    ) -> types.ListRootsResult | types.ErrorData: ...


class LoggingFnT(Protocol):
    async def __call__(
        self,
        params: types.LoggingMessageNotificationParams,
    ) -> None: ...


class MessageHandlerFnT(Protocol):
    async def __call__(
        self,
        message: RequestResponder[types.ServerRequest, types.ClientResult] | types.ServerNotification | Exception,
    ) -> None: ...


async def validate_tool_result(output_schema: dict[str, Any] | None, name: str, result: types.CallToolResult) -> None:
    """Validates tool result structured content against its output schema."""
    if output_schema and len(output_schema) > 0:
        if result.structuredContent is None and not result.content:
            raise RuntimeError(f"Tool {name} has an output schema but did not return structured content or content")
        if result.structuredContent is not None:
            try:
                validate(result.structuredContent, output_schema)
            except ValidationError as e:
                raise RuntimeError(f"Invalid structured content returned by tool {name}: {e}") from e
            except SchemaError as e:
                raise RuntimeError(f"Invalid schema for tool {name}: {e}") from e
