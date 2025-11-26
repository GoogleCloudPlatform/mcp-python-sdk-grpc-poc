"""Example client with TLS for calling the MCP gRPC server."""

import asyncio

from absl import app
from absl import flags
import grpc
import mcp
from mcp.client import grpc_transport_session
from mcp.examples.grpc.auth import _credentials


_SERVER_HOST = flags.DEFINE_string("server_host", "localhost", "Server host")
_SERVER_PORT = flags.DEFINE_integer("server_port", 50051, "Server port")


async def call_server(host, port):
  """Call the MCP gRPCserver and print the results."""
  channel_credential = grpc.ssl_channel_credentials(
      _credentials.ROOT_CERTIFICATE
  )
  session = grpc_transport_session.GRPCTransportSession(
      target=f"{host}:{port}", channel_credential=channel_credential
  )

  try:
    print("--- Listing Tools ---")
    tools = await session.list_tools()
    print(tools)
    print("---------------------\n")

    print("--- Calling tool with image output ---")
    result = await session.call_tool("add", {"a": 7, "b": 2})
    print(f"Result: {result}")
    print("--------------------------------------------\n")

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
