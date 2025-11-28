import asyncio
import logging

from mcp import types
from mcp.client.grpc_transport_session import GRPCTransportSession
from mcp.shared.exceptions import McpError

logger = logging.getLogger(__name__)


async def main():
    """Run the gRPC client."""
    logging.basicConfig(level=logging.INFO)
    transport = GRPCTransportSession(target="127.0.0.1:50051")

    try:
        logger.info("Calling long_running_tool twice")
        call_tool_task1 = asyncio.create_task(transport.call_tool("long_running_tool", {}))
        call_tool_task2 = asyncio.create_task(transport.call_tool("long_running_tool", {}))

        # Allow some time for the calls to start
        await asyncio.sleep(1)

        # Send cancellation notification for request_id 1
        request_id_to_cancel = 1
        logger.info(f"Sending cancellation for request_id: {request_id_to_cancel}")
        cancel_notification1 = types.ClientNotification(
            root=types.CancelledNotification(
                method="notifications/cancelled",
                params=types.CancelledNotificationParams(requestId=request_id_to_cancel),
            )
        )
        await transport.send_notification(cancel_notification1)

        try:
            result1 = await call_tool_task1
            logger.info(f"Tool call 1 result: {result1}")
        except McpError as e:
            if e.error.code == types.REQUEST_CANCELLED:
                logger.info("Tool call 1 successfully cancelled as expected.")
            else:
                logger.error(f"Tool call 1 failed with unexpected error: {e}")

        # Check task 2 is still running then cancel it
        try:
            await asyncio.wait_for(asyncio.shield(call_tool_task2), 0.1)
        except asyncio.TimeoutError:
            logger.info("Tool call 2 is still running as expected.")
        else:
            logger.error("Tool call 2 finished unexpectedly.")

        await asyncio.sleep(3)

        logger.info("Sending cancellation for request_id 2")
        cancel_notification2 = types.ClientNotification(
            root=types.CancelledNotification(
                method="notifications/cancelled",
                params=types.CancelledNotificationParams(requestId=2),
            )
        )
        await transport.send_notification(cancel_notification2)

        try:
            result2 = await call_tool_task2
            logger.info(f"Tool call 2 result: {result2}")
        except McpError as e:
            if e.error.code == types.REQUEST_CANCELLED:
                logger.info("Tool call 2 successfully cancelled as expected.")
            else:
                logger.error(f"Tool call 2 failed with unexpected error: {e}")

    finally:
        await transport.close()
        logger.info("Connection closed")


if __name__ == "__main__":
    asyncio.run(main())
