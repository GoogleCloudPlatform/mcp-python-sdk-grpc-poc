# Handling Timeouts

This document describes how timeouts are managed within the MCP Python SDK's gRPC transport. Timeouts are crucial for preventing long-running or unresponsive calls from consuming excessive resources.

## 1. Client-Side Timeouts

In the gRPC implementation, clients can specify a timeout for each RPC call made through the `GRPCTransportSession`. This is typically done by passing a `timeout` parameter to the client methods.

### Setting Timeouts in `GRPCTransportSession`

When initializing or using methods of `GRPCTransportSession`, you can provide a timeout value, often in seconds. This timeout will be applied to the underlying gRPC channel or individual RPC calls. Note that the `call_tool` method also accepts a timeout parameter, which, if provided, takes precedence over any session-level timeout.

Example of setting a timeout for a `list_tools` call:

```python
import asyncio
from datetime import timedelta
from mcp.transport.grpc_transport_session import GRPCTransportSession

async def list_tools_with_timeout(host="localhost", port=50051):
    # Set a read timeout of 5 seconds for the session
    session = GRPCTransportSession(target=f"{host}:{port}", read_timeout_seconds=timedelta(seconds=5))
    try:
        print("--- Listing Tools with Timeout ---")
        tools = await session.list_tools()
        print(tools)
        print("-------------------------------\n")
    except asyncio.TimeoutError:
        print("Error: list_tools timed out!")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        await session.close()

if __name__ == "__main__":
    asyncio.run(list_tools_with_timeout())
```


### How Timeouts are Handled

When a timeout is set, the gRPC client will automatically cancel the RPC if the response is not received within the specified duration. This results in an exception being raised on the client side. The specific exception you might encounter is:

*   `mcp_grpc.shared.exceptions.McpError` with a code of `mcp_grpc.types.REQUEST_TIMEOUT`: This is raised when the gRPC call exceeds the deadline, originating from a `grpc.RpcError` with `grpc.StatusCode.DEADLINE_EXCEEDED`.

## 3. Configuration

The `grpc_transport_session.py` and `grpc.py` files contain the implementation details of how these timeouts are specifically integrated with the gRPC client and server within the MCP SDK. For instance, `grpc_transport_session.py` would be responsible for passing the `timeout` value to the underlying gRPC library calls.
