"""
Client example for the Simple gRPC Server using MCPClient class.

This script demonstrates how to connect to and interact with the Simple gRPC Server
using the MCPClient class pattern with gRPC transport.
"""

import logging
from datetime import timedelta
from mcp.client.grpc_transport_session import GRPCTransportSession
from mcp.types import CallToolRequestParams
from mcp import McpError
import asyncio
import argparse

logging.basicConfig(level=logging.INFO)

async def main(host="localhost", port=50051):
    """Run the client example using MCPClient class."""
    session = GRPCTransportSession(target=f"{host}:{port}")
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
                print(f"Progress: {progress/total*100:.2f}% - {message}")
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
        weather = await session.call_tool(
            "get_weather", {"city": "London"}
        )
        print(f"Weather in London: {weather}")

        print("-------------------------------------------\n")
        list_tools = await session.call_tool("list_tools")
        print(f"List Tools: {list_tools}")

        location = await session.call_tool(
            "get_location", {"address": "1600 Amphitheatre Parkway"}
        )
        print(f"Location: {location}")

        stats = await session.call_tool(
            "get_statistics", {"data_type": "sales"}
        )
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
            result = await session.call_tool(
                "blocking_tool", {}, read_timeout_seconds=timedelta(seconds=1)
            )
            print(f"Result: {result}")
        except McpError as e:
            print(f"Caught expected timeout error: {e}")
            print(f"Error code: {e.error.code}")
        print("-------------------------------------------\n")

    except McpError as e:
        print(f"An error occurred: {e}")
    finally:
        await session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="MCP gRPC Client with MCPClient Class"
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Server host (default: localhost)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=50051,
        help="Server port (default: 50051)"
    )
    args = parser.parse_args()

    asyncio.run(main(
        host=args.host,
        port=args.port
    ))
