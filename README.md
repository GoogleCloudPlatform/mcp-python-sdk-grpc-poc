This project is a fork of <https://github.com/modelcontextprotocol/python-sdk> that adds
support for the gRPC transport described in
[SEP-1352](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1352).
This is a proof-of-concept (POC) in support of that SEP.

This fork may or may not be maintained in the long term.  Ideally, if the SEP is
accepted, we will upstream these changes and abandon this fork.  Alternatively,
if we can introduce a pluggable transport API to the upstream SDK, then we can
distribute the gRPC transport as a separate package without having to fork the entire
SDK, in which case would also abandon this fork.  However, if we can't make either
of those options work, then we will continue to maintain this fork, periodically
syncing changes from the upstream SDK.

See also the README from the upstream SDK at <https://github.com/modelcontextprotocol/python-sdk/blob/main/README.md>.

### gRPC Transport

## Features

✅ Supported ❌ Not Supported ⚪ Not Needed/Not Applicable

| Feature | gRPC Transport | Comment |
| :--- | :---: | :--- |
| Initialisation | ✅ | Was done as version negotion |
| Server-Tool | ✅ | |
| Server-Client | ✅ | |
| Server-Prompt | ❌ | |
| Client-Roots | ❌ | |
| Client-Sampling | ❌ | |
| Client-Elicitation | ❌ | |
| Utility-Ping | ⚪ | This is not needed for gRPC transport |
| Utility-Cancellation | ✅ | Cancellation of RPC call in gRPC transport |
| Utility-Progress | ✅ | |
| Utility-Completion | ❌ | |
| Utility-Logging | ❌ | |
| Utility-Pagination | ❌ | |

## Documentation

The following documentation files have been added to the `docs` folder:

* [`grpc_docs/version_negotiation.md`](grpc_docs/version_negotiation.md): Documentation on version negotiation.
* [`grpc_docs/timeout.md`](grpc_docs/timeout.md): Documentation on handling timeouts.
* [`grpc_docs/tll_notification.md`](grpc_docs/tll_notification.md): Documentation on TTL and expiry change notification.

## New Files

The major new files introduced for gRPC transport are:

* `mcp/server/grpc.py`: Contains the gRPC server implementation.
* `mcp/client/grpc_transport_session.py`: Contains the gRPC client transport session.

### Other New Files

* `mcp/utils/convert.py`: Provides utility functions for converting between different data formats.
* `mcp/utils/grpc_utils.py`: Contains gRPC-specific utility functions.
* `mcp/server/grpc_session.py`: Defines the session object for gRPC tool calls.
* `examples/`: This directory contains example implementations for both gRPC and HTTP transports, including server and client examples.

## Protocol Definition

The gRPC services and messages are defined in `src/mcp/proto/mcp.proto`. This file is essential for understanding the structure of the gRPC communication.

## Getting Started

### Server Examples

Here's how to start an MCP server using `FastMCP` with both gRPC and HTTP transports. The gRPC server can be started in a similar fashion to the HTTP server by changing the `transport` parameter in `mcp.run()` to `transport="grpc"`.

The gRPC server implementation uses the `grpc.aio` stack.

#### gRPC Server

```python
from mcp.server.fastmcp.server import FastMCP

mcp = FastMCP()
@mcp.tool()
def my_tool(param: str) -> str:
  return f"Hello from {param}"

mcp.run(transport="grpc")
```

All options that a `grpc.aio.Server` takes can be given to the `FastMCP` server as settings when initializing `FastMCP`. These settings include:
* `target`: The address the gRPC server will listen on.
* `grpc_enable_reflection`: Whether to enable gRPC reflection.
* `grpc_migration_thread_pool`: Executor for gRPC migration.
* `grpc_handlers`: Custom gRPC handlers.
* `grpc_interceptors`: gRPC interceptors to apply.
* `grpc_options`: Additional gRPC channel options.
* `grpc_maximum_concurrent_rpcs`: Maximum number of concurrent RPCs.
* `grpc_compression`: gRPC compression algorithm.
* `grpc_credentials`: Credentials for secure gRPC channels.

#### HTTP Server

```python
from mcp.server.fastmcp.server import FastMCP

mcp = FastMCP()
@mcp.tool()
def my_tool(param: str) -> str:
  return f"Hello from {param}"

mcp.run(transport="streamable-http")
```

### Client Examples

The client APIs are exactly the same as in the original Python SDK,
but the transport session objects used are different.

#### gRPC Client

```python
import asyncio
import grpc
from mcp.transport.grpc_transport_session import GRPCTransportSession

async def main(host="localhost", port=50051):
    credentials = grpc.local_channel_credentials()
    session = GRPCTransportSession(target=f"{host}:{port}", credentials=credentials)
    try:
        print("--- Listing Tools ---")
        tools = await session.list_tools()
        print(tools)
        print("---------------------\n")
    finally:
        await session.close()

if __name__ == "__main__":
    asyncio.run(main())
```

#### HTTP Client

```python
from datetime import timedelta
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def main():
    async with streamablehttp_client(
        url="http://localhost:8000/mcp",
        headers={"User-Agent": "MyMCPClient/1.0"},
        timeout=timedelta(seconds=30),
        sse_read_timeout=timedelta(minutes=5),
        terminate_on_close=True,  # Send DELETE on close
    ) as (read_stream, write_stream, get_session_id):

        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            session_id = get_session_id()
            print(f"Session ID: {session_id}")
            tools = await session.list_tools()
            print(f"Tools: {tools}")
```
