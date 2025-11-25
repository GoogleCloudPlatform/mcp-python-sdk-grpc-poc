"""Example MCP server with gRPC transport for tool cancellation."""

import asyncio

from absl import app
from absl import flags
from absl import logging
from mcp.server import fastmcp
import pydantic

_PORT = flags.DEFINE_integer("port", 50051, "Server port")


def setup_server(port: int) -> fastmcp.FastMCP:
  """Set up the FastMCP server with cancellable tool."""
  mcp = fastmcp.FastMCP(
      name="Tool Cancellation gRPC Server",
      instructions=(
          "A simple MCP server demonstrating gRPC transport with tool"
          " cancellation."
      ),
      target=f"127.0.0.1:{port}",
      grpc_enable_reflection=True,
  )

  class Message(pydantic.BaseModel):
    """For structured output, we need to define the model."""
    message: str

  @mcp.tool()
  async def slow_tool() -> Message:
    """A tool that waits for 10 seconds, unless cancelled."""
    logging.info("slow_tool started")
    try:
      await asyncio.sleep(10)
      logging.info("slow_tool finished")
      return Message(message="Finished after 10 seconds")
    except asyncio.CancelledError:
      logging.info("slow_tool cancelled!")
      raise

  return mcp

def main(argv) -> None:
  if len(argv) > 1:
    raise app.UsageError("Too many command-line arguments.")

  mcp = setup_server(_PORT.value)
  logging.info("Starting MCP gRPC Server on port %s...", _PORT.value)
  logging.info("Server will be available on localhost:%s", _PORT.value)
  logging.info("Press Ctrl-C to stop the server")

  try:
    mcp.run(transport="grpc")
  except KeyboardInterrupt:
    logging.info("Server stopped by user")
  except Exception as e:
    print(f"Server error: {e}")
    raise


if __name__ == "__main__":
  app.run(main)
