from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import grpc
import pytest

from mcp.shared import grpc_utils, version


@pytest.fixture
def mock_context() -> Any:
    context = AsyncMock(spec=grpc.aio.ServicerContext)
    context.abort = AsyncMock()
    context.invocation_metadata = MagicMock(return_value=())
    context.send_initial_metadata = AsyncMock()
    return context


def test_get_metadata_value_found_string():
    """Test get_metadata_value with a key present and a string value."""
    metadata = (("key1", "value1"), ("Key2", "value2"))
    assert grpc_utils.get_metadata_value(cast(Any, metadata), "key2") == "value2"


def test_get_metadata_value_found_bytes():
    """Test get_metadata_value with a key present and a bytes value."""
    metadata = (("key1", b"value1"), ("key2", b"value2"))
    assert grpc_utils.get_metadata_value(cast(Any, metadata), "key1") == "value1"


def test_get_metadata_value_case_insensitive():
    """Test get_metadata_value with case-insensitive key matching."""
    metadata = (("KeY1", "value1"),)
    assert grpc_utils.get_metadata_value(cast(Any, metadata), "key1") == "value1"
    assert grpc_utils.get_metadata_value(cast(Any, metadata), "KEY1") == "value1"


def test_get_metadata_value_not_found():
    """Test get_metadata_value with a key not present."""
    metadata = (("key1", "value1"), ("key2", "value2"))
    assert grpc_utils.get_metadata_value(cast(Any, metadata), "key3") is None


def test_get_metadata_value_empty_metadata():
    """Test get_metadata_value with empty metadata."""
    metadata: tuple[tuple[str, str], ...] = ()
    assert grpc_utils.get_metadata_value(cast(Any, metadata), "key1") is None


def test_get_metadata_value_none_metadata():
    """Test get_metadata_value with None metadata."""
    assert grpc_utils.get_metadata_value(None, "key1") is None


@pytest.mark.asyncio
async def test_get_protocol_version_from_context_no_version(mock_context: Any):
    """Test aborting when no protocol version is provided in metadata."""
    mock_context.invocation_metadata.return_value = ()
    supported_versions = version.SUPPORTED_PROTOCOL_VERSIONS
    mock_context.abort.side_effect = grpc.RpcError("Aborted")

    with pytest.raises(grpc.RpcError):
        await grpc_utils.get_protocol_version_from_context(mock_context, supported_versions)

    mock_context.send_initial_metadata.assert_called_once_with(
        [(grpc_utils.MCP_PROTOCOL_VERSION_KEY, version.LATEST_PROTOCOL_VERSION)]
    )
    mock_context.abort.assert_called_once_with(
        grpc.StatusCode.UNIMPLEMENTED,
        "Protocol version not provided. Supported versions are: 2024-11-05, 2025-03-26, 2025-06-18, 2025-11-25",
    )


@pytest.mark.asyncio
async def test_get_protocol_version_from_context_unsupported_version(mock_context: Any):
    """Test aborting when an unsupported protocol version is provided."""
    mock_context.invocation_metadata.return_value = ((grpc_utils.MCP_PROTOCOL_VERSION_KEY, "unsupported"),)
    supported_versions = version.SUPPORTED_PROTOCOL_VERSIONS
    mock_context.abort.side_effect = grpc.RpcError("Aborted")

    with pytest.raises(grpc.RpcError):
        await grpc_utils.get_protocol_version_from_context(mock_context, supported_versions)

    mock_context.send_initial_metadata.assert_called_once_with(
        [(grpc_utils.MCP_PROTOCOL_VERSION_KEY, version.LATEST_PROTOCOL_VERSION)]
    )
    mock_context.abort.assert_called_once_with(
        grpc.StatusCode.UNIMPLEMENTED,
        "Unsupported protocol version: unsupported. "
        + "Supported versions are: 2024-11-05, 2025-03-26, 2025-06-18, 2025-11-25",
    )


@pytest.mark.asyncio
async def test_get_protocol_version_from_context_supported_version(mock_context: Any):
    """Test success when a supported protocol version is provided."""
    test_version = version.SUPPORTED_PROTOCOL_VERSIONS[0]
    mock_context.invocation_metadata.return_value = ((grpc_utils.MCP_PROTOCOL_VERSION_KEY, test_version),)
    supported_versions = version.SUPPORTED_PROTOCOL_VERSIONS

    result = await grpc_utils.get_protocol_version_from_context(mock_context, supported_versions)

    assert result == test_version
    mock_context.abort.assert_not_called()
