"""Example MCP server with gRPC transport for tool with schema."""

from typing import Literal

import pydantic
from absl import app, flags, logging

from mcp.server import fastmcp

_PORT = flags.DEFINE_integer("port", 50051, "Server port")


class CalculatorOutput(pydantic.BaseModel):
    result: float


def setup_server(port: int) -> fastmcp.FastMCP:
    """Set up the FastMCP server with tool with schema."""
    mcp = fastmcp.FastMCP(
        name="Tool With Schema gRPC Server",
        instructions=("A simple MCP server demonstrating gRPC transport with tool schema validation."),
        target=f"127.0.0.1:{port}",
        grpc_enable_reflection=True,
    )

    @mcp.tool()
    def weather_tool(location: str, unit: Literal["celsius", "fahrenheit"] = "celsius") -> str:
        """Gets the weather for a given location."""
        return f"Weather for {location}: Sunny, unit: {unit}"

    @mcp.tool()
    def calculator_tool(a: float, b: float) -> CalculatorOutput:
        """Performs a calculation."""
        return CalculatorOutput(result=a + b)

    @mcp.tool()
    def bad_calculator_tool(a: float, b: float) -> CalculatorOutput:
        """Performs a calculation but returns wrong output type."""
        # This should fail validation because result is string
        # but schema expects float.
        return {"result": f"result={a + b}"}  # type: ignore

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
