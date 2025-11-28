from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic

from typing_extensions import TypeVar

from mcp.shared.session import BaseSession
from mcp.types import RequestId, RequestParams

LifespanContextT = TypeVar("LifespanContextT")
RequestT = TypeVar("RequestT", default=Any)

if TYPE_CHECKING:
    from mcp.client.transport_session import TransportSession as ClientTransportSession
    from mcp.server.transport_session import TransportSession as ServerTransportSession

SessionT = TypeVar(
    "SessionT", bound=BaseSession[Any, Any, Any, Any, Any] | "ClientTransportSession" | "ServerTransportSession"
)


@dataclass
class RequestContext(Generic[SessionT, LifespanContextT, RequestT]):
    request_id: RequestId
    meta: RequestParams.Meta | None
    session: SessionT
    lifespan_context: LifespanContextT
    request: RequestT | None = None
