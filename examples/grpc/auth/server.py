"""Example MCP server with gRPC transport with TLS"""

import grpc
from absl import app, flags, logging
from mcp.examples.grpc.auth import _credentials

from mcp.server import fastmcp

_PORT = flags.DEFINE_integer("port", 50051, "Server port")


def setup_server(port: int) -> fastmcp.FastMCP:
    """Set up the FastMCP server with TLS."""
    server_credentials = grpc.ssl_server_credentials(
        (
            (
                _credentials.SERVER_CERTIFICATE_KEY,
                _credentials.SERVER_CERTIFICATE,
            ),
        )
    )
    mcp = fastmcp.FastMCP(
        name="Simple gRPC Server",
        instructions=("A simple MCP server demonstrating gRPC transport capabilities."),
        target=f"127.0.0.1:{port}",
        grpc_enable_reflection=True,
        grpc_credentials=server_credentials,
    )

    @mcp.tool()
    def add(a: int, b: int) -> int:
        """Add two numbers together."""
        result = a + b
        logging.info("Adding %s + %s = %s", a, b, result)
        return result

    return mcp


def main(argv) -> None:
    if len(argv) > 1:
        raise app.UsageError("Too many command-line arguments.")

    mcp = setup_server(_PORT.value)
    logging.info("Starting MCP gRPC Server on port %s...")
    logging.info("Server will be available on localhost:%s", _PORT.value)
    logging.info("Press Ctrl-C to stop the server")

    try:
        # Run the server with gRPC transport
        mcp.run(transport="grpc")
    except KeyboardInterrupt:
        logging.info("Server stopped by user")
    except Exception as e:
        logging.error("Server error: %s", e)
        raise


if __name__ == "__main__":
    app.run(main)
