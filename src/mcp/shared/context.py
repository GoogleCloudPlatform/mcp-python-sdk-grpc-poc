from dataclasses import dataclass
from typing import Any, Generic, TYPE_CHECKING

from typing_extensions import TypeVar

from mcp.shared.session import BaseSession
from mcp.types import RequestId, RequestParams

if TYPE_CHECKING:
    from mcp.client.transport_session import TransportSession as ClientTransportSession
    from mcp.server.transport_session import TransportSession as ServerTransportSession


SessionT = TypeVar("SessionT", bound=BaseSession[Any, Any, Any, Any, Any] | "ClientTransportSession" | "ServerTransportSession")
LifespanContextT = TypeVar("LifespanContextT")
RequestT = TypeVar("RequestT", default=Any)


@dataclass
class RequestContext(Generic[SessionT, LifespanContextT, RequestT]):
    request_id: RequestId
    meta: RequestParams.Meta | None
    session: SessionT
    lifespan_context: LifespanContextT
    request: RequestT | None = None
