import asyncio
from datetime import timedelta
from unittest import mock
import grpc
import pytest
import time
import unittest.mock

from mcp.proto import mcp_pb2, mcp_pb2_grpc
from mcp.shared import version
from google3.google.protobuf import struct_pb2

from mcp.client.grpc_transport_session import GRPCTransportSession
from mcp.client.cache import CacheEntry
from mcp.client import session_common
from mcp.shared.exceptions import McpError
from mcp import types

# Fixtures from test_grpc_transport_session.py
import socket
from collections.abc import Generator
from mcp.server.fastmcp.server import Context, FastMCP
from mcp.server.grpc import create_mcp_grpc_server
from mcp import types
from io import BytesIO
from PIL import Image as PILImage
import base64
from pydantic import BaseModel
from jsonschema import ValidationError


def setup_test_server(port: int) -> FastMCP:
    """Set up a minimal FastMCP server for testing mocks."""
    mcp = FastMCP(
        name="Test gRPC Server",
        instructions="A test MCP server for gRPC transport.",
        host="127.0.0.1",
        port=port,
    )
    return mcp


@pytest.fixture
def server_port() -> int:
    """Find an available port for the server."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
async def grpc_server(server_port: int) -> Generator[None, None, None]:
    """Start a gRPC server in process."""
    server_instance = setup_test_server(server_port)
    server = await create_mcp_grpc_server(
        target=f"127.0.0.1:{server_port}", mcp_server=server_instance
    )

    yield server

    await server.stop(grace=1)
    # Add a small delay to allow gRPC channels to close
    await asyncio.sleep(0.1)


def _create_mock_tool_proto(name: str):
    """Creates a mock tool proto with a given name."""
    mock_tool_proto = mock.MagicMock()
    mock_tool_proto.name = name
    mock_tool_proto.description = f"A {name} tool"
    mock_descriptor = mock.Mock()
    mock_descriptor.full_name = "mock_input_schema"
    mock_input_schema = mock.Mock(DESCRIPTOR=mock_descriptor)
    mock_input_schema.ListFields.return_value = []
    mock_tool_proto.input_schema = mock_input_schema
    return mock_tool_proto


class MockAsyncStream:
    def __init__(self, items):
        self._items = items
        self._iterator = iter(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._iterator)
        except StopIteration:
            raise StopAsyncIteration

@pytest.mark.anyio
async def test_list_resources_with_ttl_cache(grpc_server: None, server_port: int):
    """Test GRPCTransportSession.list_resources() uses cache with TTL."""
    message_handler = mock.AsyncMock()
    transport = GRPCTransportSession(
        target=f"127.0.0.1:{server_port}", message_handler=message_handler
    )
    try:
        list_resources_response = mock.MagicMock(resources=[], ttl=mock.MagicMock(seconds=0.01, nanos=0))
        list_resources_mock = mock.AsyncMock(return_value=list_resources_response)
        transport.grpc_stub.ListResources = list_resources_mock

        # First call, should call stub
        await transport.list_resources()
        assert list_resources_mock.call_count == 1

        # Wait for TTL to expire
        await asyncio.sleep(0.02)
        message_handler.assert_called_once()
        notification = message_handler.call_args[0][0]
        assert notification.root.method == "notifications/resources/list_changed"

        # Second call after expiry, should call stub again
        await transport.list_resources()
        assert list_resources_mock.call_count == 2
    finally:
        await transport.close()


@pytest.mark.anyio
async def test_list_resource_templates_with_ttl_cache(
    grpc_server: None, server_port: int
):
    """Test GRPCTransportSession.list_resource_templates() uses cache with TTL."""
    message_handler = mock.AsyncMock()
    transport = GRPCTransportSession(
        target=f"127.0.0.1:{server_port}", message_handler=message_handler
    )
    try:
        list_templates_response = mock.MagicMock(resourceTemplates=[], ttl=mock.MagicMock(seconds=0.01, nanos=0))
        list_templates_mock = mock.AsyncMock(return_value=list_templates_response)
        transport.grpc_stub.ListResourceTemplates = list_templates_mock

        # First call, should call stub
        await transport.list_resource_templates()
        assert list_templates_mock.call_count == 1

        # Wait for TTL to expire
        await asyncio.sleep(0.02)
        message_handler.assert_called_once()
        notification = message_handler.call_args[0][0]
        assert notification.root.method == "notifications/resources/list_changed"

        # Second call after expiry, should call stub again
        await transport.list_resource_templates()
        assert list_templates_mock.call_count == 2
    finally:
        await transport.close()

@pytest.mark.anyio
async def test_cache_entry_ttl():
    on_expire_mock = mock.AsyncMock()
    cache = CacheEntry(on_expire_mock)
    data = {"key": "value"}
    cache.set(data, timedelta(seconds=0.01))
    assert cache.get() == data

    # Wait for TTL to expire
    await asyncio.sleep(0.02)
    # Cache should now be expired, get() triggers on_expired
    result = cache.get()
    assert result is None
    on_expire_mock.assert_called_once()
    # Subsequent gets should also be None
    assert cache.get() is None

# Split of test_grpc_transport_session_timeout
@pytest.mark.anyio
async def test_list_resources_honors_session_timeout(grpc_server: None, server_port: int):
    """Test GRPCTransportSession.list_resources() honors session timeout."""
    transport = GRPCTransportSession(
        target=f"127.0.0.1:{server_port}",
        read_timeout_seconds=timedelta(seconds=5),
    )
    list_resources_mock = mock.AsyncMock(return_value=mock.MagicMock(resources=[], ttl=mock.MagicMock(seconds=1, nanos=0)))
    transport.grpc_stub.ListResources = list_resources_mock
    try:
        await transport.list_resources()
        list_resources_mock.assert_called_once_with(mock.ANY, timeout=5.0, metadata=[('mcp-protocol-version', version.LATEST_PROTOCOL_VERSION)])
    finally:
        await transport.close()

@pytest.mark.anyio
async def test_list_tools_honors_session_timeout(grpc_server: None, server_port: int):
    """Test GRPCTransportSession.list_tools() honors session timeout."""
    transport = GRPCTransportSession(
        target=f"127.0.0.1:{server_port}",
        read_timeout_seconds=timedelta(seconds=5),
    )
    list_tool_mock = mock.AsyncMock(return_value=mock.MagicMock(tools=[], ttl=mock.MagicMock(seconds=1, nanos=0)))
    transport.grpc_stub.ListTools = list_tool_mock
    try:
        await transport.list_tools()
        list_tool_mock.assert_called_once_with(mock.ANY, timeout=5.0, metadata=[('mcp-protocol-version', version.LATEST_PROTOCOL_VERSION)])
    finally:
        await transport.close()

@pytest.mark.anyio
async def test_list_resource_templates_honors_session_timeout(grpc_server: None, server_port: int):
    """Test GRPCTransportSession.list_resource_templates() honors session timeout."""
    transport = GRPCTransportSession(
        target=f"127.0.0.1:{server_port}",
        read_timeout_seconds=timedelta(seconds=5),
    )
    list_templates_mock = mock.AsyncMock(return_value=mock.MagicMock(resourceTemplates=[], ttl=mock.MagicMock(seconds=1, nanos=0)))
    transport.grpc_stub.ListResourceTemplates = list_templates_mock
    try:
        await transport.list_resource_templates()
        list_templates_mock.assert_called_once_with(mock.ANY, timeout=5.0, metadata=[('mcp-protocol-version', version.LATEST_PROTOCOL_VERSION)])
    finally:
        await transport.close()

@pytest.mark.anyio
async def test_read_resource_honors_session_timeout(grpc_server: None, server_port: int):
    """Test GRPCTransportSession.read_resource() honors session timeout."""
    transport = GRPCTransportSession(
        target=f"127.0.0.1:{server_port}",
        read_timeout_seconds=timedelta(seconds=5),
    )
    read_resource_mock = mock.AsyncMock()
    transport.grpc_stub.ReadResource = read_resource_mock
    resource_content_mock = mock.MagicMock(uri="test://resource", mime_type="text/plain", text="text", blob=None)
    read_resource_mock.return_value = mock.MagicMock(resource=resource_content_mock)

    try:
        with mock.patch.object(
            transport,
            "list_resources",
            mock.AsyncMock(),
        ):
            type(transport._list_resources_cache).is_valid = mock.PropertyMock(return_value=True)
            transport._list_resources_cache._data = types.ListResourcesResult(
                resources=[types.Resource(uri="test://resource", name="test_resource", title="Test Resource", description="A test resource", mimeType="text/plain")]
            )
            await transport.read_resource("test://resource")
            transport.list_resources.assert_not_called()
            read_resource_mock.assert_called_once_with(mock.ANY, timeout=5.0, metadata=[('mcp-resource-uri', 'test://resource'), ('mcp-protocol-version', version.LATEST_PROTOCOL_VERSION)])
    finally:
        await transport.close()

# Split of test_grpc_transport_deadline_exceeded
class DeadlineExceededError(grpc.RpcError):
    def code(self):
        return grpc.StatusCode.DEADLINE_EXCEEDED
    def details(self):
        return "Deadline Exceeded"
deadline_error = DeadlineExceededError()

@pytest.mark.anyio
async def test_list_resources_deadline_exceeded(grpc_server: None, server_port: int):
    """Test ListResources raises timeout error on DEADLINE_EXCEEDED."""
    transport = GRPCTransportSession(target=f"127.0.0.1:{server_port}")
    try:
        with mock.patch.object(
            transport.grpc_stub, "ListResources", side_effect=deadline_error
        ), pytest.raises(McpError) as e:
            await transport.list_resources()
        assert e.value.error.code == types.REQUEST_TIMEOUT
        assert "Timed out" in e.value.error.message
        assert "ListResourcesRequest" in e.value.error.message
    finally:
        await transport.close()

@pytest.mark.anyio
async def test_list_resource_templates_deadline_exceeded(grpc_server: None, server_port: int):
    """Test ListResourceTemplates raises timeout error on DEADLINE_EXCEEDED."""
    transport = GRPCTransportSession(target=f"127.0.0.1:{server_port}")
    try:
        with mock.patch.object(
            transport.grpc_stub, "ListResourceTemplates", side_effect=deadline_error
        ), pytest.raises(McpError) as e:
            await transport.list_resource_templates()
        assert e.value.error.code == types.REQUEST_TIMEOUT
        assert "Timed out" in e.value.error.message
        assert "ListResourceTemplatesRequest" in e.value.error.message
    finally:
        await transport.close()

@pytest.mark.anyio
async def test_read_resource_deadline_exceeded(grpc_server: None, server_port: int):
    """Test ReadResource raises timeout error on DEADLINE_EXCEEDED."""
    transport = GRPCTransportSession(target=f"127.0.0.1:{server_port}")
    try:
        with mock.patch.object(
            transport, "list_resources", mock.AsyncMock()
        ):
            type(transport._list_resources_cache).is_valid = mock.PropertyMock(return_value=True)
            transport._list_resources_cache._data = types.ListResourcesResult(
                resources=[types.Resource(uri="test://resource", name="test_resource", mimeType="text/plain")]
            )
            with mock.patch.object(
                transport.grpc_stub, "ReadResource", side_effect=deadline_error
            ), pytest.raises(McpError) as e:
                await transport.read_resource("test://resource")
        assert e.value.error.code == types.REQUEST_TIMEOUT
        assert "Timed out" in e.value.error.message
        assert "ReadResourceRequest" in e.value.error.message
    finally:
        await transport.close()

@pytest.mark.anyio
async def test_list_tools_deadline_exceeded(grpc_server: None, server_port: int):
    """Test ListTools raises timeout error on DEADLINE_EXCEEDED."""
    transport = GRPCTransportSession(target=f"127.0.0.1:{server_port}")
    try:
        with mock.patch.object(
            transport.grpc_stub, "ListTools", side_effect=deadline_error
        ), pytest.raises(McpError) as e:
            await transport.list_tools()
        assert e.value.error.code == types.REQUEST_TIMEOUT
        assert "Timed out" in e.value.error.message
        assert "ListToolsRequest" in e.value.error.message
    finally:
        await transport.close()

@pytest.mark.anyio
async def test_call_tool_deadline_exceeded(grpc_server: None, server_port: int):
    """Test CallTool raises timeout error on DEADLINE_EXCEEDED."""
    transport = GRPCTransportSession(target=f"127.0.0.1:{server_port}")
    try:
        with mock.patch.object(
            transport.grpc_stub, "CallTool", side_effect=deadline_error
        ), pytest.raises(McpError) as e:
            await transport.call_tool("tool", {})
        assert e.value.error.code == types.REQUEST_TIMEOUT
        assert "Timed out" in e.value.error.message
        assert "CallTool" in e.value.error.message
    finally:
        await transport.close()

@pytest.mark.anyio
async def test_call_tool_list_tools_initial_call(grpc_server: None, server_port: int):
    """Test GRPCTransportSession.call_tool() triggers ListTools on first call."""
    transport = GRPCTransportSession(target=f"127.0.0.1:{server_port}")
    try:
        mock_tool_proto = _create_mock_tool_proto("greet")
        list_tools_response = mock.MagicMock(tools=[mock_tool_proto], ttl=mock.MagicMock(seconds=1, nanos=0))
        list_tools_mock = mock.AsyncMock(return_value=list_tools_response)
        transport.grpc_stub.ListTools = list_tools_mock
        call_tool_response = mock.MagicMock(structured_content={"result": "test"})
        call_tool_mock = mock.Mock()
        call_tool_mock.return_value = MockAsyncStream([call_tool_response])
        transport.grpc_stub.CallTool = call_tool_mock
        # Ensure cache is empty
        transport._list_tool_cache._data = None
        transport._list_tool_cache._expiry = 0

        await transport.call_tool("greet", {"name": "Test"})
        list_tools_mock.assert_called_once()
    finally:
        await transport.close()

@pytest.mark.anyio
async def test_call_tool_list_tools_cache_hit(grpc_server: None, server_port: int):
    """Test GRPCTransportSession.call_tool() uses cache when valid."""
    transport = GRPCTransportSession(target=f"127.0.0.1:{server_port}")
    try:
        mock_tool_proto = _create_mock_tool_proto("greet")
        list_tools_response = mock.MagicMock(tools=[mock_tool_proto], ttl=mock.MagicMock(seconds=1, nanos=0))
        list_tools_mock = mock.AsyncMock(return_value=list_tools_response)
        transport.grpc_stub.ListTools = list_tools_mock
        call_tool_response = mock.MagicMock(structured_content={"result": "test"})
        call_tool_mock = mock.Mock()
        call_tool_mock.return_value = MockAsyncStream([call_tool_response])
        transport.grpc_stub.CallTool = call_tool_mock
        # First call to populate cache
        await transport.call_tool("greet", {"name": "Test"})
        assert list_tools_mock.call_count == 1
        # Second call, should use cache
        await transport.call_tool("greet", {"name": "Test"})
        assert list_tools_mock.call_count == 1
    finally:
        await transport.close()

@pytest.mark.anyio
async def test_call_tool_list_tools_cache_invalidation(grpc_server: None, server_port: int):
    """Test cache invalidation sends notification."""
    message_handler = mock.AsyncMock()
    transport = GRPCTransportSession(
        target=f"127.0.0.1:{server_port}", message_handler=message_handler
    )
    try:
        list_tools_mock = mock.AsyncMock(return_value=mock.MagicMock(tools=[], ttl=mock.MagicMock(seconds=0.1, nanos=0)))
        transport.grpc_stub.ListTools = list_tools_mock
        call_tool_response = mock.MagicMock(structured_content={"result": "test"})
        call_tool_mock = mock.Mock()
        call_tool_mock.return_value = MockAsyncStream([call_tool_response])
        transport.grpc_stub.CallTool = call_tool_mock
        # First call to populate cache
        await transport.call_tool("greet", {"name": "Test"})
        # Wait for cache to expire and notification to be sent
        await asyncio.sleep(0.2)
        message_handler.assert_called_once()
        notification = message_handler.call_args[0][0]
        assert notification.root.method == "notifications/tools/list_changed"
    finally:
        await transport.close()

@pytest.mark.anyio
async def test_call_tool_list_tools_cache_miss(grpc_server: None, server_port: int):
    """Test GRPCTransportSession.call_tool() calls ListTools after cache expiry."""
    transport = GRPCTransportSession(target=f"127.0.0.1:{server_port}")
    try:
        mock_tool_proto_1 = _create_mock_tool_proto("greet")
        list_tools_response_1 = mock.MagicMock(tools=[mock_tool_proto_1], ttl=mock.MagicMock(seconds=0.1, nanos=0))
        list_tools_response_2 = mock.MagicMock(tools=[mock_tool_proto_1], ttl=mock.MagicMock(seconds=1, nanos=0))
        list_tools_mock = mock.AsyncMock(side_effect=[list_tools_response_1, list_tools_response_2])
        transport.grpc_stub.ListTools = list_tools_mock
        call_tool_response = mock.MagicMock(structured_content={"result": "test"})
        call_tool_mock = mock.Mock()
        call_tool_mock.return_value = MockAsyncStream([call_tool_response])
        transport.grpc_stub.CallTool = call_tool_mock
        # Ensure cache is empty
        transport._list_tool_cache._data = None
        transport._list_tool_cache._expiry = 0

        await transport.call_tool("greet", {"name": "Test"})
        assert list_tools_mock.call_count == 1
        await asyncio.sleep(0.2)
        await transport.call_tool("greet", {"name": "Test"})
        assert list_tools_mock.call_count == 2
    finally:
        await transport.close()

@pytest.mark.anyio
@pytest.mark.anyio
async def test_read_resource_grpc_transport_text(grpc_server: None, server_port: int):
    """Test GRPCTransportSession.read_resource() for text resources."""
    transport = GRPCTransportSession(target=f"127.0.0.1:{server_port}")
    try:
        with mock.patch.object(transport, "list_resources", mock.AsyncMock()):
            type(transport._list_resources_cache).is_valid = mock.PropertyMock(return_value=True)
            transport._list_resources_cache._data = types.ListResourcesResult(
                resources=[
                    types.Resource(uri="test://resource", name="test_resource", title="Test Resource", description="A test resource", mimeType="text/plain")
                ]
            )
            read_resource_mock = mock.AsyncMock()
            read_resource_response = mock.MagicMock()
            read_resource_response.resource = [mock.MagicMock(uri="test://resource", mime_type="text/plain", text="test resource content")]
            read_resource_mock.return_value = read_resource_response
            transport.grpc_stub.ReadResource = read_resource_mock

            read_resource_result = await transport.read_resource("test://resource")
            assert read_resource_result is not None
            transport.list_resources.assert_not_called()
        assert len(read_resource_result.contents) == 1
        content = read_resource_result.contents[0]
        assert content.text == "test resource content"
        assert content.mimeType == "text/plain"
    finally:
        await transport.close()

@pytest.mark.anyio
async def test_call_tool_grpc_transport_session_timeout_override(grpc_server: None, server_port: int):
    """Test GRPCTransportSession.call_tool() with session timeout overridden by call timeout."""
    transport = GRPCTransportSession(
        target=f"127.0.0.1:{server_port}",
        read_timeout_seconds=timedelta(seconds=5),
    )
    try:
        call_tool_mock = mock.MagicMock()
        transport.grpc_stub.CallTool = call_tool_mock

        response_mock = mock.MagicMock()
        response_mock.common.HasField.return_value = False
        response_mock.content = []
        response_mock.HasField.return_value = False
        response_mock.is_error = False

        async def aiterator():
            yield response_mock

        with mock.patch(
            "mcp.client.grpc_transport_session.convert.proto_result_to_content"
        ) as mock_convert, mock.patch.object(
            transport, "_validate_tool_result", mock.AsyncMock()
        ):
            mock_convert.return_value = types.CallToolResult(
                content=[types.TextContent(type="text", text="result")]
            )

            # Case 1: session timeout 5s, call_tool timeout 10s -> expect 10s
            call_tool_mock.return_value = aiterator()
            await transport.call_tool(
                "greet",
                {"name": "Test"},
                read_timeout_seconds=timedelta(seconds=10),
            )
            call_tool_mock.assert_called_once_with(mock.ANY, timeout=10.0, metadata=[('mcp-tool-name', 'greet'), ('mcp-protocol-version', transport.negotiated_version)])
    finally:
        await transport.close()

@pytest.mark.anyio
async def test_call_tool_grpc_transport_session_timeout_default(grpc_server: None, server_port: int):
    """Test GRPCTransportSession.call_tool() uses session timeout when call timeout is None."""
    transport = GRPCTransportSession(
        target=f"127.0.0.1:{server_port}",
        read_timeout_seconds=timedelta(seconds=5),
    )
    try:
        call_tool_mock = mock.MagicMock()
        transport.grpc_stub.CallTool = call_tool_mock

        response_mock = mock.MagicMock()
        response_mock.common.HasField.return_value = False
        response_mock.content = []
        response_mock.HasField.return_value = False
        response_mock.is_error = False

        async def aiterator():
            yield response_mock

        with mock.patch(
            "mcp.client.grpc_transport_session.convert.proto_result_to_content"
        ) as mock_convert, mock.patch.object(
            transport, "_validate_tool_result", mock.AsyncMock()
        ):
            mock_convert.return_value = types.CallToolResult(
                content=[types.TextContent(type="text", text="result")]
            )

            # Case 2: session timeout 5s, call_tool timeout None -> expect 5s
            call_tool_mock.return_value = aiterator()
            await transport.call_tool(
                "greet",
                {"name": "Test"},
            )
            call_tool_mock.assert_called_once_with(mock.ANY, timeout=5.0, metadata=[('mcp-tool-name', 'greet'), ('mcp-protocol-version', transport.negotiated_version)])
    finally:
        await transport.close()

@pytest.mark.anyio
async def test_call_tool_grpc_transport_no_session_timeout_with_call_timeout(grpc_server: None, server_port: int):
    """Test GRPCTransportSession.call_tool() with no session timeout but with call timeout."""
    transport_no_session_timeout = GRPCTransportSession(
        target=f"127.0.0.1:{server_port}", 
    )
    try:
        call_tool_mock = mock.MagicMock()
        transport_no_session_timeout.grpc_stub.CallTool = call_tool_mock
        response_mock = mock.MagicMock()
        response_mock.common.HasField.return_value = False
        response_mock.content = []
        response_mock.HasField.return_value = False
        response_mock.is_error = False
        async def aiterator():
            yield response_mock
        with mock.patch(
            "mcp.client.grpc_transport_session.convert.proto_result_to_content"
        ) as mock_convert, mock.patch.object(
            transport_no_session_timeout, "_validate_tool_result", mock.AsyncMock()
        ):
            mock_convert.return_value = types.CallToolResult(
                content=[types.TextContent(type="text", text="result")]
            )
            # Case 3: session timeout None, call_tool timeout 10s -> expect 10s
            call_tool_mock.return_value = aiterator()
            await transport_no_session_timeout.call_tool(
                "greet",
                {"name": "Test"},
                read_timeout_seconds=timedelta(seconds=10),
            )
            call_tool_mock.assert_called_once_with(mock.ANY, timeout=10.0, metadata=[('mcp-tool-name', 'greet'), ('mcp-protocol-version', transport_no_session_timeout.negotiated_version)])
    finally:
        await transport_no_session_timeout.close()

@pytest.mark.anyio
async def test_call_tool_grpc_transport_no_session_timeout_no_call_timeout(grpc_server: None, server_port: int):
    """Test GRPCTransportSession.call_tool() with no session timeout and no call timeout."""
    transport_no_session_timeout = GRPCTransportSession(
        target=f"127.0.0.1:{server_port}", read_timeout_seconds=None
    )
    try:
        call_tool_mock = mock.MagicMock()
        transport_no_session_timeout.grpc_stub.CallTool = call_tool_mock
        response_mock = mock.MagicMock()
        response_mock.common.HasField.return_value = False
        response_mock.content = []
        response_mock.HasField.return_value = False
        response_mock.is_error = False
        async def aiterator():
            yield response_mock
        with mock.patch(
            "mcp.client.grpc_transport_session.convert.proto_result_to_content"
        ) as mock_convert, mock.patch.object(
            transport_no_session_timeout, "_validate_tool_result", mock.AsyncMock()
        ):
            mock_convert.return_value = types.CallToolResult(
                content=[types.TextContent(type="text", text="result")]
            )
            # Case 4: session timeout None, call_tool timeout None -> expect None
            call_tool_mock.return_value = aiterator()
            await transport_no_session_timeout.call_tool(
                "greet",
                {"name": "Test"},
                read_timeout_seconds=None,
            )
            call_tool_mock.assert_called_once_with(mock.ANY, timeout=None, metadata=[('mcp-tool-name', 'greet'), ('mcp-protocol-version', transport_no_session_timeout.negotiated_version)])
    finally:
        await transport_no_session_timeout.close()

@pytest.mark.anyio
async def test_validate_tool_result_validation_error(grpc_server: None, server_port: int):
    """Test _validate_tool_result raises error on ValidationError."""
    transport = GRPCTransportSession(target=f"127.0.0.1:{server_port}")
    try:
        # Mock a tool with a schema that expects a "message" field
        mock_tool_with_schema = types.Tool(
            name="tool_with_schema",
            description="A tool with an output schema",
            inputSchema={},
            outputSchema={"type": "object", "properties": {"message": {"type": "string"}}},
        )
        transport._list_tool_cache.set(
            {"tool_with_schema": mock_tool_with_schema},
            timedelta(seconds=60)
        )

        # Result with structuredContent that does NOT match the schema (missing "message")
        invalid_result = types.CallToolResult(
            content=[],
            structuredContent={"message": 123},
        )

        with pytest.raises(McpError) as excinfo:
            await transport._validate_and_return_result(
                "tool_with_schema", invalid_result
            )

        assert excinfo.value.error.code == types.INTERNAL_ERROR
        expected_message = "Tool result validation failed for \"tool_with_schema\": Invalid structured content returned by tool tool_with_schema: 123 is not of type 'string'"
        assert expected_message in excinfo.value.error.message
        assert "Failed validating 'type' in schema['properties']['message']" in excinfo.value.error.message
    finally:
        await transport.close()

async def mock_call_tool_generator(responses):
    """An async generator to mock CallTool responses."""
    for response in responses:
        if isinstance(response, Exception):
            raise response
        yield response

@pytest.fixture
def mock_grpc_stub(monkeypatch):
    """Fixture to mock the gRPC stub."""
    mock_stub = unittest.mock.Mock()
    monkeypatch.setattr(mcp_pb2_grpc, "McpStub", unittest.mock.Mock(return_value=mock_stub))
    return mock_stub

@pytest.mark.anyio
async def test_call_tool_version_mismatch_retry_success(mock_grpc_stub, monkeypatch, server_port):
    """Test CallTool retries successfully after a version mismatch."""
    session = GRPCTransportSession(target=f"127.0.0.1:{server_port}")
    session.negotiated_version = "v1"
    monkeypatch.setattr(version, "SUPPORTED_PROTOCOL_VERSIONS", ["v1", "v2"])

    # Define the sequence of responses for each CallTool invocation
    e = grpc.RpcError()
    e.code = lambda: grpc.StatusCode.UNIMPLEMENTED
    e.details = lambda: "Unsupported protocol version: v1"
    e.initial_metadata = lambda: [("mcp-protocol-version", "v2")]

    success_response = mcp_pb2.CallToolResponse(is_error=False)
    content_item = mcp_pb2.CallToolResponse.Content()
    content_item.text.text = "Success"
    success_response.content.append(content_item)

    call_count = 0
    def call_tool_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise e
        elif call_count == 2:
            return MockAsyncStream([success_response])
        else:
            raise Exception("Should not be called more than twice")

    mock_grpc_stub.CallTool.side_effect = call_tool_side_effect

    # Mock ListTools for the validation step
    mock_grpc_stub.ListTools = unittest.mock.AsyncMock(return_value=mcp_pb2.ListToolsResponse())

    # Execute CallTool
    result = await session.call_tool("test_tool", {"arg": "value"})

    # Assertions
    assert session.negotiated_version == "v2"  # Version should be updated
    assert mock_grpc_stub.CallTool.call_count == 2
    assert result.isError is False
    assert result.content[0].text == "Success"
    assert mock_grpc_stub.ListTools.called # Ensure list_tools was called for validation
    assert mock_grpc_stub.ListTools.call_count == 1

@pytest.mark.anyio
async def test_call_tool_version_mismatch_retry_failure(mock_grpc_stub, monkeypatch, server_port):
    """Test CallTool raises McpError if version mismatch persists after retries."""
    session = GRPCTransportSession(target=f"127.0.0.1:{server_port}")
    session.negotiated_version = "v1"

    # Mock responses: Fail with version mismatch, offering no compatible version.
    e = grpc.RpcError()
    e.code = lambda: grpc.StatusCode.UNIMPLEMENTED
    e.details = lambda: "Unsupported protocol version: v1"
    e.initial_metadata = lambda: [("mcp-protocol-version", "v3")] # Server suggests v3, client doesn't support

    mock_grpc_stub.CallTool.side_effect = [e] # Only one call expected

    # Execute CallTool and expect McpError
    with pytest.raises(McpError) as excinfo:
        await session.call_tool("test_tool", {"arg": "value"})

    # Assertions
    assert session.negotiated_version == "v1"  # Version should NOT be updated
    assert mock_grpc_stub.CallTool.call_count == 1 # Only one call made
    _args, kwargs = mock_grpc_stub.CallTool.call_args
    metadata = kwargs.get("metadata")
    assert metadata is not None
    assert ("mcp-tool-name", "test_tool") in metadata
    assert ("mcp-protocol-version", "v1") in metadata
    assert excinfo.value.error.message == 'grpc.RpcError - Failed to call tool "test_tool": Unsupported protocol version: v1'
    assert excinfo.value.error.code == -32603 # INTERNAL_ERROR

@pytest.mark.anyio
async def test_call_tool_sends_tool_name_in_metadata(mock_grpc_stub, server_port):
    """Test that CallTool sends mcp-tool-name in metadata."""
    session = GRPCTransportSession(target=f"127.0.0.1:{server_port}")
    tool_name = "test_tool_name"

    # Mock CallTool to return a successful async generator and capture metadata
    mock_grpc_stub.CallTool.return_value = mock_call_tool_generator([mcp_pb2.CallToolResponse()])
    mock_grpc_stub.ListTools = unittest.mock.AsyncMock(return_value=mcp_pb2.ListToolsResponse())

    # Execute CallTool
    try:
        await session.call_tool(tool_name, {"arg": "value"})
    except McpError:
        pytest.fail("CallTool raised an unexpected McpError")

    # Assertions
    mock_grpc_stub.CallTool.assert_called_once()
    _args, kwargs = mock_grpc_stub.CallTool.call_args
    metadata = kwargs.get("metadata")
    assert metadata is not None
    assert ("mcp-tool-name", tool_name) in metadata
    assert ("mcp-protocol-version", session.negotiated_version) in metadata
    assert mock_grpc_stub.ListTools.called

@pytest.mark.anyio
async def test_read_resource_sends_resource_uri_in_metadata(mock_grpc_stub, server_port):
    """Test that ReadResource sends mcp-resource-uri in metadata."""
    session = GRPCTransportSession(target=f"127.0.0.1:{server_port}")
    resource_uri = "test://some/resource"

    # Mock ReadResource to return a successful response and capture metadata
    mock_grpc_stub.ReadResource = unittest.mock.AsyncMock(return_value=mcp_pb2.ReadResourceResponse())

    # Execute ReadResource
    try:
        await session.read_resource(resource_uri)
    except McpError:
        pytest.fail("ReadResource raised an unexpected McpError")

    # Assertions
    mock_grpc_stub.ReadResource.assert_called_once()
    _args, kwargs = mock_grpc_stub.ReadResource.call_args
    metadata = kwargs.get("metadata")
    assert metadata is not None
    assert ("mcp-resource-uri", resource_uri) in metadata
    assert ("mcp-protocol-version", session.negotiated_version) in metadata

@pytest.mark.anyio
async def test_call_unary_rpc_metadata_update_on_retry(mock_grpc_stub, monkeypatch, server_port):
    """Test _call_unary_rpc updates metadata correctly on retry after version mismatch."""
    session = GRPCTransportSession(target=f"127.0.0.1:{server_port}")
    initial_version = "v1"
    new_version = "v2"
    session.negotiated_version = "v1"
    monkeypatch.setattr(version, "SUPPORTED_PROTOCOL_VERSIONS", [initial_version, new_version])

    mock_rpc_method = mock.AsyncMock()
    # First call: Raise UNIMPLEMENTED with new_version in metadata
    e = grpc.RpcError()
    e.code = lambda: grpc.StatusCode.UNIMPLEMENTED
    e.details = lambda: "Unsupported protocol version: v1"
    e.initial_metadata = lambda: [("mcp-protocol-version", new_version)]
    # Second call: Successful response
    mock_rpc_method.side_effect = [e, mock.MagicMock()]

    # We need a dummy request and timeout
    dummy_request = mcp_pb2.ListToolsRequest()
    dummy_timeout = 5.0
    initial_metadata = []

    # Call _call_unary_rpc
    await session._call_unary_rpc(mock_rpc_method, dummy_request, dummy_timeout, metadata=initial_metadata)

    # Assertions
    assert mock_rpc_method.call_count == 2
    # Check metadata in the first call
    _, kwargs1 = mock_rpc_method.call_args_list[0]
    metadata1 = kwargs1.get("metadata")
    assert metadata1 is not None
    assert ("mcp-protocol-version", initial_version) in metadata1

    # Check metadata in the second call
    _, kwargs2 = mock_rpc_method.call_args_list[1]
    metadata2 = kwargs2.get("metadata")
    assert metadata2 is not None
    assert ("mcp-protocol-version", new_version) in metadata2
