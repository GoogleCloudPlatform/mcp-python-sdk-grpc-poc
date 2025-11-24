"""Example client for calling the MCP gRPC server simple resource."""

import asyncio

from absl import app
from absl import flags
import mcp
from mcp.client import grpc_transport_session

_SERVER_HOST = flags.DEFINE_string("server_host", "localhost", "Server host")
_SERVER_PORT = flags.DEFINE_integer("server_port", 50052, "Server port")


async def call_server(host: str, port: int):
  """Call the MCP gRPCserver and print the results."""
  print("========================================")
  print(" MCP gRPC Simple Resource Client Example")
  print("========================================")
  session = grpc_transport_session.GRPCTransportSession(target=f"{host}:{port}")
  print(f"➡️ Connecting to server: {host}:{port}")

  try:
    print("\n========================================")
    print("➡️ Listing available resources...")
    print("========================================")
    resources = await session.list_resources()
    print("✅ Received resource list. Available resources:")
    print(f"{resources}")

    print("\n========================================")
    print("➡️ Reading non-existent resource 'mcp://resource/non_existent'...")
    print("========================================")
    try:
      await session.read_resource("mcp://resource/non_existent")
    except mcp.McpError as e:
      print(
          "❌ Received expected failure response for non-existent resource:"
          f"\n   {e}"
      )

    print("\n========================================")
    print("➡️ Reading resource 'mcp://resource/simple'...")
    print("========================================")
    resource_content = await session.read_resource("mcp://resource/simple")
    print(f"✅ Received resource content:\n   {resource_content}")
    print("========================================")

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
