import asyncio
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

            config = await session.call_tool("get_config")
            print(f"Untyped Config: {config}")

            cities = await session.call_tool("list_cities")
            print(f"Cities: {cities}")

            list_tool = await session.call_tool("list_tools")
            print(f"List Tool: {list_tool}")

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
            result = await session.call_tool("get_image")
            print(f"Result: {result}")
            print("--------------------------------------------\n")

if __name__ == "__main__":
    asyncio.run(main())