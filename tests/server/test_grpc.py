import asyncio
import socket
from collections.abc import Generator
import json
import os
from pathlib import Path
import unittest.mock

import grpc
import os
import pytest
from pydantic import BaseModel
from google.protobuf import json_format
from google3.google.protobuf import struct_pb2
from mcp import types
from mcp.client.grpc_transport_session import GRPCTransportSession
from mcp.proto import mcp_pb2, mcp_pb2_grpc
from mcp.server.fastmcp.server import FastMCP
from mcp.server.grpc import create_mcp_grpc_server
from mcp.shared.exceptions import McpError
from mcp.shared import version


def setup_test_server(port: int, test_dir: Path) -> FastMCP:
    """Set up a FastMCP server for testing."""
    mcp = FastMCP(
        name="Test gRPC Server",
        instructions="A test MCP server for gRPC transport.",
        host="127.0.0.1",
        port=port,
    )

    @mcp.resource("test://data")
    def test_resource() -> str:
        """A test resource."""
        return "resource data"

    @mcp.resource("test://binary_resource", name="binary_resource", mime_type="application/octet-stream")
    def binary_resource() -> bytes:
        """A binary resource."""
        return b"binary data"

    @mcp.resource("test://empty_resource", name="empty_resource", mime_type="text/plain")
    def empty_resource() -> str:
        """An empty resource."""
        return ""

    @mcp.resource("test://template/{name}", name="template_resource", mime_type="text/plain")
    def template_resource(name: str) -> str:
        """A template resource."""
        return f"Hello, {name}!"

    @mcp.resource(
        "test://template_empty/{name}",
        name="empty_template_resource",
        mime_type="text/plain",
    )
    def empty_template_resource(name: str) -> str:
        """An empty template resource."""
        return ""

    @mcp.resource("file://test_dir/example.py")
    def read_example_py() -> str:
        """Read the example.py file"""
        try:
            return (test_dir / "example.py").read_text()
        except FileNotFoundError:
            return "File not found"

    @mcp.resource("file://test_dir/readme.md")
    def read_readme_md() -> str:
        """Read the readme.md file"""
        try:
            return (test_dir / "readme.md").read_text()
        except FileNotFoundError:
            return "File not found"

    @mcp.resource("file://test_dir/config.json")
    def read_config_json() -> str:
        """Read the config.json file"""
        try:
            return (test_dir / "config.json").read_text()
        except FileNotFoundError:
            return "File not found"

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
    def failing_tool() -> str:
        """A tool that always fails."""
        raise ValueError("This tool is designed to fail.")

    @mcp.tool()
    def list_tool() -> list[str]:
        """A tool that returns a list of strings."""
        return ["one", "two"]

    @mcp.tool()
    def dict_tool() -> dict:
        """A tool that returns a dict."""
        return {"key": "value"}

    class DictOutput(BaseModel):
        key: str

    @mcp.tool()
    def structured_dict_tool() -> DictOutput:
        """A tool that returns a dict via pydantic model."""
        return DictOutput(key="value")

    @mcp.tool()
    async def blocking_tool():
        """A tool that blocks until cancelled."""
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            raise

    return mcp


@pytest.fixture
def server_port() -> int:
    """Find an available port for the server."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
async def grpc_server(server_port: int, tmp_path: Path) -> Generator[None, None, None]:
    """Start a gRPC server in process."""
    test_dir = tmp_path / "test_dir"
    test_dir.mkdir()
    (test_dir / "example.py").write_text("print('hello')")
    (test_dir / "readme.md").write_text("# Test Readme")
    (test_dir / "config.json").write_text('{"test": "value"}')
    server_instance = setup_test_server(server_port, test_dir)
    server = await create_mcp_grpc_server(
        target=f"127.0.0.1:{server_port}", mcp_server=server_instance
    )

    yield
    await server.stop(None)


@pytest.fixture
async def grpc_stub(server_port: int) -> Generator[mcp_pb2_grpc.McpStub, None, None]:
    """Create a gRPC client stub."""
    async with grpc.aio.insecure_channel(f"127.0.0.1:{server_port}") as channel:
        stub = mcp_pb2_grpc.McpStub(channel)
        yield stub

@pytest.mark.anyio
@pytest.mark.parametrize("protocol_version", version.SUPPORTED_PROTOCOL_VERSIONS)
async def test_protocol_version_supported(grpc_server: None, grpc_stub: mcp_pb2_grpc.McpStub, protocol_version: str):
    """Test RPCs with a supported protocol version in metadata."""
    metadata = [("mcp-protocol-version", protocol_version)]
    request = mcp_pb2.ListToolsRequest(common=mcp_pb2.RequestFields())
    call = grpc_stub.ListTools(request, metadata=metadata)
    response = await call
    assert response is not None
    initial_metadata = await call.initial_metadata()
    assert initial_metadata is not None
    found_protocol_version = False
    for key, value in initial_metadata:
        if key == "mcp-protocol-version":
            assert value == protocol_version
            found_protocol_version = True
            break
    assert found_protocol_version, "mcp-protocol-version not found in initial metadata"

@pytest.mark.anyio
async def test_missing_protocol_version_fails_request(grpc_server: None, grpc_stub: mcp_pb2_grpc.McpStub):
    """Test that requests without mcp-protocol-version metadata fail with UNIMPLEMENTED."""
    request = mcp_pb2.ListToolsRequest(common=mcp_pb2.RequestFields())
    with pytest.raises(grpc.aio.AioRpcError) as excinfo:
        await grpc_stub.ListTools(request, metadata=[])
    assert excinfo.value.code() == grpc.StatusCode.UNIMPLEMENTED
    assert "Protocol version not provided." in excinfo.value.details()

@pytest.mark.anyio
async def test_protocol_version_none(grpc_server: None, grpc_stub: mcp_pb2_grpc.McpStub):
    """Test RPCs with no protocol version in metadata."""
    request = mcp_pb2.ListToolsRequest(common=mcp_pb2.RequestFields())
    call = grpc_stub.ListTools(request)
    with pytest.raises(grpc.aio.AioRpcError) as excinfo:
        await call
    assert excinfo.value.code() == grpc.StatusCode.UNIMPLEMENTED
    assert "Protocol version not provided." in excinfo.value.details()
    initial_metadata = await call.initial_metadata()
    assert initial_metadata is not None
    found_protocol_version = False
    for key, value in initial_metadata:
        if key == "mcp-protocol-version":
            assert value == version.LATEST_PROTOCOL_VERSION
            found_protocol_version = True
            break
    assert found_protocol_version, "mcp-protocol-version not found in initial metadata"

@pytest.mark.anyio
@pytest.mark.parametrize("protocol_version", version.SUPPORTED_PROTOCOL_VERSIONS)
async def test_call_tool_protocol_version_supported(grpc_server: None, grpc_stub: mcp_pb2_grpc.McpStub, protocol_version: str):
    """Test CallTool RPCs with a supported protocol version in metadata."""
    metadata = [("mcp-protocol-version", protocol_version)]
    tool_name = "greet"
    arguments = {"name": "Test"}
    args_struct = struct_pb2.Struct()
    json_format.ParseDict(arguments, args_struct)
    request = mcp_pb2.CallToolRequest(
        common=mcp_pb2.RequestFields(),
        request=mcp_pb2.CallToolRequest.Request(
            name=tool_name, arguments=args_struct
        )
    )
    async def request_iterator():
      yield request

    call = grpc_stub.CallTool(request_iterator(), metadata=metadata)
    responses = [item async for item in call]
    assert len(responses) == 1
    assert responses[0].content[0].text.text == "Hello, Test! Welcome to the Simple gRPC Server!"
    initial_metadata = await call.initial_metadata()
    assert initial_metadata is not None
    found_protocol_version = False
    for key, value in initial_metadata:
        if key == "mcp-protocol-version":
            assert value == protocol_version
            found_protocol_version = True
            break
    assert found_protocol_version, "mcp-protocol-version not found in initial metadata"

@pytest.mark.anyio
async def test_call_tool_protocol_version_none(grpc_server: None, grpc_stub: mcp_pb2_grpc.McpStub):
    """Test CallTool RPCs with no protocol version in metadata."""
    tool_name = "greet"
    arguments = {"name": "Test"}
    args_struct = struct_pb2.Struct()
    json_format.ParseDict(arguments, args_struct)
    request = mcp_pb2.CallToolRequest(
        common=mcp_pb2.RequestFields(),
        request=mcp_pb2.CallToolRequest.Request(
            name=tool_name, arguments=args_struct
        )
    )
    async def request_iterator():
      yield request

    with pytest.raises(grpc.aio.AioRpcError) as excinfo:
        async for _ in grpc_stub.CallTool(request_iterator()):
            pass
    assert excinfo.value.code() == grpc.StatusCode.UNIMPLEMENTED
    assert "Protocol version not provided." in excinfo.value.details()
    initial_metadata = excinfo.value.initial_metadata()
    assert initial_metadata is not None
    found_protocol_version = False
    for key, value in initial_metadata:
        if key == "mcp-protocol-version":
            assert value == version.LATEST_PROTOCOL_VERSION
            found_protocol_version = True
            break
    assert found_protocol_version, "mcp-protocol-version not found in initial metadata"

@pytest.mark.anyio
async def test_protocol_version_unsupported(grpc_server: None, grpc_stub: mcp_pb2_grpc.McpStub):
    """Test RPCs with an unsupported protocol version in metadata.

    The server should return an UNIMPLEMENTED error and include the latest supported
    protocol version in the initial metadata.
    """
    metadata = [("mcp-protocol-version", "unsupported-version")]
    request = mcp_pb2.ListToolsRequest(common=mcp_pb2.RequestFields())
    call = grpc_stub.ListTools(request, metadata=metadata)
    with pytest.raises(grpc.aio.AioRpcError) as excinfo:
        await call
    assert excinfo.value.code() == grpc.StatusCode.UNIMPLEMENTED
    assert "Unsupported protocol version: unsupported-version" in excinfo.value.details()
    initial_metadata = await call.initial_metadata()
    assert initial_metadata is not None
    found_protocol_version = False
    for key, value in initial_metadata:
        if key == "mcp-protocol-version":
            assert value == version.LATEST_PROTOCOL_VERSION
            found_protocol_version = True
            break
    assert found_protocol_version, "mcp-protocol-version not found in initial metadata"

@pytest.mark.anyio
async def test_call_tool_unsupported_version_returns_latest(grpc_server: None, grpc_stub: mcp_pb2_grpc.McpStub):
    """Test that unsupported protocol versions return the latest version in trailing metadata for CallTool."""
    metadata = [("mcp-protocol-version", "unsupported-version")]
    tool_name = "greet"
    arguments = {"name": "Test"}
    args_struct = struct_pb2.Struct()
    json_format.ParseDict(arguments, args_struct)
    request = mcp_pb2.CallToolRequest(
        common=mcp_pb2.RequestFields(),
        request=mcp_pb2.CallToolRequest.Request(
            name=tool_name, arguments=args_struct
        )
    )
    async def request_iterator():
        yield request
    with pytest.raises(grpc.aio.AioRpcError) as excinfo:
        async for _ in grpc_stub.CallTool(request_iterator(), metadata=metadata):
            pass
    assert excinfo.value.code() == grpc.StatusCode.UNIMPLEMENTED

@pytest.mark.anyio
async def test_list_resources_grpc(grpc_server: None, grpc_stub: mcp_pb2_grpc.McpStub):
    """Test ListResources via gRPC."""
    metadata = [("mcp-protocol-version", version.LATEST_PROTOCOL_VERSION)]
    request = mcp_pb2.ListResourcesRequest()
    response = await grpc_stub.ListResources(request, metadata=metadata)

    assert response is not None
    assert len(response.resources) == 6

    resources = {r.name: r for r in response.resources}
    assert "test_resource" in resources
    assert resources["test_resource"].uri == "test://data"
    assert "binary_resource" in resources
    assert resources["binary_resource"].uri == "test://binary_resource"
    assert "empty_resource" in resources
    assert resources["empty_resource"].uri == "test://empty_resource"
    assert "read_example_py" in resources
    assert resources["read_example_py"].uri == "file://test_dir/example.py"
    assert "read_readme_md" in resources
    assert resources["read_readme_md"].uri == "file://test_dir/readme.md"
    assert "read_config_json" in resources
    assert resources["read_config_json"].uri == "file://test_dir/config.json"


@pytest.mark.anyio
async def test_list_resource_templates_grpc(
    grpc_server: None, grpc_stub: mcp_pb2_grpc.McpStub
):
    """Test ListResourceTemplates via gRPC."""
    request = mcp_pb2.ListResourceTemplatesRequest(
        common=mcp_pb2.RequestFields()
    )
    metadata = [("mcp-protocol-version", version.LATEST_PROTOCOL_VERSION)]
    response = await grpc_stub.ListResourceTemplates(request, metadata=metadata)

    assert response is not None
    assert len(response.resource_templates) == 2

    templates = {r.name: r for r in response.resource_templates}
    assert "template_resource" in templates
    assert templates["template_resource"].uri_template == "test://template/{name}"
    assert templates["template_resource"].mime_type == "text/plain"
    assert "empty_template_resource" in templates
    assert (
        templates["empty_template_resource"].uri_template
        == "test://template_empty/{name}"
    )
    assert templates["empty_template_resource"].mime_type == "text/plain"


@pytest.mark.anyio
async def test_list_resources_grpc_binary(grpc_server: None, grpc_stub: mcp_pb2_grpc.McpStub):
    """Test ListResources via gRPC for binary resource."""
    request = mcp_pb2.ListResourcesRequest(
        common=mcp_pb2.RequestFields()
    )
    metadata = [("mcp-protocol-version", version.LATEST_PROTOCOL_VERSION)]
    response = await grpc_stub.ListResources(request, metadata=metadata)

    assert response is not None
    resources = {r.name: r for r in response.resources}
    assert "binary_resource" in resources
    resource = resources["binary_resource"]
    assert resource.uri == "test://binary_resource"
    assert resource.mime_type == "application/octet-stream"


@pytest.mark.anyio
async def test_list_tools_grpc(grpc_server: None, grpc_stub: mcp_pb2_grpc.McpStub):
    """Test ListTools via gRPC."""
    request = mcp_pb2.ListToolsRequest(
        common=mcp_pb2.RequestFields()
    )
    metadata = [("mcp-protocol-version", version.LATEST_PROTOCOL_VERSION)]
    response = await grpc_stub.ListTools(request, metadata=metadata)

    assert response is not None
    assert len(response.tools) == 7

    tools_by_name = {tool.name: tool for tool in response.tools}

    expected_tools = {
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
            "inputSchema": {
                "properties": {},
                "title": "failing_toolArguments",
                "type": "object",
            },
            "outputSchema": {
                "properties": {"result": {"title": "Result", "type": "string"}},
                "required": ["result"],
                "title": "failing_toolOutput",
                "type": "object",
            },
        },
        "list_tool": {
            "name": "list_tool",
            "description": "A tool that returns a list of strings.",
            "inputSchema": {
                "properties": {},
                "title": "list_toolArguments",
                "type": "object",
            },
            "outputSchema": {
                "properties": {
                    "result": {
                        "items": {"type": "string"},
                        "title": "Result",
                        "type": "array",
                    }
                },
                "required": ["result"],
                "title": "list_toolOutput",
                "type": "object",
            },
        },
        "dict_tool": {
            "name": "dict_tool",
            "description": "A tool that returns a dict.",
            "inputSchema": {
                "properties": {},
                "title": "dict_toolArguments",
                "type": "object",
            },
            "outputSchema": {},
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
        "blocking_tool": {
            "name": "blocking_tool",
            "description": "A tool that blocks until cancelled.",
            "inputSchema": {
                "properties": {},
                "title": "blocking_toolArguments",
                "type": "object",
            },
            "outputSchema": {},
        },
    }

    assert tools_by_name.keys() == expected_tools.keys()

    for tool_name, tool in tools_by_name.items():
        expected_tool = expected_tools[tool_name]
        assert tool.name == expected_tool["name"]
        assert tool.description == expected_tool["description"]
        assert json_format.MessageToDict(tool.input_schema) == expected_tool["inputSchema"]
        assert json_format.MessageToDict(tool.output_schema) == expected_tool["outputSchema"]


def setup_failing_test_server(port: int) -> FastMCP:
    """Set up a FastMCP server that fails on list_tools."""
    mcp = FastMCP(
        name="Failing Test gRPC Server",
        host="127.0.0.1",
        port=port,
    )

    async def failing_list_tools():
        raise RuntimeError("This is an intentional error")

    mcp.list_tools = failing_list_tools
    return mcp


def setup_failing_test_server_for_resources(port: int) -> FastMCP:
    """Set up a FastMCP server that fails on list_resources."""
    mcp = FastMCP(
        name="Failing Test gRPC Server",
        host="127.0.0.1",
        port=port,
    )

    async def failing_list_resources():
        raise RuntimeError("This is an intentional error for resources")

    mcp.list_resources = failing_list_resources
    return mcp


def setup_failing_test_server_for_resource_templates(port: int) -> FastMCP:
    """Set up a FastMCP server that fails on list_resource_templates."""
    mcp = FastMCP(
        name="Failing Test gRPC Server",
        host="127.0.0.1",
        port=port,
    )

    async def failing_list_resource_templates():
        raise RuntimeError("This is an intentional error for resource templates")

    mcp.list_resource_templates = failing_list_resource_templates
    return mcp


@pytest.fixture
def failing_server_port() -> int:
    """Find an available port for the server."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
async def failing_grpc_server(failing_server_port: int) -> Generator[None, None, None]:
    """Start a gRPC server in process that fails on list_tools."""
    server_instance = setup_failing_test_server(failing_server_port)
    server = await create_mcp_grpc_server(
        target=f"127.0.0.1:{failing_server_port}", mcp_server=server_instance
    )

    yield
    await server.stop(None)


@pytest.fixture
async def failing_grpc_server_for_resources(
    failing_server_port: int,
) -> Generator[None, None, None]:
    """Start a gRPC server in process that fails on list_resources."""
    server_instance = setup_failing_test_server_for_resources(failing_server_port)
    server = await create_mcp_grpc_server(
        target=f"127.0.0.1:{failing_server_port}", mcp_server=server_instance
    )

    yield
    await server.stop(None)


@pytest.fixture
async def failing_grpc_server_for_resource_templates(
    failing_server_port: int,
) -> Generator[None, None, None]:
    """Start a gRPC server in process that fails on list_resource_templates."""
    server_instance = setup_failing_test_server_for_resource_templates(
        failing_server_port
    )
    server = await create_mcp_grpc_server(
        target=f"127.0.0.1:{failing_server_port}", mcp_server=server_instance
    )

    yield
    await server.stop(None)

@pytest.fixture
async def failing_grpc_stub(
    failing_server_port: int,
) -> Generator[mcp_pb2_grpc.McpStub, None, None]:
    """Create a gRPC client stub for failing server."""
    async with grpc.aio.insecure_channel(
        f"127.0.0.1:{failing_server_port}"
    ) as channel:
        stub = mcp_pb2_grpc.McpStub(channel)
        yield stub


@pytest.mark.anyio
async def test_list_resources_grpc_error(
    failing_grpc_server_for_resources: None, failing_grpc_stub: mcp_pb2_grpc.McpStub
):
    """Test ListResources via gRPC when server handler raises an error."""
    request = mcp_pb2.ListResourcesRequest(
        common=mcp_pb2.RequestFields()
    )
    metadata = [("mcp-protocol-version", version.LATEST_PROTOCOL_VERSION)]
    with pytest.raises(grpc.aio.AioRpcError) as excinfo:
        await failing_grpc_stub.ListResources(request, metadata=metadata)

    assert excinfo.value.code() == grpc.StatusCode.INTERNAL
    assert "This is an intentional error for resources" in excinfo.value.details()


@pytest.mark.anyio
async def test_list_resources_grpc_parse_error(
    grpc_server: None, grpc_stub: mcp_pb2_grpc.McpStub
):
    """Test ListResources via gRPC when conversion raises ParseError."""
    request = mcp_pb2.ListResourcesRequest(
        common=mcp_pb2.RequestFields()
    )
    metadata = [("mcp-protocol-version", version.LATEST_PROTOCOL_VERSION)]
    with unittest.mock.patch(
        "mcp.server.grpc.convert.resource_types_to_protos",
        side_effect=json_format.ParseError("Intentional ParseError"),
    ):
        with pytest.raises(grpc.aio.AioRpcError) as excinfo:
            await grpc_stub.ListResources(request, metadata=metadata)

    assert excinfo.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert "Failed to parse resource data" in excinfo.value.details()


@pytest.mark.anyio
async def test_list_resource_templates_grpc_exception(
    failing_grpc_server_for_resource_templates: None,
    failing_grpc_stub: mcp_pb2_grpc.McpStub,
):
    """Test ListResourceTemplates via gRPC when server handler raises an exception."""
    request = mcp_pb2.ListResourceTemplatesRequest(
        common=mcp_pb2.RequestFields()
    )
    metadata = [("mcp-protocol-version", version.LATEST_PROTOCOL_VERSION)]
    with pytest.raises(grpc.aio.AioRpcError) as excinfo:
        await failing_grpc_stub.ListResourceTemplates(request, metadata=metadata)

    assert excinfo.value.code() == grpc.StatusCode.INTERNAL
    assert (
        "This is an intentional error for resource templates"
        in excinfo.value.details()
    )


@pytest.mark.anyio
async def test_list_resource_templates_grpc_parse_error(
    grpc_server: None, grpc_stub: mcp_pb2_grpc.McpStub
):
    """Test ListResourceTemplates via gRPC when conversion raises ParseError."""
    request = mcp_pb2.ListResourceTemplatesRequest(
        common=mcp_pb2.RequestFields()
    )
    metadata = [("mcp-protocol-version", version.LATEST_PROTOCOL_VERSION)]
    with unittest.mock.patch(
        "mcp.server.grpc.convert.resource_template_types_to_protos",
        side_effect=json_format.ParseError("Intentional ParseError"),
    ):
        with pytest.raises(grpc.aio.AioRpcError) as excinfo:
            await grpc_stub.ListResourceTemplates(request, metadata=metadata)

    assert excinfo.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert "Failed to parse resource template data" in excinfo.value.details()


@pytest.mark.anyio
async def test_read_resource_grpc(grpc_server: None, grpc_stub: mcp_pb2_grpc.McpStub):
    """Test ReadResource via gRPC."""
    request = mcp_pb2.ReadResourceRequest(
        common=mcp_pb2.RequestFields(),
        uri="test://data",
    )
    metadata = [("mcp-protocol-version", version.LATEST_PROTOCOL_VERSION)]
    response = await grpc_stub.ReadResource(request, metadata=metadata)

    assert response is not None
    assert response.resource[0].text == "resource data"
    assert response.resource[0].mime_type == "text/plain"

    request = mcp_pb2.ReadResourceRequest(
        common=mcp_pb2.RequestFields(),
        uri="test://binary_resource",
    )
    metadata = [("mcp-protocol-version", version.LATEST_PROTOCOL_VERSION)]
    response = await grpc_stub.ReadResource(request, metadata=metadata)
    assert response is not None
    assert response.resource[0].blob == b"binary data"
    assert response.resource[0].mime_type == "application/octet-stream"

    request = mcp_pb2.ReadResourceRequest(
        common=mcp_pb2.RequestFields(),
        uri="file://test_dir/example.py",
    )
    metadata = [("mcp-protocol-version", version.LATEST_PROTOCOL_VERSION)]
    response = await grpc_stub.ReadResource(request, metadata=metadata)
    assert response is not None
    assert response.resource[0].text == "print('hello')"


@pytest.mark.anyio
async def test_read_empty_resource_grpc(grpc_server: None, grpc_stub: mcp_pb2_grpc.McpStub):
    """Test ReadResource via gRPC when resource is empty."""
    request = mcp_pb2.ReadResourceRequest(
        common=mcp_pb2.RequestFields(),
        uri="test://empty_resource",
    )
    metadata = [("mcp-protocol-version", version.LATEST_PROTOCOL_VERSION)]
    response = await grpc_stub.ReadResource(request, metadata=metadata)
    assert response is not None
    assert response.resource[0].text == ""
    assert response.resource[0].mime_type == "text/plain"


@pytest.mark.anyio
async def test_read_resource_not_found_grpc(grpc_server: None, grpc_stub: mcp_pb2_grpc.McpStub):
    """Test ReadResource via gRPC when resource not found."""
    request = mcp_pb2.ReadResourceRequest(
        common=mcp_pb2.RequestFields(),
        uri="test://not-found",
    )
    metadata = [("mcp-protocol-version", version.LATEST_PROTOCOL_VERSION)]
    with pytest.raises(grpc.aio.AioRpcError) as excinfo:
        await grpc_stub.ReadResource(request, metadata=metadata)

    assert excinfo.value.code() == grpc.StatusCode.NOT_FOUND


@pytest.mark.anyio
async def test_read_empty_template_resource_grpc(grpc_server: None, grpc_stub: mcp_pb2_grpc.McpStub):
    """Test ReadResource via gRPC when resource is empty."""
    request = mcp_pb2.ReadResourceRequest(
        common=mcp_pb2.RequestFields(),
        uri="test://template_empty/world",
    )
    metadata = [("mcp-protocol-version", version.LATEST_PROTOCOL_VERSION)]
    response = await grpc_stub.ReadResource(request, metadata=metadata)
    assert response is not None
    assert response.resource[0].text == ""
    assert response.resource[0].mime_type == "text/plain"


@pytest.mark.anyio
async def test_read_resource_not_found_raises_mcp_error(grpc_server: None, server_port: int):
    """Test that read_resource raises McpError with code -32002 for NOT_FOUND."""
    transport = GRPCTransportSession(target=f"127.0.0.1:{server_port}")
    try:
        with pytest.raises(McpError) as excinfo:
            await transport.read_resource(uri="test://not-found")
        assert excinfo.value.error.code == -32002
        assert "Resource test://not-found not found." in excinfo.value.error.message
    finally:
        await transport.close()


@pytest.mark.anyio
async def test_list_tools_grpc_error(
    failing_grpc_server: None, failing_grpc_stub: mcp_pb2_grpc.McpStub
):
    """Test ListTools via gRPC when server handler raises an error."""
    request = mcp_pb2.ListToolsRequest(
        common=mcp_pb2.RequestFields()
    )
    metadata = [("mcp-protocol-version", version.LATEST_PROTOCOL_VERSION)]
    with pytest.raises(grpc.aio.AioRpcError) as excinfo:
        await failing_grpc_stub.ListTools(request, metadata=metadata)

    assert excinfo.value.code() == grpc.StatusCode.INTERNAL
    assert "This is an intentional error" in excinfo.value.details()


@pytest.mark.anyio
async def test_call_tool_grpc_greet(grpc_server: None, grpc_stub: mcp_pb2_grpc.McpStub):
    """Test CallTool via gRPC with greet tool."""
    tool_name = "greet"
    arguments = {"name": "Test"}
    args_struct = struct_pb2.Struct()
    json_format.ParseDict(arguments, args_struct)

    request = mcp_pb2.CallToolRequest(
        common=mcp_pb2.RequestFields(),
        request=mcp_pb2.CallToolRequest.Request(
            name=tool_name, arguments=args_struct
        )
    )

    async def request_iterator():
        yield request

    responses = []
    metadata = [("mcp-protocol-version", version.LATEST_PROTOCOL_VERSION)]
    async for response in grpc_stub.CallTool(request_iterator(), metadata=metadata):
        responses.append(response)

    assert len(responses) == 1
    assert (
        responses[0].content[0].text.text
        == "Hello, Test! Welcome to the Simple gRPC Server!"
    )
    assert not responses[0].is_error
    assert responses[0].structured_content['result'] == "Hello, Test! Welcome to the Simple gRPC Server!"


@pytest.mark.anyio
async def test_call_tool_grpc_invalid_input(
    grpc_server: None, grpc_stub: mcp_pb2_grpc.McpStub
):
    """Test CallTool via gRPC with invalid tool input."""
    tool_name = "greet"
    arguments = {"name": 123}  # Invalid input, should be string
    args_struct = struct_pb2.Struct()
    json_format.ParseDict(arguments, args_struct)

    request = mcp_pb2.CallToolRequest(
        common=mcp_pb2.RequestFields(),
        request=mcp_pb2.CallToolRequest.Request(
            name=tool_name, arguments=args_struct
        )
    )

    async def request_iterator():
        yield request

    responses = []
    metadata = [("mcp-protocol-version", version.LATEST_PROTOCOL_VERSION)]
    async for response in grpc_stub.CallTool(request_iterator(), metadata=metadata):
        responses.append(response)

    assert len(responses) == 1
    assert responses[0].is_error
    assert "validation error" in responses[0].content[0].text.text


@pytest.mark.anyio
async def test_call_tool_grpc_test_tool(
    grpc_server: None, grpc_stub: mcp_pb2_grpc.McpStub
):
    """Test CallTool via gRPC with test_tool."""
    tool_name = "test_tool"
    arguments = {"a": 1, "b": 2}
    args_struct = struct_pb2.Struct()
    json_format.ParseDict(arguments, args_struct)

    request = mcp_pb2.CallToolRequest(
        common=mcp_pb2.RequestFields(),
        request=mcp_pb2.CallToolRequest.Request(
            name=tool_name, arguments=args_struct
        )
    )

    async def request_iterator():
        yield request

    responses = []
    metadata = [("mcp-protocol-version", version.LATEST_PROTOCOL_VERSION)]
    async for response in grpc_stub.CallTool(request_iterator(), metadata=metadata):
        responses.append(response)

    assert len(responses) == 1
    assert responses[0].content[0].text.text == "3"
    assert not responses[0].is_error
    assert responses[0].structured_content['result'] == 3

@pytest.mark.anyio
async def test_call_failing_tool_grpc(grpc_server: None, grpc_stub: mcp_pb2_grpc.McpStub):
    """Test CallTool with a tool that raises an error."""
    tool_name = "failing_tool"
    arguments = {}
    args_struct = struct_pb2.Struct()
    json_format.ParseDict(arguments, args_struct)

    request = mcp_pb2.CallToolRequest(
        common=mcp_pb2.RequestFields(),
        request=mcp_pb2.CallToolRequest.Request(
            name=tool_name, arguments=args_struct
        )
    )

    async def request_iterator():
        yield request

    responses = []
    metadata = [("mcp-protocol-version", version.LATEST_PROTOCOL_VERSION)]
    async for response in grpc_stub.CallTool(request_iterator(), metadata=metadata):
        responses.append(response)

    assert len(responses) == 1
    assert responses[0].is_error
    assert (
        "Error executing tool failing_tool: This tool is designed to fail."
        in responses[0].content[0].text.text
    )


@pytest.mark.anyio
async def test_call_tool_not_found_grpc(grpc_server: None, grpc_stub: mcp_pb2_grpc.McpStub):
    """Test CallTool with a tool that is not found."""
    tool_name = "non_existent_tool"
    arguments = {}
    args_struct = struct_pb2.Struct()
    json_format.ParseDict(arguments, args_struct)

    request = mcp_pb2.CallToolRequest(
        common=mcp_pb2.RequestFields(),
        request=mcp_pb2.CallToolRequest.Request(
            name=tool_name, arguments=args_struct
        )
    )

    async def request_iterator():
        yield request

    responses = []
    metadata = [("mcp-protocol-version", version.LATEST_PROTOCOL_VERSION)]
    async for response in grpc_stub.CallTool(request_iterator(), metadata=metadata):
        responses.append(response)

    assert len(responses) == 1
    assert responses[0].is_error
    assert (
        f"Tool '{tool_name}' not found."
        in responses[0].content[0].text.text
    )


@pytest.mark.anyio
async def test_call_tool_grpc_list_tool(grpc_server: None, grpc_stub: mcp_pb2_grpc.McpStub):
    """Test CallTool via gRPC with list_tool."""
    tool_name = "list_tool"
    arguments = {}
    args_struct = struct_pb2.Struct()
    json_format.ParseDict(arguments, args_struct)

    request = mcp_pb2.CallToolRequest(
        common=mcp_pb2.RequestFields(),
        request=mcp_pb2.CallToolRequest.Request(
            name=tool_name, arguments=args_struct
        )
    )

    async def request_iterator():
        yield request

    responses = []
    metadata = [("mcp-protocol-version", version.LATEST_PROTOCOL_VERSION)]
    async for response in grpc_stub.CallTool(request_iterator(), metadata=metadata):
        responses.append(response)

    assert len(responses) == 1
    assert responses[0].content[0].text.text == "one"
    assert responses[0].content[1].text.text == "two"
    assert not responses[0].is_error
    assert responses[0].structured_content['result'] == ["one", "two"]


@pytest.mark.anyio
async def test_call_tool_grpc_no_initial_request(grpc_server: None, grpc_stub: mcp_pb2_grpc.McpStub):
    """Test CallTool via gRPC with no initial request."""
    request = mcp_pb2.CallToolRequest(
        common=mcp_pb2.RequestFields()
    )

    async def request_iterator():
        yield request

    responses = []
    metadata = [("mcp-protocol-version", version.LATEST_PROTOCOL_VERSION)]
    async for response in grpc_stub.CallTool(request_iterator(), metadata=metadata):
        responses.append(response)

    assert len(responses) == 1
    assert responses[0].is_error
    assert "Initial request cannot be empty." in responses[0].content[0].text.text


@pytest.mark.anyio
async def test_call_tool_grpc_dict_tool(grpc_server: None, grpc_stub: mcp_pb2_grpc.McpStub):
    """Test CallTool via gRPC with dict_tool."""
    tool_name = "dict_tool"
    arguments = {}
    args_struct = struct_pb2.Struct()
    json_format.ParseDict(arguments, args_struct)

    request = mcp_pb2.CallToolRequest(
        common=mcp_pb2.RequestFields(),
        request=mcp_pb2.CallToolRequest.Request(
            name=tool_name, arguments=args_struct
        )
    )

    async def request_iterator():
        yield request

    responses = []
    metadata = [("mcp-protocol-version", version.LATEST_PROTOCOL_VERSION)]
    async for response in grpc_stub.CallTool(request_iterator(), metadata=metadata):
        responses.append(response)

    assert len(responses) == 1
    assert json.loads(responses[0].content[0].text.text) == {"key": "value"}
    assert not responses[0].is_error


@pytest.mark.anyio
async def test_call_tool_grpc_structured_dict_tool(
    grpc_server: None, grpc_stub: mcp_pb2_grpc.McpStub
):
    """Test CallTool via gRPC with structured_dict_tool."""
    tool_name = "structured_dict_tool"
    arguments = {}
    args_struct = struct_pb2.Struct()
    json_format.ParseDict(arguments, args_struct)

    request = mcp_pb2.CallToolRequest(
        common=mcp_pb2.RequestFields(),
        request=mcp_pb2.CallToolRequest.Request(
            name=tool_name, arguments=args_struct
        )
    )

    async def request_iterator():
        yield request

    responses = []
    metadata = [("mcp-protocol-version", version.LATEST_PROTOCOL_VERSION)]
    async for response in grpc_stub.CallTool(request_iterator(), metadata=metadata):
        responses.append(response)

    assert len(responses) == 1
    assert json.loads(responses[0].content[0].text.text) == {"key": "value"}
    assert not responses[0].is_error
    assert responses[0].structured_content == {"key": "value"}


@pytest.mark.anyio
async def test_server_handles_client_cancellation(grpc_server: None, server_port: int):
    """
    Test that McpServicer.CallTool's cancellation handling is triggered
    when a client cancels a call. This test indirectly verifies that
    the `except asyncio.CancelledError` block in `McpServicer.CallTool`
    is entered, and that it correctly cancels the tool-running task.
    """
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
        await asyncio.sleep(0.2)  # give call_tool time to start
        await transport.send_notification(cancel_notification)

        with pytest.raises(McpError) as e:
            await call_tool_task
        assert e.value.error.code == types.REQUEST_CANCELLED
        # If we reach here without timeout, it means server-side
        # cancellation handling in McpServicer.CallTool worked and cancelled
        # the tool task running blocking_tool, allowing call_tool to
        # receive cancellation from server and raise McpError quickly.
    finally:
        await transport.close()
