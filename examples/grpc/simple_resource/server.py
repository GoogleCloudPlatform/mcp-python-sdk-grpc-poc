"""Example MCP server with gRPC transport for a simple resource."""

from absl import app, flags, logging

from mcp.server import fastmcp

_PORT = flags.DEFINE_integer("port", 50052, "Server port")


def setup_server(port: int) -> fastmcp.FastMCP:
    """Set up the FastMCP server with simple resource."""
    mcp = fastmcp.FastMCP(
        name="Simple Resource gRPC Server",
        instructions=("A simple MCP server demonstrating gRPC transport with a simple resource."),
        target=f"127.0.0.1:{port}",
        grpc_enable_reflection=True,
    )

    @mcp.resource("mcp://resource/simple", mime_type="text/plain")
    def simple_resource() -> str:
        """A simple resource that returns text."""
        return "Hello from resource!"

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
