"""Utility functions for gRPC."""

import asyncio
import functools
import grpc
from grpc import aio
from mcp.shared import version
from typing import Any, Callable, TypeVar, cast


MCP_PROTOCOL_VERSION_KEY = "mcp-protocol-version"
MCP_TOOL_NAME_KEY = "mcp-tool-name"
MCP_RESOURCE_URI_KEY = "mcp-resource-uri"


F = TypeVar("F", bound=Callable[..., Any])


def check_protocol_version_from_metadata(func: F) -> F:
  """Decorator to check protocol version from metadata for gRPC methods.
  It aborts the RPC if the protocol version is not provided or is not supported.
  """

  @functools.wraps(func)
  async def async_wrapper(self, request, context, *args, **kwargs):
    protocol_version_str = await get_protocol_version_from_context(context, version.SUPPORTED_PROTOCOL_VERSIONS)
    if protocol_version_str in version.SUPPORTED_PROTOCOL_VERSIONS:
      await context.send_initial_metadata([
          (MCP_PROTOCOL_VERSION_KEY, protocol_version_str),
      ])
    return await func(self, request, context, *args, **kwargs)

  @functools.wraps(func)
  async def async_generator_wrapper(self, request, context, *args, **kwargs):
    protocol_version_str = await get_protocol_version_from_context(context, version.SUPPORTED_PROTOCOL_VERSIONS)
    if protocol_version_str in version.SUPPORTED_PROTOCOL_VERSIONS:
      await context.send_initial_metadata([
          (MCP_PROTOCOL_VERSION_KEY, protocol_version_str),
      ])
    async for item in func(self, request, context, *args, **kwargs):
      yield item

  if asyncio.iscoroutinefunction(func):
    return cast(F, async_wrapper)
  else:
    return cast(F, async_generator_wrapper)




async def get_protocol_version_from_context(
    context: aio.ServicerContext, supported_versions: str
) -> str:
  """Extracts and validates the protocol version from gRPC metadata, canceling the RPC if invalid."""
  metadata = context.invocation_metadata()
  protocol_version_str = get_metadata_value(metadata, MCP_PROTOCOL_VERSION_KEY)

  if protocol_version_str is None:
    supported_versions_str = ", ".join(supported_versions)
    await context.send_initial_metadata([(MCP_PROTOCOL_VERSION_KEY, version.LATEST_PROTOCOL_VERSION)])
    await context.abort(
        grpc.StatusCode.UNIMPLEMENTED,
        f"Protocol version not provided. Supported versions are: {supported_versions_str}",
    ) # type: ignore

  if protocol_version_str not in supported_versions:
    supported_versions_str = ", ".join(supported_versions)
    await context.send_initial_metadata([(MCP_PROTOCOL_VERSION_KEY, version.LATEST_PROTOCOL_VERSION)])
    await context.abort(
        grpc.StatusCode.UNIMPLEMENTED,
        f"Unsupported protocol version: {protocol_version_str}. Supported versions are: {supported_versions_str}",
    ) # type: ignore
  return protocol_version_str


def get_metadata_value(
    metadata: tuple[tuple[str, str | bytes], ...], key: str
) -> str | None:
    """Extracts a value from gRPC metadata by key."""
    if metadata:
        for k, value in metadata:
            if k.lower() == key.lower():
                if isinstance(value, bytes):
                    return value.decode("utf-8")
                return str(value)
    return None
