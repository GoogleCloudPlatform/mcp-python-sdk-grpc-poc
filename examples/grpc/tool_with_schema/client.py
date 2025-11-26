"""Example client for tool with schema."""

import asyncio
import json

from absl import app
from absl import flags
import mcp
from mcp.client import grpc_transport_session

_SERVER_HOST = flags.DEFINE_string("server_host", "localhost", "Server host")
_SERVER_PORT = flags.DEFINE_integer("server_port", 50051, "Server port")


async def call_server(host: str, port: int):
  """Call the MCP gRPCserver and print the results."""
  print("========================================")
  print(" MCP gRPC Tool With Schema Client Example")
  print("========================================")
  session = grpc_transport_session.GRPCTransportSession(target=f"{host}:{port}")
  print(f"➡️ Connecting to server: {host}:{port}")

  try:
    print("\n========================================")
    print("➡️ Listing available tools...")
    print("========================================")
    tools = await session.list_tools()
    print("✅ Received tool list. Available tools:")
    for tool in tools.tools:
      print(f"   - {tool.name}: {tool.description}")
      if tool.inputSchema:
        print(f"     Input Schema: {json.dumps(tool.inputSchema, indent=2)}")
      if tool.outputSchema:
        print(f"     Output Schema: {json.dumps(tool.outputSchema, indent=2)}")

    # 1. Call weather_tool with correct input schema
    print("\n========================================")
    print(
        "➡️ Calling weather_tool with arguments: location='London',"
        " unit='celsius'..."
    )
    print("========================================")
    try:
      weather_response = await session.call_tool(
          "weather_tool", {"location": "London", "unit": "celsius"}
      )
      print(f"✅ Received weather_tool response:\n   {weather_response}")
    except mcp.McpError as e:
      print(f"❌ weather_tool failed unexpectedly: {e}")

    # 2. Call calculator_tool with correct input and output schema
    print("\n========================================")
    print("➡️ Calling calculator_tool with arguments: a=10, b=5...")
    print("========================================")
    try:
      calc_response = await session.call_tool(
          "calculator_tool", {"a": 10.0, "b": 5.0}
      )
      print(
          f"✅ Received calculator_tool response:\n   Result: {calc_response}"
      )
    except mcp.McpError as e:
      print(f"❌ calculator_tool failed unexpectedly: {e}")

    # 3. Call weather_tool with incorrect input schema (location is number)
    print("\n========================================")
    print("➡️ Calling weather_tool with invalid input schema: location=123.0...")
    print("========================================")
    try:
      result = await session.call_tool("weather_tool", {"location": 123.0})
      if result.isError:
        print(
            "✅ Received expected failure for weather_tool invalid input:\n "
            f"  {result}"
        )
      else:
        print(f"❌ weather_tool with invalid input succeeded Result: {result}")
    except mcp.McpError as e:
      print(f"❌ weather_tool with invalid input failed unexpectedly: {e}")

    # 4. Call bad_calculator_tool which returns output schema mismatch
    print("\n========================================")
    print(
        "➡️ Calling bad_calculator_tool with output schema mismatch: a=1.0,"
        " b=2.0..."
    )
    print("========================================")
    try:
      result = await session.call_tool(
          "bad_calculator_tool", {"a": 1.0, "b": 2.0}
      )
      if result.isError:
        print(
            "✅ Received expected failure for bad_calculator_tool invalid"
            f" output:\n   {result}"
        )
      else:
        print(f"❌ bad_calculator_tool with invalid output! Result: {result}")
    except mcp.McpError as e:
      print(f"❌ bad_calculator_tool failed unexpectedly: {e}")

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
