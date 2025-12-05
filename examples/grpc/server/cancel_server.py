import asyncio
import logging

from mcp.server.fastmcp import FastMCP
from mcp.server.grpc import create_mcp_grpc_server

logger = logging.getLogger(__name__)


async def main():
    """Run the gRPC server."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    mcp = FastMCP(
        name="CancelExample",
        instructions="An example server with a cancellable tool.",
    )

    @mcp.tool()
    async def long_running_tool():
        """
        This tool runs for 60 seconds, but can be cancelled by the client.
        """
        logger.info("long_running_tool started")
        try:
            await asyncio.sleep(60)
            logger.info("long_running_tool finished")
            return "Tool finished without cancellation"
        except asyncio.CancelledError:
            logger.info("long_running_tool cancelled")
            return "Tool was cancelled"

    server = await create_mcp_grpc_server(target="127.0.0.1:50051", mcp_server=mcp)
    logger.info("gRPC server started on 127.0.0.1:50051")
    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        await server.stop(grace=1)
    logger.info("gRPC server stopped")


if __name__ == "__main__":
    asyncio.run(main())
