"""Example client for calling the MCP gRPC server."""

import asyncio
import datetime

from absl import app, flags

import mcp
from mcp.client import grpc_transport_session

_SERVER_HOST = flags.DEFINE_string("server_host", "localhost", "Server host")
_SERVER_PORT = flags.DEFINE_integer("server_port", 50051, "Server port")


async def call_server(host, port):
    """Call the MCP gRPCserver and print the results."""
    session = grpc_transport_session.GRPCTransportSession(target=f"{host}:{port}")

    try:
        print("--- Listing Tools ---")
        tools = await session.list_tools()
        print(tools)
        print("---------------------\n")

        print("--- Listing Resources ---")
        resources = await session.list_resources()
        print(resources)
        print("-----------------------\n")

        print("--- Listing Resource Templates ---")
        resource_templates = await session.list_resource_templates()
        print(resource_templates)
        print("-----------------------\n")

        print("--- Reading Resource test://hello ---")
        resource_content = await session.read_resource("test://hello")
        print(resource_content)
        print("-----------------------------------\n")

        print("--- Reading Resource test://blob ---")
        resource_content = await session.read_resource("test://blob")
        print(resource_content)
        print("-----------------------------------\n")

        print("--- Reading Resource test://greet/World ---")
        resource_content = await session.read_resource("test://greet/World")
        print(resource_content)
        print("-----------------------------------\n")

        print("--- Reading Resource test://image ---")
        resource_content = await session.read_resource("test://image")
        print(resource_content)
        print("-----------------------------------\n")

        print("--- Reading Resource test://image_bytes ---")
        resource_content = await session.read_resource("test://image_bytes")
        print(resource_content)
        print("-----------------------------------\n")

        print("--- Reading Resource dir://desktop ---")
        resource_content = await session.read_resource("dir://desktop")
        print(resource_content)
        print("-----------------------------------\n")

        print("--- Calling download_file with progress ---")

        async def progress_callback(progress: float, total: float | None, message: str | None):
            if total:
                print(f"Progress: {progress / total * 100:.2f}% - {message}")
            else:
                print(f"Progress: {progress} - {message}")

        result = await session.call_tool(
            name="download_file",
            arguments={"filename": "test.txt", "size_mb": 1.0},
            progress_callback=progress_callback,
        )
        print(f"Final Result: {result}")

        print("-------------------------------------------\n")

        print("--- Calling tools with structured output ---")
        weather = await session.call_tool("get_weather", {"city": "London"})
        print(f"Weather in London: {weather}")

        print("-------------------------------------------\n")
        list_tools = await session.call_tool("list_tools")
        print(f"List Tools: {list_tools}")

        location = await session.call_tool("get_location", {"address": "1600 Amphitheatre Parkway"})
        print(f"Location: {location}")

        stats = await session.call_tool("get_statistics", {"data_type": "sales"})
        print(f"Statistics: {stats}")

        user = await session.call_tool("get_user", {"user_id": "123"})
        print(f"User Profile: {user}")

        config = await session.call_tool("get_config", {})
        print(f"Untyped Config: {config}")

        cities = await session.call_tool("list_cities", {})
        print(f"Cities: {cities}")

        temp = await session.call_tool("get_temperature", {"city": "Paris"})
        print(f"Temperature in Paris: {temp}")

        shrimp_names = await session.call_tool(
            "name_shrimp",
            {
                "tank": {"shrimp": [{"name": "shrimp1"}, {"name": "shrimp2"}]},
                "extra_names": ["bubbles"],
            },
        )
        print(f"Shrimp names: {shrimp_names}")
        print("--------------------------------------------\n")

        print("--- Calling tool with image output ---")
        result = await session.call_tool("get_image", {})
        print(f"Result: {result}")
        print("--------------------------------------------\n")

        print("--- Calling blocking_tool with 1s timeout ---")
        try:
            result = await session.call_tool("blocking_tool", {}, read_timeout_seconds=datetime.timedelta(seconds=1))
            print(f"Result: {result}")
        except mcp.McpError as e:
            print(f"Caught expected timeout error: {e}")
            print(f"Error code: {e.error.code}")
        print("-------------------------------------------\n")
    except mcp.McpError as e:
        print(f"An error occurred: {e}")
    finally:
        await session.close()


def main(argv) -> None:
    if len(argv) > 2:
        raise app.UsageError("Too many command-line arguments.")

    asyncio.run(call_server(host=_SERVER_HOST.value, port=_SERVER_PORT.value))


if __name__ == "__main__":
    app.run(main)
