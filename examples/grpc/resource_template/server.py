"""Example MCP server with gRPC transport for resource templates."""

from absl import app, flags, logging

from mcp.server import fastmcp

_PORT = flags.DEFINE_integer("port", 50051, "Server port")


def setup_server(port: int) -> fastmcp.FastMCP:
    """Set up the FastMCP server with resource templates."""
    mcp = fastmcp.FastMCP(
        name="Resource Template gRPC Server",
        instructions=("A simple MCP server demonstrating gRPC transport with resource templates."),
        target=f"127.0.0.1:{port}",
        grpc_enable_reflection=True,
    )

    @mcp.resource("mcp://hostname/user/{user}/profile")
    def user_profile_resource(user: str) -> str:
        """A templated resource for user profiles."""
        return f"Profile for {user}"

    @mcp.resource("mcp://hostname/user/{user}/document/{doc_id}")
    def user_document_resource(user: str, doc_id: str) -> str:
        """A templated resource for user documents."""
        return f"Document {doc_id} for {user}"

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
