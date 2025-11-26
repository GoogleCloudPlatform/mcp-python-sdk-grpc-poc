# TTL and Expiry Change Notification

The Model Context Protocol (MCP) allows resources to have a Time-To-Live (TTL) and an expiry time. This document explains how these are handled in the gRPC transport layer of the Python SDK.

## Time-To-Live (TTL)

TTL specifies how long a client can cache a resource before it should be considered stale. The gRPC implementation communicates TTL information within the proto responses.

### Server-Side: `mcp/server/grpc.py`

In `mcp/server/grpc.py`, when the MCP server sends a resource, it can include TTL information in the gRPC response proto. The server implementation must read the TTL associated with a resource (if any) and include it in the response sent to the client.

The exact mechanism for including TTL in the gRPC response proto would be within the resource handling logic in `grpc.py`.

### Client-Side: `mcp/client/grpc_transport_session.py`

The `grpc_transport_session.py` is responsible for the client-side handling of gRPC communication. When a client makes a `ReadResource` call, the `GRPCTransportSession` receives the response, including any gRPC response proto.

## Expiry Change Notification

MCP also allows for notifications when a resource's expiry time changes. This is important for ensuring clients have up-to-date information.

### How it's Handled in gRPC

When a resource's TTL expires, the `grpc_transport_session.py` will call the provided `message_handler` with a `types.ServerNotification`. This notification indicates that a change has occurred, allowing the client to take appropriate action, such as re-fetching the resource.
