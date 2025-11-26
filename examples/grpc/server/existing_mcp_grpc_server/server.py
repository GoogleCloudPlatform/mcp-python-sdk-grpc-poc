"""The Python implementation of the AIO GRPC server."""

from concurrent import futures
import logging
import asyncio

import grpc
from grpc import aio

from mcp.server.fastmcp import FastMCP

def setup_server(port: int) -> FastMCP:
  """Set up the FastMCP server with comprehensive features."""
  mcp = FastMCP(
      name="Simple gRPC Server",
      instructions=(
          "A simple MCP server demonstrating gRPC transport capabilities."
      ),
      host="127.0.0.1",
      port=port,
  )

  @mcp.tool()
  def add(a: int, b: int) -> int:
    """Add two numbers together."""
    # Create an instance of the expected message type
    result = a + b
    return result

  return mcp

async def serve():
    port = "50051"
    server = aio.server(futures.ThreadPoolExecutor(max_workers=10))
    mcp_server = setup_server(port)
    mcp_server.add_to_existing_server(server)
    server.add_insecure_port("[::]:" + port)
    await server.start()
    print("Server started, listening on " + port)
    await server.wait_for_termination()


if __name__ == "__main__":
    logging.basicConfig()
    asyncio.run(serve())
