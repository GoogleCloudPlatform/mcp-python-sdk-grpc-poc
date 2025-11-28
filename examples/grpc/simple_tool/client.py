"""Example client for calling the MCP gRPC server simple tool."""

import asyncio

from absl import app, flags

import mcp
from mcp.client import grpc_transport_session

_SERVER_HOST = flags.DEFINE_string("server_host", "localhost", "Server host")
_SERVER_PORT = flags.DEFINE_integer("server_port", 50051, "Server port")
_NAME = flags.DEFINE_string("name", "World", "Name to greet.")


async def call_server(host: str, port: int, name: str):
    """Call the MCP gRPCserver and print the results."""
    print("========================================")
    print(" MCP gRPC Simple Tool Client Example")
    print("========================================")
    session = grpc_transport_session.GRPCTransportSession(target=f"{host}:{port}")
    print(f"➡️ Connecting to server: {host}:{port}")

    try:
        print("\n========================================")
        print("➡️ Listing available tools...")
        print("========================================")
        tools = await session.list_tools()
        print("✅ Received tool list. Available tools:")
        print(f"{tools}")

        print("\n========================================")
        print("➡️ Calling non-existent tool 'non_existent_tool'")
        print("========================================")
        try:
            result = await session.call_tool("non_existent_tool", {})
            # Currently tool not found error returns
            #  as a text response with is_error true.(for python sdk)
            print(f"❌  Received tool response:\n   {result}")
        except mcp.McpError as e:
            print(f"❌ Received failure response for non-existent tool:\n   {e}")

        print("\n========================================")
        print(f"➡️ Calling tool 'greeting_tool' with parameter name: '{name}'")
        print("========================================")
        result = await session.call_tool(
            name="greeting_tool",
            arguments={"name": name},
        )
        print(f"✅ Received tool response:\n   {result}")
        print("========================================")

    except mcp.McpError as e:
        print(f"An error occurred: {e}")
    finally:
        await session.close()


def main(argv) -> None:
    if len(argv) > 3:
        raise app.UsageError("Too many command-line arguments.")

    asyncio.run(call_server(host=_SERVER_HOST.value, port=_SERVER_PORT.value, name=_NAME.value))


if __name__ == "__main__":
    app.run(main)
