# Version Negotiation

This document describes how protocol version negotiation is handled in the MCP Python SDK's gRPC transport. Version negotiation ensures that clients and servers can communicate effectively even if they support different sets of MCP protocol versions.

## 1. Supported Protocol Versions

The set of supported MCP protocol versions is defined in `shared/version.py`:

```python
from mcp.types import LATEST_PROTOCOL_VERSION

SUPPORTED_PROTOCOL_VERSIONS: list[str] = ["2024-11-05", "2025-03-26", LATEST_PROTOCOL_VERSION]
```

`LATEST_PROTOCOL_VERSION` is the most recent version the SDK supports.

## 2. Client-Side Version Handling

The client-side gRPC transport session, implemented in `mcp/client/grpc_transport_session.py`, manages the negotiated protocol version.

### Sending the Protocol Version

When a client makes a unary RPC call (e.g., `ListTools`, `ListResources`, `ReadResource`), the `GRPCTransportSession` includes the `mcp-protocol-version` in the gRPC request metadata. Initially, this is set to `LATEST_PROTOCOL_VERSION`.

```python
# From mcp/client/grpc_transport_session.py
async def _call_unary_rpc(self, rpc_method: Any, request: Any, timeout: float | None, metadata: list[tuple[str, str]] | None = None) -> Any:
    # ...
    new_metadata = metadata + [(grpc_utils.MCP_PROTOCOL_VERSION_KEY, self.negotiated_version)]
    # ... makes the RPC call with new_metadata
```

### Handling Version Mismatch

If the server does not support the protocol version sent by the client, it will respond with a `grpc.StatusCode.UNIMPLEMENTED` error. The client's `_check_and_update_version` method is designed to catch and handle this:

```python
# From mcp/client/grpc_transport_session.py
def _check_and_update_version(self, e: grpc.RpcError) -> bool:
    if e.code() == grpc.StatusCode.UNIMPLEMENTED:
        initial_metadata = e.initial_metadata()
        negotiated_version = grpc_utils.get_metadata_value(initial_metadata, grpc_utils.MCP_PROTOCOL_VERSION_KEY)

        if negotiated_version is not None and negotiated_version in version.SUPPORTED_PROTOCOL_VERSIONS:
            # Server provided a supported version, update and retry
            self.negotiated_version = negotiated_version
            return True
        # ... otherwise, fail ...
    return False
```

If the server's `UNIMPLEMENTED` error includes metadata with a supported `mcp-protocol-version`, the client updates its `self.negotiated_version` and retries the RPC with the newly negotiated version.

## 3. Server-Side Version Checking

The MCP gRPC server implementation in `mcp/server/grpc.py` uses a decorator to enforce protocol version checks.

### The `@grpc_utils.check_protocol_version_from_metadata` Decorator

Each of the `McpServicer` RPC methods (`ListResources`, `ListTools`, etc.) is decorated with `@grpc_utils.check_protocol_version_from_metadata`. This decorator, defined in `mcp/shared/grpc_utils.py`, performs the following steps:

1. **Extract Version:** It extracts the value of the `mcp-protocol-version` key from the incoming request's gRPC metadata.
2. **Validate Version:** It checks if the extracted version is present in `version.SUPPORTED_PROTOCOL_VERSIONS`.
3. **Handle Missing/Unsupported Version:**
    * If the `mcp-protocol-version` is missing or not supported, the server sends initial metadata back to the client. This metadata includes the server's `LATEST_PROTOCOL_VERSION`.
    * The server then aborts the RPC with `grpc.StatusCode.UNIMPLEMENTED`, providing a message indicating the unsupported version and listing the versions it *does* support.
4. **Handle Supported Version:** If the client's provided version is supported, the server sends initial metadata back to the client, echoing the client's `mcp-protocol-version`, and allows the RPC call to proceed.

This collaborative process ensures that both client and server can successfully negotiate a common protocol version to use for their communication.
