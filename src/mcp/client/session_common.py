from typing import Any, Protocol
import mcp.types as types
from mcp.shared.context import RequestContext
from mcp.shared.session import RequestResponder
from jsonschema import ValidationError, SchemaError
from jsonschema.validators import validate

class SamplingFnT(Protocol):
    async def __call__(
        self,
        context: RequestContext["TransportSession", Any],
        params: types.CreateMessageRequestParams,
    ) -> types.CreateMessageResult | types.ErrorData: ...


class ElicitationFnT(Protocol):
    async def __call__(
        self,
        context: RequestContext["TransportSession", Any],
        params: types.ElicitRequestParams,
    ) -> types.ElicitResult | types.ErrorData: ...


class ListRootsFnT(Protocol):
    async def __call__(
        self, context: RequestContext["TransportSession", Any]
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

async def validate_tool_result(output_schema: dict[str, Any],
                                name: str,
                                result: types.CallToolResult) -> None:
    """Validates tool result structured content against its output schema."""
    if output_schema is not None and bool(output_schema):
        if result.structuredContent is None and not result.content:
            raise RuntimeError(
                f"Tool {name} has an output schema but did not return"
                " structured content or content"
            )
        if result.structuredContent is not None:
            try:
                validate(result.structuredContent, output_schema)
            except ValidationError as e:
                raise RuntimeError(
                    f"Invalid structured content returned by tool {name}: {e}"
                ) from e
            except SchemaError as e:
                raise RuntimeError(f"Invalid schema for tool {name}: {e}") from e
