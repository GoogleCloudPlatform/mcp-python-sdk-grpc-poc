"""Example client for tool cancellation."""

import asyncio

from absl import app, flags

import mcp
from mcp import types
from mcp.client import grpc_transport_session

_SERVER_HOST = flags.DEFINE_string("server_host", "localhost", "Server host")
_SERVER_PORT = flags.DEFINE_integer("server_port", 50051, "Server port")


async def call_server(host: str, port: int):
    """Call the MCP gRPCserver and print the results."""
    print("========================================")
    print(" MCP gRPC Tool Cancellation Example")
    print("========================================")
    session = grpc_transport_session.GRPCTransportSession(target=f"{host}:{port}")
    print(f"➡️ Connecting to server: {host}:{port}")

    try:
        # 1. Call slow_tool and cancel after 5 seconds
        print("\n========================================")
        print("➡️ Calling slow_tool and cancelling after 5 seconds...")
        print("========================================")
        call_tool_task1 = asyncio.create_task(session.call_tool("slow_tool", {}))

        await asyncio.sleep(5)
        # Fist request id is 1. we still need a way to get request id from api.
        # Cancel can also be called using timeout of the call API.
        request_id_to_cancel = 1
        print(f"➡️ Cancelling slow_tool call with request_id: {request_id_to_cancel}")
        cancel_notification1 = types.ClientNotification(
            root=types.CancelledNotification(
                method="notifications/cancelled",
                params=types.CancelledNotificationParams(requestId=request_id_to_cancel),
            )
        )
        await session.send_notification(cancel_notification1)

        try:
            result1 = await call_tool_task1
            print(f"Tool call 1 unexpected result: {result1}")
        except mcp.McpError as e:
            if e.error.code == types.REQUEST_CANCELLED:
                print("✅ Received expected cancellation for slow_tool:")
                print(f"   {e.error}")
            else:
                print(f"Tool call 1 failed with unexpected error: {e}")

        # 2. Call slow_tool and let it finish
        print("\n========================================")
        print("➡️ Calling slow_tool and letting it finish...")
        print("========================================")
        try:
            result2 = await asyncio.wait_for(session.call_tool("slow_tool", {}), timeout=15)
            print(f"✅ Received slow_tool response:\n   Message: {result2}")
        except mcp.McpError as e:
            print(f"❌ slow_tool failed unexpectedly: {e}")
        except asyncio.TimeoutError:
            print("❌ slow_tool timed out.")

        print("========================================")

    except mcp.McpError as e:
        print(f"An error occurred: {e}")
    finally:
        await session.close()
        print("Connection closed")


def main(argv) -> None:
    if len(argv) > 2:
        raise app.UsageError("Too many command-line arguments.")
    asyncio.run(call_server(host=_SERVER_HOST.value, port=_SERVER_PORT.value))


if __name__ == "__main__":
    app.run(main)
