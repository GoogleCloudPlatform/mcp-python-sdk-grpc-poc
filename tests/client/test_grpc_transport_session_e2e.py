import asyncio
import socket
from collections.abc import AsyncGenerator
from pydantic import AnyUrl
import base64
import json

from typing import Any, cast
import logging
from datetime import timedelta

import grpc
from pydantic import BaseModel

import pytest
from _pytest.logging import LogCaptureFixture

from mcp.client.grpc_transport_session import GRPCTransportSession
from mcp.shared.exceptions import McpError
from mcp.server.fastmcp.server import Context, FastMCP
from mcp.server.grpc import create_mcp_grpc_server
from mcp import types


def setup_test_server(port: int) -> FastMCP:
    """Set up a FastMCP server for testing."""
    mcp = FastMCP(
        name="Test gRPC Server",
        instructions="A test MCP server for gRPC transport.",
        host="127.0.0.1",
        port=port,
    )

    @mcp.resource("test://resource")
    def test_resource() -> str:
        """A test resource."""
        return "test resource content"

    @mcp.resource("test://blob_resource", mime_type="application/octet-stream")
    def blob_resource() -> bytes:
        """A blob resource."""
        return b"blob data"

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

    @mcp.resource("test://template/{name}", name="template_resource", mime_type="text/plain")
    def template_resource(name: str) -> str:
        """A template resource."""
        return f"Hello, {name}!"

    @mcp.tool()
    def greet(name: str) -> str:
        """A simple greeting tool."""
        greeting = f"Hello, {name}! Welcome to the Simple gRPC Server!"
        return greeting

    @mcp.tool()
    def test_tool(a: int, b: int) -> int:
        """A test tool that adds two numbers."""
        return a + b

    @mcp.tool()
    def failing_tool():
      """A tool that always fails."""
      raise ValueError("This tool always fails")

    @mcp.tool()
    async def blocking_tool():
        """A tool that blocks until cancelled."""
        await asyncio.sleep(10)

    @mcp.tool()
    def get_image() -> types.ImageContent:
      return types.ImageContent(type="image", data=base64.b64encode(b"fake img data").decode("utf-8"), mimeType="image/png")

    @mcp.tool()
    def get_audio() -> types.AudioContent:
      return types.AudioContent(type="audio", data=base64.b64encode(b"fake wav data").decode("utf-8"), mimeType="audio/wav")

    @mcp.tool()
    def get_resource_link() -> types.ResourceLink:
      return types.ResourceLink(name="resourcelink", type="resource_link", uri=AnyUrl("test://example/link"))

    @mcp.tool()
    def get_embedded_text_resource() -> types.EmbeddedResource:
      return types.EmbeddedResource(
          type="resource",
          resource=types.TextResourceContents(
              uri=AnyUrl("test://example/embeddedtext"), mimeType="text/plain", text="some text"
          ),
      )

    @mcp.tool()
    def get_embedded_blob_resource() -> types.EmbeddedResource:
      return types.EmbeddedResource(
          type="resource",
          resource=types.BlobResourceContents(
              uri=AnyUrl("test://example/embeddedblob"), mimeType="application/octet-stream", blob=base64.b64encode(b"blobdata").decode("utf-8")
          ),
      )

    @mcp.tool()
    def get_untyped_object() -> dict: # type: ignore
        class UntypedObject:
            def __str__(self) -> str:
                return "UntypedObject()"
        return {"result": str(UntypedObject())}

    @mcp.tool()
    async def progress_tool(ctx: Context[Any, Any, Any]) -> str:
        """A tool that reports progress."""
        await ctx.report_progress(0.5, 1.0, "halfway")
        return "done"

    @mcp.tool()
    async def progress_tool_non_int_token(ctx: Context[Any, Any, Any]) -> str:
        """A tool that reports progress with non-int token."""
        await ctx.session.send_progress_notification("non-int-token", 0.5, 1.0, "halfway")
        return "done"

    class DictOutput(BaseModel):
        key: str

    @mcp.tool()
    def structured_dict_tool() -> DictOutput:
        """A tool that returns a dict via pydantic model."""
        return DictOutput(key="value")

    return mcp


def setup_empty_test_server(port: int) -> FastMCP:
    """Set up a FastMCP server with no tools for testing."""
    mcp = FastMCP(
        name="Empty Test gRPC Server",
        instructions="A test MCP server with no tools.",
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
async def grpc_server(server_port: int) -> AsyncGenerator[grpc.aio.Server, None]:
    """Start a gRPC server in process."""
    server_instance = setup_test_server(server_port)
    server = await create_mcp_grpc_server(
        target=f"127.0.0.1:{server_port}", mcp_server=server_instance
    )

    yield server

    await server.stop(grace=1)
    # Add a small delay to allow gRPC channels to close
    await asyncio.sleep(0.1)


@pytest.fixture
async def empty_grpc_server(server_port: int) -> AsyncGenerator[grpc.aio.Server, None]:
    """Start a gRPC server in process with no tools."""
    server_instance = setup_empty_test_server(server_port)
    server = await create_mcp_grpc_server(
        target=f"127.0.0.1:{server_port}", mcp_server=server_instance
    )

    yield server

    await server.stop(grace=1)
    # Add a small delay to allow gRPC channels to close
    await asyncio.sleep(0.1)


@pytest.mark.anyio
async def test_setup_test_server_resources(server_port: int) -> None:
    mcp_server: FastMCP = setup_test_server(server_port)
    resource_manager = mcp_server._resource_manager
    assert "test://resource" in resource_manager._resources
    assert "test://blob_resource" in resource_manager._resources
    assert "test://image" in resource_manager._resources
    assert "test://image_bytes" in resource_manager._resources

@pytest.mark.anyio
async def test_list_resources_grpc_transport(grpc_server: grpc.aio.Server, server_port: int) -> None:
    """Test GRPCTransportSession.list_resources()."""
    transport = GRPCTransportSession(target=f"127.0.0.1:{server_port}")
    try:
        list_resources_result = await transport.list_resources()

        assert list_resources_result is not None
        assert len(list_resources_result.resources) == 4
        resources: dict[str, types.Resource] = {r.name: r for r in list_resources_result.resources}
        assert "test_resource" in resources
        assert str(resources["test_resource"].uri) == "test://resource"
        assert "blob_resource" in resources
        assert str(resources["blob_resource"].uri) == "test://blob_resource"
        assert "get_image_as_string" in resources
        assert str(resources["get_image_as_string"].uri) == "test://image"
        assert "get_image_as_bytes" in resources
        assert str(resources["get_image_as_bytes"].uri) == "test://image_bytes"
    finally:
        await transport.close()


@pytest.mark.anyio
async def test_list_resource_templates_grpc_transport(
    grpc_server: grpc.aio.Server, server_port: int
) -> None:
    """Test GRPCTransportSession.list_resource_templates()."""
    transport = GRPCTransportSession(target=f"127.0.0.1:{server_port}")
    try:
        list_resource_templates_result = await transport.list_resource_templates()

        assert list_resource_templates_result is not None
        assert len(list_resource_templates_result.resourceTemplates) == 1
        templates: dict[str, types.ResourceTemplate] = {
            t.name: t for t in list_resource_templates_result.resourceTemplates
        }
        assert "template_resource" in templates
        assert (
            str(templates["template_resource"].uriTemplate)
            == "test://template/{name}"
        )
        assert templates["template_resource"].mimeType == "text/plain"
    finally:
        await transport.close()


@pytest.mark.anyio
async def test_list_resources_grpc_transport_failure(server_port: int) -> None:
    """Test GRPCTransportSession.list_resources() when no server is running."""
    transport = GRPCTransportSession(target=f"127.0.0.1:{server_port + 1}")
    try:
        with pytest.raises(McpError) as e:
            await transport.list_resources()
        assert e.value.error.code == -32603  # types.INTERNAL_ERROR
        assert "grpc.RpcError - Failed to list resources" in e.value.error.message
        assert "StatusCode.UNAVAILABLE" in e.value.error.message
        assert "Connection refused" in e.value.error.message
    finally:
        await transport.close()

@pytest.mark.anyio
async def test_read_resource_grpc_transport_failure(server_port: int) -> None:
    """Test GRPCTransportSession.read_resource() when no server is running."""
    transport = GRPCTransportSession(target=f"127.0.0.1:{server_port + 1}")
    try:
        with pytest.raises(McpError) as e:
            await transport.read_resource(AnyUrl("test://resource"))
        assert e.value.error.code == -32603  # types.INTERNAL_ERROR
        assert "grpc.RpcError - Failed to read resource" in e.value.error.message
        assert "StatusCode.UNAVAILABLE" in e.value.error.message
        assert "Connection refused" in e.value.error.message
    finally:
        await transport.close()


@pytest.mark.anyio
async def test_list_tools_grpc_transport(grpc_server: grpc.aio.Server, server_port: int) -> None:
    """Test GRPCTransportSession.list_tools()."""
    transport = GRPCTransportSession(target=f"127.0.0.1:{server_port}")
    try:
        list_tools_result = await transport.list_tools()

        assert list_tools_result is not None
        assert len(list_tools_result.tools) == 13

        tools_by_name: dict[str, types.Tool] = {tool.name: tool for tool in list_tools_result.tools}

        expected_tools: dict[str, Any] = {
            "greet": {
                "name": "greet",
                "description": "A simple greeting tool.",
                "inputSchema": {
                    "properties": {"name": {"title": "Name", "type": "string"}},
                    "required": ["name"],
                    "title": "greetArguments",
                    "type": "object",
                },
                "outputSchema": {
                    "properties": {"result": {"title": "Result", "type": "string"}},
                    "required": ["result"],
                    "title": "greetOutput",
                    "type": "object",
                },
            },
            "test_tool": {
                "name": "test_tool",
                "description": "A test tool that adds two numbers.",
                "inputSchema": {
                    "properties": {
                        "a": {"title": "A", "type": "integer"},
                        "b": {"title": "B", "type": "integer"},
                    },
                    "required": ["a", "b"],
                    "title": "test_toolArguments",
                    "type": "object",
                },
                "outputSchema": {
                    "properties": {"result": {"title": "Result", "type": "integer"}},
                    "required": ["result"],
                    "title": "test_toolOutput",
                    "type": "object",
                },
            },
            "failing_tool": {
                "name": "failing_tool",
                "description": "A tool that always fails.",
                "inputSchema": {"properties": {}, "title": "failing_toolArguments", "type": "object"},
                "outputSchema": {},
            },
            "blocking_tool": {
                "name": "blocking_tool",
                "description": "A tool that blocks until cancelled.",
                "inputSchema": {"properties": {}, "title": "blocking_toolArguments", "type": "object"},
                "outputSchema": {},
            },
            "get_image": {
                "name": "get_image",
                "description": "",
                "inputSchema": {"properties": {}, "title": "get_imageArguments", "type": "object"},
                "outputSchema": types.ImageContent.model_json_schema(),
            },
            "get_audio": {
                "name": "get_audio",
                "description": "",
                "inputSchema": {"properties": {}, "title": "get_audioArguments", "type": "object"},
                "outputSchema": types.AudioContent.model_json_schema(),
            },
            "get_resource_link": {
                "name": "get_resource_link",
                "description": "",
                "inputSchema": {"properties": {}, "title": "get_resource_linkArguments", "type": "object"},
                "outputSchema": types.ResourceLink.model_json_schema(),
            },
            "get_embedded_text_resource": {
                "name": "get_embedded_text_resource",
                "description": "",
                "inputSchema": {"properties": {}, "title": "get_embedded_text_resourceArguments", "type": "object"},
                "outputSchema": types.EmbeddedResource.model_json_schema(),
            },
            "get_embedded_blob_resource": {
                "name": "get_embedded_blob_resource",
                "description": "",
                "inputSchema": {"properties": {}, "title": "get_embedded_blob_resourceArguments", "type": "object"},
                "outputSchema": types.EmbeddedResource.model_json_schema(),
            },
            "get_untyped_object": {
                "name": "get_untyped_object",
                "description": "",
                "inputSchema": {
                    "properties": {},
                    "title": "get_untyped_objectArguments",
                    "type": "object",
                },
                "outputSchema": {},
            },
            "progress_tool": {
                "name": "progress_tool",
                "description": "A tool that reports progress.",
                "inputSchema": {
                    "properties": {},
                    "title": "progress_toolArguments",
                    "type": "object",
                },
                "outputSchema": {
                    "properties": {"result": {"title": "Result", "type": "string"}},
                    "required": ["result"],
                    "title": "progress_toolOutput",
                    "type": "object",
                },
            },
            "progress_tool_non_int_token": {
                "name": "progress_tool_non_int_token",
                "description": (
                    "A tool that reports progress with non-int token."
                ),
                "inputSchema": {
                    "properties": {},
                    "title": "progress_tool_non_int_tokenArguments",
                    "type": "object",
                },
                "outputSchema": {
                    "properties": {"result": {"title": "Result", "type": "string"}},
                    "required": ["result"],
                    "title": "progress_tool_non_int_tokenOutput",
                    "type": "object",
                },
            },
            "structured_dict_tool": {
                "name": "structured_dict_tool",
                "description": "A tool that returns a dict via pydantic model.",
                "inputSchema": {
                    "properties": {},
                    "title": "structured_dict_toolArguments",
                    "type": "object",
                },
                "outputSchema": {
                    "properties": {"key": {"title": "Key", "type": "string"}},
                    "required": ["key"],
                    "title": "DictOutput",
                    "type": "object",
                },
            },
        }

        assert tools_by_name.keys() == expected_tools.keys()

        for tool_name, tool in tools_by_name.items():
            expected_tool = expected_tools[tool_name]
            assert tool.name == expected_tool["name"]
            assert tool.description == expected_tool["description"]
            assert tool.inputSchema == expected_tool["inputSchema"]
            assert tool.outputSchema == expected_tool["outputSchema"]
    finally:
        await transport.close()


@pytest.mark.anyio
async def test_list_tools_grpc_empty_tools(empty_grpc_server: grpc.aio.Server, server_port: int) -> None:
    """Test GRPCTransportSession.list_tools() with no tools."""
    transport = GRPCTransportSession(target=f"127.0.0.1:{server_port}")
    try:
        list_tools_result = await transport.list_tools()
        assert list_tools_result is not None
        assert len(list_tools_result.tools) == 0
    finally:
        await transport.close()


@pytest.mark.anyio
async def test_list_tools_grpc_transport_failure(server_port: int) -> None:
    """Test GRPCTransportSession.list_tools() when no server is running."""
    transport = GRPCTransportSession(target=f"127.0.0.1:{server_port + 1}")
    try:
        with pytest.raises(McpError) as e:
            await transport.list_tools()
        assert e.value.error.code == -32603  # types.INTERNAL_ERROR
        assert "grpc.RpcError - Failed to list tools" in e.value.error.message
        assert "StatusCode.UNAVAILABLE" in e.value.error.message
        assert "Connection refused" in e.value.error.message
    finally:
        await transport.close()





@pytest.mark.anyio
@pytest.mark.parametrize(
    "tool_name, tool_args, expected_content, expected_structured_content",
    [
        (
            "greet",
            {"name": "World"},
            [{"type": "text", "text": "Hello, World! Welcome to the Simple gRPC Server!"}],
            {"result": "Hello, World! Welcome to the Simple gRPC Server!"},
        ),
        (
            "test_tool",
            {"a": 2, "b": 3},
            [{"type": "text", "text": "5"}],
            {"result": 5},
        ),
        (
            "get_image",
            {},
            [{"type": "image", "data": base64.b64encode(b"fake img data").decode("utf-8"), "mimeType": "image/png"}],
            {'data': 'ZmFrZSBpbWcgZGF0YQ==', 'mimeType': 'image/png', 'annotations': None, '_meta': None, 'type': 'image'}
        ),
        (
            "get_audio",
            {},
            [{"type": "audio", "data": base64.b64encode(b"fake wav data").decode("utf-8"), "mimeType": "audio/wav"}],
            {'data': 'ZmFrZSB3YXYgZGF0YQ==', 'mimeType': 'audio/wav', 'annotations': None, '_meta': None, 'type': 'audio'},
        ),
        (
            "get_resource_link",
            {},
            [{"type": "resource_link", "uri": "test://example/link", "name": "resourcelink"}],
            {'name': 'resourcelink', 'title': None, 'uri': 'test://example/link', 'description': None, 'mimeType': None, 'size': None, 'annotations': None, '_meta': None, 'type': 'resource_link'},
        ),
        (
            "get_embedded_text_resource",
            {},
            [{
                "type": "resource",
                "resource": {"type": "text", "uri": "test://example/embeddedtext", "mimeType": "text/plain", "text": "some text"},
            }],
            {
                "type": "resource",
                "resource": {"uri": "test://example/embeddedtext", "mimeType": "text/plain", "text": "some text", "_meta": None},
                "annotations": None,
                "_meta": None,
            },
        ),
        (
            "get_embedded_blob_resource",
            {},
            [{
                "type": "resource",
                "resource": {"type": "blob", "uri": "test://example/embeddedblob", "mimeType": "application/octet-stream", "blob": base64.b64encode(b"blobdata").decode("utf-8")},
            }],
            {
                "type": "resource",
                "resource": {"uri": "test://example/embeddedblob", "mimeType": "application/octet-stream", "blob": base64.b64encode(b"blobdata").decode("utf-8"), "_meta": None},
                "annotations": None,
                "_meta": None,
            },
        ),
        (
            "get_untyped_object",
            {},
            [{"type": "text", "text": json.dumps({"result": "UntypedObject()"}, indent=2)}],
            None,
        ),
        (
            "structured_dict_tool",
            {},
            [{"type": "text", "text": '{\n  "key": "value"\n}'}],
            {"key": "value"},
        ),
    ],
)
async def test_call_tool_grpc_transport_success(
    grpc_server: grpc.aio.Server,
    server_port: int,
    tool_name: str,
    tool_args: dict[str, Any],
    expected_content: list[dict[str, Any]],
    expected_structured_content: dict[str, Any] | None,
) -> None:
    """Test GRPCTransportSession.call_tool() for successful calls."""
    transport = GRPCTransportSession(target=f"127.0.0.1:{server_port}")
    try:
        result = await transport.call_tool(tool_name, tool_args)
        assert result is not None
        assert not result.isError
        assert len(result.content) == len(expected_content)
        for i, content_block in enumerate(result.content):
            expected: dict[str, Any] = expected_content[i]
            assert content_block.type == expected["type"]
            if content_block.type == "text":
                assert content_block.text == expected["text"]
            elif content_block.type == "image":
                assert base64.b64decode(content_block.data) == base64.b64decode(cast(str, expected["data"]))
                assert content_block.mimeType == expected["mimeType"]
            elif content_block.type == "audio":
                assert content_block.data == expected["data"]
                assert content_block.mimeType == expected["mimeType"]
            elif content_block.type == "resource_link":
                assert str(content_block.uri) == expected["uri"]
                assert content_block.name == expected["name"]
            elif content_block.type == "resource":
                assert str(content_block.resource.uri) == expected["resource"]["uri"]
                assert content_block.resource.mimeType == expected["resource"]["mimeType"]
                if isinstance(content_block.resource, types.TextResourceContents):
                    assert content_block.resource.text == expected["resource"]["text"]
                else: # isinstance(content_block.resource, types.BlobResourceContents)
                    assert content_block.resource.blob == expected["resource"]["blob"]

        if result.structuredContent is not None and expected_structured_content is not None:
            assert result.structuredContent == expected_structured_content
        else:
            assert result.structuredContent is None or result.structuredContent == {}
    finally:
        await transport.close()


@pytest.mark.anyio
async def test_call_tool_grpc_transport_failing_tool(grpc_server: grpc.aio.Server, server_port: int) -> None:
    """Test GRPCTransportSession.call_tool() when the tool raises an exception."""
    transport = GRPCTransportSession(target=f"127.0.0.1:{server_port}")
    try:
        result = await transport.call_tool("failing_tool", {})

        assert result is not None
        assert result.isError
        assert len(result.content) == 1
        content_block = result.content[0]
        assert isinstance(content_block, types.TextContent)
        assert "Error executing tool failing_tool: This tool always fails" in content_block.text
    finally:
        await transport.close()


@pytest.mark.anyio
async def test_call_tool_grpc_transport_tool_timeout(grpc_server: grpc.aio.Server, server_port: int) -> None:
    """Test GRPCTransportSession.call_tool() when tool execution exceeds timeout."""
    transport = GRPCTransportSession(target=f"127.0.0.1:{server_port}")
    try:
        with pytest.raises(McpError) as e:
            await transport.call_tool(
                "blocking_tool", {}, read_timeout_seconds=timedelta(seconds=5)
            )
        assert e.value.error.code == types.REQUEST_TIMEOUT
        assert "Timed out" in e.value.error.message
        assert "CallTool" in e.value.error.message
    finally:
        await transport.close()


@pytest.mark.anyio
async def test_call_tool_grpc_transport_failure(server_port: int) -> None:
    """Test GRPCTransportSession.call_tool() when the transport fails."""
    transport = GRPCTransportSession(target=f"127.0.0.1:{server_port + 1}")
    try:
        with pytest.raises(McpError) as e:
            await transport.call_tool("greet", {"name": "Test"})
        assert e.value.error.code == -32603  # types.INTERNAL_ERROR
        assert "grpc.RpcError - Failed to call tool" in e.value.error.message
        assert "Connection refused" in e.value.error.message
    finally:
        await transport.close()

@pytest.mark.anyio
async def test_call_tool_non_existent_tool(grpc_server: grpc.aio.Server, server_port: int) -> None:
    """Test GRPCTransportSession.call_tool() with a non-existent tool name."""
    transport = GRPCTransportSession(target=f"127.0.0.1:{server_port}")
    try:
        result = await transport.call_tool("non_existent_tool", {})
        assert result is not None
        assert result.isError
        assert len(result.content) == 1
        content_block = result.content[0]
        assert isinstance(content_block, types.TextContent)
        assert "Tool 'non_existent_tool' not found" in content_block.text
    finally:
        await transport.close()

@pytest.mark.anyio
async def test_call_tool_empty_tool_name(grpc_server: grpc.aio.Server, server_port: int) -> None:
    """Test GRPCTransportSession.call_tool() with an empty tool name."""
    transport = GRPCTransportSession(target=f"127.0.0.1:{server_port}")
    try:
        result = await transport.call_tool("", {})
        assert result is not None
        assert result.isError
        assert len(result.content) == 1
        content_block = result.content[0]
        assert isinstance(content_block, types.TextContent)
        assert "Tool '' not found" in content_block.text
    finally:
        await transport.close()

@pytest.mark.anyio
async def test_call_tool_invalid_arguments_missing(grpc_server: grpc.aio.Server, server_port: int) -> None:
    """Test GRPCTransportSession.call_tool() with missing required arguments."""
    transport = GRPCTransportSession(target=f"127.0.0.1:{server_port}")
    try:
        # "greet" tool requires "name"
        result = await transport.call_tool("greet", {})
        assert result is not None
        assert result.isError
        assert len(result.content) == 1
        content_block = result.content[0]
        assert isinstance(content_block, types.TextContent)
        assert "Error executing tool greet" in content_block.text
        assert "1 validation error for greetArguments" in content_block.text
        assert "name" in content_block.text
        assert "Field required" in content_block.text
    finally:
        await transport.close()

@pytest.mark.anyio
async def test_call_tool_invalid_arguments_wrong_type(grpc_server: grpc.aio.Server, server_port: int) -> None:
    """Test GRPCTransportSession.call_tool() with arguments of the wrong type."""
    transport = GRPCTransportSession(target=f"127.0.0.1:{server_port}")
    try:
        # "greet" tool expects "name" to be a string
        result = await transport.call_tool("greet", {"name": 123})
        assert result is not None
        assert result.isError
        assert len(result.content) == 1
        content_block = result.content[0]
        assert isinstance(content_block, types.TextContent)
        assert "Error executing tool greet" in content_block.text
        assert "1 validation error for greetArguments" in content_block.text
        assert "name" in content_block.text
        assert "Input should be a valid string" in content_block.text
    finally:
        await transport.close()

@pytest.mark.anyio
async def test_send_notification_cancel(grpc_server: grpc.aio.Server, server_port: int) -> None:
    """Test GRPCTransportSession.send_notification() for cancellation."""
    transport = GRPCTransportSession(target=f"127.0.0.1:{server_port}")
    try:
        request_id = transport._request_counter + 1
        cancel_notification = types.ClientNotification(
            root=types.CancelledNotification(
                method="notifications/cancelled",
                params=types.CancelledNotificationParams(requestId=request_id),
            )
        )

        call_tool_task = asyncio.create_task(transport.call_tool("blocking_tool", {}))
        await asyncio.sleep(0.2) # give call_tool time to start and populate _running_calls
        await transport.send_notification(cancel_notification)

        with pytest.raises(McpError) as e:
            await call_tool_task
        assert e.value.error.code == types.REQUEST_CANCELLED
        assert 'Tool call "blocking_tool" was cancelled' in e.value.error.message
    finally:
        await transport.close()


@pytest.mark.anyio
async def test_call_tool_with_progress_callback(grpc_server: grpc.aio.Server, server_port: int) -> None:
    """Test GRPCTransportSession.call_tool() with progress callback."""
    transport = GRPCTransportSession(target=f"127.0.0.1:{server_port}")
    progress_data: list[tuple[float, float | None, str | None]] = []

    async def progress_callback(
        progress: float, total: float | None, message: str | None
    ) -> None:
        progress_data.append((progress, total, message))

    try:
        result = await transport.call_tool(
            "progress_tool", {}, progress_callback=progress_callback
        )
        assert result is not None
        assert not result.isError
        content_block = result.content[0]
        assert isinstance(content_block, types.TextContent)
        assert content_block.text == "done"
        assert progress_data == [(0.5, 1.0, "halfway")]
    finally:
        await transport.close()


@pytest.mark.anyio
async def test_call_tool_with_non_int_token_progress(
    grpc_server: grpc.aio.Server, server_port: int, caplog: LogCaptureFixture
) -> None:
    """Test GRPCTransportSession.call_tool() with progress callback."""
    transport = GRPCTransportSession(target=f"127.0.0.1:{server_port}")
    progress_data: list[tuple[float, float | None, str | None]] = []

    async def progress_callback(
        progress: float, total: float | None, message: str | None
    ) -> None:
        progress_data.append((progress, total, message))

    try:
        caplog.set_level(logging.WARNING)
        result = await transport.call_tool(
            "progress_tool_non_int_token", {}, progress_callback=progress_callback
        )
        assert result is not None
        assert not result.isError
        content_block = result.content[0]
        assert isinstance(content_block, types.TextContent)
        assert content_block.text == "done"
        assert progress_data == []
        assert "Progress token is not an integer: non-int-token" in caplog.text
    finally:
        await transport.close()

@pytest.mark.anyio
async def test_read_resource_non_existent_uri(grpc_server: grpc.aio.Server, server_port: int) -> None:
    """Test GRPCTransportSession.read_resource() with a non-existent URI."""
    transport = GRPCTransportSession(target=f"127.0.0.1:{server_port}")
    try:
        with pytest.raises(McpError) as e:
            await transport.read_resource(AnyUrl("test://nonexistent"))
        assert e.value.error.code == -32002  # types.NOT_FOUND
        assert 'Resource test://nonexistent not found.' in e.value.error.message
    finally:
        await transport.close()

@pytest.mark.anyio
async def test_read_resource_empty_uri(grpc_server: grpc.aio.Server, server_port: int) -> None:
    """Test GRPCTransportSession.read_resource() with an empty URI."""
    transport = GRPCTransportSession(target=f"127.0.0.1:{server_port}")
    try:
        with pytest.raises(McpError) as e:
            await transport.read_resource("")
        assert e.value.error.code == -32002  # types.NOT_FOUND
        assert 'Resource  not found.' in e.value.error.message
    finally:
        await transport.close()
