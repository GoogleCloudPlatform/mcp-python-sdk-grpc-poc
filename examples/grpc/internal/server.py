"""Example MCP server with gRPC transport."""

import asyncio
import base64
import io
import pathlib
from typing import Annotated, TypedDict

import pydantic
from absl import app, flags, logging
from PIL import Image as PILImage

from mcp.server import fastmcp, session

_PORT = flags.DEFINE_integer("port", 50051, "Server port")


class ShrimpTank(pydantic.BaseModel):
    class Shrimp(pydantic.BaseModel):
        name: Annotated[str, pydantic.Field(max_length=10)]

    shrimp: list[Shrimp]


def setup_server(port: int) -> fastmcp.FastMCP:
    """Set up the FastMCP server with comprehensive features."""
    mcp = fastmcp.FastMCP(
        name="Simple gRPC Server",
        instructions=("A simple MCP server demonstrating gRPC transport capabilities."),
        target=f"127.0.0.1:{port}",
        grpc_enable_reflection=True,
    )

    @mcp.resource("test://hello")
    def hello_resource() -> str:
        """A simple resource that returns hello."""
        return "Hello from resource!"

    @mcp.resource("test://blob", mime_type="application/octet-stream")
    def blob_resource() -> bytes:
        """A resource that returns binary data."""
        return b"\x01\x02\x03\x04"

    @mcp.resource("test://greet/{name}")
    def greet_resource(name: str) -> str:
        """A resource that greets based on URI."""
        return f"Hello, {name} from resource!"

    image_bytes = b"fake_image_data"
    base64_string = base64.b64encode(image_bytes).decode("utf-8")

    @mcp.resource("test://image", mime_type="image/png")
    def get_image_as_string() -> str:
        """Return a test image as base64 string."""
        return base64_string

    @mcp.resource("test://image_bytes", mime_type="image/png")
    def get_image_as_bytes() -> bytes:
        """Return a test image as bytes."""
        return image_bytes

    @mcp.resource("dir://desktop")
    def desktop() -> list[str]:
        """List the files in the user"s desktop."""
        desktop = pathlib.Path.home() / "Desktop"
        return [str(f) for f in desktop.iterdir()]

    @mcp.tool()
    def add(a: int, b: int) -> int:
        """Add two numbers together."""
        # Create an instance of the expected message type
        result = a + b
        logging.info("Adding %s + %s = %s", a, b, result)
        return result

    @mcp.tool()
    def list_tools() -> list[str]:
        """A tool that returns a list of strings."""
        return ["one", "two"]

    @mcp.tool()
    def greet(name: str) -> str:
        """Greet someone by name."""
        # Create an instance of the expected message type
        greeting = f"Hello, {name}! Welcome to the Simple gRPC Server!"
        logging.info("Greeting %s", name)
        # Use generated proto message if available
        return greeting

    @mcp.tool()
    def name_shrimp(
        tank: ShrimpTank,
        # You can use pydantic Field in function signatures for validation.
        extra_names: Annotated[list[str], pydantic.Field(max_length=10)],
    ) -> list[str]:
        """List all shrimp names in the tank."""
        return [shrimp.name for shrimp in tank.shrimp] + extra_names

    @mcp.tool()
    async def download_file(
        filename: str,
        size_mb: float,
        ctx: fastmcp.Context[session.ServerSession, None],
    ) -> str:
        """Simulate downloading a file with progress updates.

        Args:
            filename: Name of the file to download
            size_mb: Size of the file in MB
            ctx: Context object for server session and progress reporting
        """
        await ctx.info(f"Starting download of {filename} ({size_mb} MB)")

        # Simulate download with progress updates
        total_bytes = int(size_mb * 1024 * 1024)  # Convert MB to bytes
        chunk_size = 64 * 1024  # 64KB chunks
        downloaded = 0

        while downloaded < total_bytes:
            # Simulate network delay
            await asyncio.sleep(0.1)

            # Calculate progress
            progress = downloaded / total_bytes
            remaining_mb = (total_bytes - downloaded) / (1024 * 1024)

            # Update progress
            print(f"🔄 Sending progress: {progress:.2f} - {downloaded / (1024 * 1024):.1f} MB downloaded")
            await ctx.report_progress(
                progress=progress,
                total=1.0,
                message=(f"Downloaded {downloaded / (1024 * 1024):.1f} MB, {remaining_mb:.1f} MB remaining"),
            )

            # Simulate chunk download
            chunk = min(chunk_size, total_bytes - downloaded)
            downloaded += chunk

        print("🔄 Sending final progress: 100% - Download completed")
        await ctx.report_progress(
            progress=1.0,
            total=1.0,
            message="Download completed successfully",
        )

        print(f"Successfully downloaded {filename} ({size_mb} MB)")
        return f"Successfully downloaded {filename} ({size_mb} MB)"

    # Using Pydantic models for rich structured data
    class WeatherData(pydantic.BaseModel):
        """Weather information structure."""

        temperature: float = pydantic.Field(description="Temperature in Celsius")
        humidity: float = pydantic.Field(description="Humidity percentage")
        condition: str
        wind_speed: float

    @mcp.tool()
    def get_weather(unused_city: str) -> WeatherData:
        """Get weather for a city - returns structured data."""
        # Simulated weather data
        return WeatherData(
            temperature=22.5,
            humidity=45.0,
            condition="sunny",
            wind_speed=5.2,
        )

    # Using TypedDict for simpler structures
    class LocationInfo(TypedDict):
        latitude: float
        longitude: float
        name: str

    @mcp.tool()
    def get_location(unused_address: str) -> LocationInfo:
        """Get location coordinates."""
        return LocationInfo(latitude=51.5074, longitude=-0.1278, name="London, UK")

    # Using dict[str, Any] for flexible schemas
    @mcp.tool()
    def get_statistics(unused_data_type: str) -> dict[str, float]:
        """Get various statistics."""
        return {"mean": 42.5, "median": 40.0, "std_dev": 5.2}

    # Ordinary classes with type hints work for structured output
    class UserProfile:
        name: str
        age: int
        email: str | None = None

        def __init__(self, name: str, age: int, email: str | None = None):
            self.name = name
            self.age = age
            self.email = email

    @mcp.tool()
    def get_user(unused_user_id: str) -> UserProfile:
        """Get user profile - returns structured data."""
        return UserProfile(name="Alice", age=30, email="alice@example.com")

    @mcp.tool()
    def get_image():
        img = PILImage.new("RGB", (1, 1), color="red")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return ["image", fastmcp.utilities.types.Image(data=buf.getvalue(), format="png")]

    # Classes WITHOUT type hints cannot be used for structured output
    class UntypedConfig:
        def __init__(self, setting1, setting2):  # type: ignore[reportMissingParameterType]
            self.setting1 = setting1
            self.setting2 = setting2

    @mcp.tool()
    def get_config() -> UntypedConfig:
        """This returns unstructured output - no schema generated."""
        return UntypedConfig("value1", "value2")

    # Lists and other types are wrapped automatically
    @mcp.tool()
    def list_cities() -> list[str]:
        """Get a list of cities."""
        return ["London", "Paris", "Tokyo"]
        # Returns: {"result": ["London", "Paris", "Tokyo"]}

    @mcp.tool()
    def get_temperature(unused_city: str) -> float:
        """Get temperature as a simple float."""
        return 22.5
        # Returns: {"result": 22.5}

    @mcp.tool()
    async def blocking_tool():
        """A tool that blocks for 10 seconds."""
        await asyncio.sleep(10)
        return "Finished"

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
