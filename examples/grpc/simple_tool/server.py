"""Example MCP server with gRPC transport for a simple tool."""

from absl import app, flags, logging

from mcp.server import fastmcp

_PORT = flags.DEFINE_integer("port", 50051, "Server port")


def setup_server(port: int) -> fastmcp.FastMCP:
    """Set up the FastMCP server with simple tool."""
    mcp = fastmcp.FastMCP(
        name="Simple Tool gRPC Server",
        instructions=("A simple MCP server demonstrating gRPC transport with a simple tool."),
        target=f"127.0.0.1:{port}",
        grpc_enable_reflection=True,
    )

    @mcp.tool()
    def greeting_tool(name: str) -> str:
        """A simple tool that returns a greeting."""
        greeting = f"Hello, {name}!"
        logging.info("Greeting %s", name)
        return greeting

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
