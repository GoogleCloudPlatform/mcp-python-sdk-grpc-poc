from datetime import timedelta
import logging
import asyncio
import uuid
import base64
import time

import grpc
from grpc import aio
from google.protobuf import json_format
from jsonschema import ValidationError, SchemaError
from jsonschema.validators import validate

from mcp import types
from mcp.client.cache import CacheEntry
from mcp.client.session_common import ElicitationFnT
from mcp.client.session_common import ListRootsFnT
from mcp.client.session_common import LoggingFnT
from mcp.client.session_common import MessageHandlerFnT
from mcp.client.session_common import SamplingFnT
from mcp.client.session_common import _validate_tool_result
from mcp.client.transport_session import TransportSession
from mcp.proto import mcp_pb2
from mcp.proto import mcp_pb2_grpc
from mcp.shared import convert
from mcp.shared import grpc_utils
from mcp.shared.exceptions import McpError
from mcp.shared import version

from typing import Any

from mcp.shared.session import ProgressFnT
from mcp.types import ErrorData
from pydantic import AnyUrl


LATEST_PROTOCOL_VERSION = types.LATEST_PROTOCOL_VERSION
logger = logging.getLogger(__name__)

class GRPCTransportSession(TransportSession):
    """gRPC-based implementation of the Transport session.

    This class handles communication with the MCP gRPC server.
    """

    def __init__(
        self,
        target: str,
        channel_credential: grpc.ChannelCredentials | None = None,
        read_timeout_seconds: timedelta | None = None,
        sampling_callback: SamplingFnT | None = None,
        elicitation_callback: ElicitationFnT | None = None,
        list_roots_callback: ListRootsFnT | None = None,
        logging_callback: LoggingFnT | None = None,
        message_handler: MessageHandlerFnT | None = None,
        client_info: types.Implementation | None = None,
        options: Optional[ChannelArgumentType] = None,
        compression: Optional[grpc.Compression] = None,
        interceptors: Optional[Sequence[grpc.aio.ClientInterceptor]] = None,
    ) -> None:
      """Initialize the gRPC transport session."""
      logger.info("Creating GRPCTransportSession for target: %s", target)
      if channel_credential is not None:
          channel = aio.secure_channel(target, channel_credential, options=options, compression=compression, interceptors=interceptors)
      else:
          channel = aio.insecure_channel(target, options=options, compression=compression, interceptors=interceptors)

      stub = mcp_pb2_grpc.McpStub(channel)
      self.grpc_stub = stub
      self._channel = channel
      self._request_counter = 0
      self._progress_callbacks: dict[str | int, ProgressFnT] = {}
      self._running_calls: dict[str | int, aio.Call] = {}
      self._session_read_timeout_seconds = read_timeout_seconds
      self.negotiated_version = LATEST_PROTOCOL_VERSION
      self._message_handler = message_handler

      # Tool cache
      self._list_tool_cache = CacheEntry(
          self._on_tool_list_expired
      )
      # Resources cache
      self._list_resources_cache = CacheEntry(
          self._on_resource_list_expired
      )
      # Resource templates cache
      self._list_resource_templates_cache = CacheEntry(
          self._on_resource_list_expired
      )

      logger.info("GRPCTransportSession created.")

    async def _call_unary_rpc(self, rpc_method: Any, request: Any, timeout: float | None, metadata: list[tuple[str, str]] | None = None) -> Any:
        """Calls a unary gRPC method with retry logic for version mismatch."""
        if metadata is None:
            metadata = []
        for attempt in range(1, 3):
            new_metadata = metadata + [(grpc_utils.MCP_PROTOCOL_VERSION_KEY, self.negotiated_version)]
            logger.info("Calling %s (attempt %s) with version %s", rpc_method._method, attempt, self.negotiated_version)
            try:
                response = await rpc_method(request, timeout=timeout, metadata=new_metadata)
                logger.info("Successfully called %s (attempt %s)", rpc_method._method, attempt)
                return response
            except grpc.RpcError as e:
                logger.warning('gRPC error on attempt %s: %s', attempt + 1, e)
                if attempt == 1:
                    if self._check_and_update_version(e):
                        continue  # Retry with new version
                raise e

    async def _on_tool_list_expired(self):
        if self._message_handler:
            await self._message_handler(
                types.ServerNotification(
                    root=types.ToolListChangedNotification(
                        method="notifications/tools/list_changed",
                    )
                )
            )

    async def _on_resource_list_expired(self):
        if self._message_handler:
            await self._message_handler(
                types.ServerNotification(
                    root=types.ResourceListChangedNotification(
                        method="notifications/resources/list_changed",
                    )
                )
            )

    def _check_and_update_version(self, e: grpc.RpcError) -> bool:
        """Checks for protocol version mismatch and updates the negotiated version if possible.

        Returns True if the version was updated and the call should be retried.
        """
        if e.code() == grpc.StatusCode.UNIMPLEMENTED:
            initial_metadata = e.initial_metadata()
            negotiated_version = grpc_utils.get_metadata_value(initial_metadata, grpc_utils.MCP_PROTOCOL_VERSION_KEY)

            if negotiated_version is None:
                logger.warning(
                    "Server did not return a valid '%s' in initial metadata. Failing.",
                    grpc_utils.MCP_PROTOCOL_VERSION_KEY
                )
                return False

            if negotiated_version in version.SUPPORTED_PROTOCOL_VERSIONS:
                logger.info(
                    "Server returned protocol version %s in initial metadata. Negotiating to this version. Retrying.",
                    negotiated_version
                )
                self.negotiated_version = negotiated_version
                return True
            else:
                logger.info(
                    "Server returned same protocol version %s in initial metadata.",
                    negotiated_version
                )
        return False

    # TODO(asheshvidyut): Look into relevance of this API
    # b/448290917
    async def close(self) -> None:
      """Close the gRPC channel."""
      logger.info("Closing GRPCTransportSession channel.")
      self._list_tool_cache.cancel_expiry_task()
      self._list_resources_cache.cancel_expiry_task()
      self._list_resource_templates_cache.cancel_expiry_task()
      await self._channel.close()
      logger.info("GRPCTransportSession channel closed.")

    def _cancel_request(self, request_id: str | int):
        """Cancel a running request by its ID."""
        call = self._running_calls.get(request_id)
        if call:
            logger.info("Cancelling request_id: %s", request_id)
            call.cancel()

    def _raise_on_deadline_exceeded(
        self, e: grpc.RpcError, request_name: str
    ) -> None:
        """Raises McpError if gRPC error is DEADLINE_EXCEEDED."""
        if e.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
            timeout = (
                self._session_read_timeout_seconds.total_seconds()
                if self._session_read_timeout_seconds
                else 'N/A'
            )
            raise McpError(
                ErrorData(
                    code=types.REQUEST_TIMEOUT,
                    message=(
                        'Timed out while waiting for response to '
                        f'{request_name}. Waited '
                        f'{timeout} seconds.'
                    ),
                )
            ) from e

    async def send_notification(self, notification: types.ClientNotification) -> None:
        """Sends a notification.

        If the notification is for cancellation, it triggers gRPC cancellation
        for the corresponding request.
        """
        if isinstance(notification.root, types.CancelledNotification):
            request_id = notification.root.params.requestId
            logger.info(
                "Received cancellation notification for request_id: %s",
                request_id,
            )
            self._cancel_request(request_id)
        else:
            logger.warning(
                "GRPCTransportSession.send_notification received unhandled "
                "notification type: %s",
                type(notification.root),
            )

    async def initialize(self) -> types.InitializeResult:
        """Send an initialize request."""
        ...

    async def send_ping(self):
      ...


    async def send_progress_notification(
        self,
        progress_token: str | int,
        progress: float,
        total: float | None = None,
        message: str | None = None,
    ) -> None:
      ...


    async def set_logging_level(self,
        level: types.LoggingLevel) -> types.EmptyResult:
      """Send a logging/setLevel request."""
      ...


    async def list_resources(self,
        cursor: str | None = None) -> types.ListResourcesResult:
      """Send a resources/list request."""
      request = mcp_pb2.ListResourcesRequest(
          common=mcp_pb2.RequestFields(
              cursor=cursor,
          )
      )
      try:
          timeout = (
              self._session_read_timeout_seconds.total_seconds()
              if self._session_read_timeout_seconds
              else None
          )
          response = await self._call_unary_rpc(
              self.grpc_stub.ListResources, request, timeout
          )
          resources = convert.resource_protos_to_types(list(response.resources))
          resources_dict = {resource.name: resource for resource in resources}
          self._list_resources_cache.set(
              resources_dict,
              convert.timedelta_from_ttl(response.ttl),
          )
          return types.ListResourcesResult(resources=resources)
      except json_format.ParseError as e:
          error_message = f'Failed to parse resource proto: {e}'
          logger.error(error_message, exc_info=True)
          raise McpError(
              ErrorData(code=types.PARSE_ERROR, message=error_message)
          ) from e
      except grpc.RpcError as e:
          self._raise_on_deadline_exceeded(e, request.__class__.__name__)
          error_message = f'grpc.RpcError - Failed to list resources: {e}'
          logger.error(error_message, exc_info=True)
          raise McpError(
              ErrorData(code=types.INTERNAL_ERROR, message=error_message)
          ) from e


    async def list_resource_templates(self,
        cursor: str | None = None) -> types.ListResourceTemplatesResult:
        """Send a resources/templates/list request."""
        request = mcp_pb2.ListResourceTemplatesRequest(
            common=mcp_pb2.RequestFields(
                cursor=cursor,
            )
        )
        try:
            timeout = (
                self._session_read_timeout_seconds.total_seconds()
                if self._session_read_timeout_seconds
                else None
            )
            response = await self._call_unary_rpc(
                self.grpc_stub.ListResourceTemplates, request, timeout
            )
            resource_templates = convert.resource_template_protos_to_types(
                list(response.resource_templates)
            )
            resource_templates_dict = {
                template.name: template for template in resource_templates
            }
            self._list_resource_templates_cache.set(
                resource_templates_dict,
                convert.timedelta_from_ttl(response.ttl),
            )
            return types.ListResourceTemplatesResult(
                resourceTemplates=resource_templates
            )
        except json_format.ParseError as e:
            error_message = f"Failed to parse resource template proto: {e}"
            logger.error(error_message, exc_info=True)
            raise McpError(
                ErrorData(code=types.PARSE_ERROR, message=error_message)
            ) from e
        except grpc.RpcError as e:
            self._raise_on_deadline_exceeded(e, request.__class__.__name__)
            error_message = (
                f'grpc.RpcError - Failed to list resource templates: {e}'
            )
            logger.error(error_message, exc_info=True)
            raise McpError(
                ErrorData(code=types.INTERNAL_ERROR, message=error_message)
            ) from e



    async def read_resource(self, uri: AnyUrl) -> types.ReadResourceResult:
        """Send a resources/read request."""
        request = mcp_pb2.ReadResourceRequest(
            common=mcp_pb2.RequestFields(),
            uri=str(uri),
        )
        try:
            timeout = (
                self._session_read_timeout_seconds.total_seconds()
                if self._session_read_timeout_seconds
                else None
            )
            metadata = [(grpc_utils.MCP_RESOURCE_URI_KEY, str(uri))]
            response = await self._call_unary_rpc(
                self.grpc_stub.ReadResource, request, timeout, metadata=metadata
            )
            resource_contents_list = response.resource
            contents = []
            for res_content in resource_contents_list:
              if res_content.text:
                  contents.append(
                      types.TextResourceContents(
                          uri=res_content.uri,
                          mimeType=res_content.mime_type,
                          text=res_content.text,
                      )
                  )
              elif res_content.blob:
                  contents.append(
                      types.BlobResourceContents(
                          uri=res_content.uri,
                          mimeType=res_content.mime_type,
                          blob=base64.b64encode(res_content.blob).decode("utf-8"),
                      )
                  )
            return types.ReadResourceResult(contents=contents)
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.NOT_FOUND:
                error_message = f'Resource {uri} not found.'
                logger.error(error_message, exc_info=True)
                raise McpError(
                    ErrorData(code=-32002, message=error_message)
                ) from e
            self._raise_on_deadline_exceeded(e, request.__class__.__name__)
            error_message = f'grpc.RpcError - Failed to read resource {uri}: {e}'
            logger.error(error_message, exc_info=True)
            raise McpError(
                ErrorData(code=types.INTERNAL_ERROR, message=error_message)
            ) from e


    async def subscribe_resource(self, uri: AnyUrl) -> types.EmptyResult:
        """Send a resources/subscribe request."""
        ...


    async def unsubscribe_resource(self, uri: AnyUrl) -> types.EmptyResult:
        """Send a resources/unsubscribe request."""
        ...

    async def request_generator(self,
                                name: str,
                                request_id: int,
                                arguments: Any | None = None):
        """Yields the single tool call request."""
        logger.info(
            "Calling tool '%s' with request_id: %s", name, request_id
        )
        yield types.CallToolRequestParams(
            name=name,
            arguments=arguments or {},
            _meta=types.RequestParams.Meta(
                progressToken=request_id
            ),
        )


    async def call_tool(
        self,
        name: str,
        arguments: Any | None = None,
        read_timeout_seconds: timedelta | None = None,
        progress_callback: ProgressFnT | None = None,
    ) -> types.CallToolResult:
        """Send a tools/call request with optional progress callback support."""
        self._request_counter += 1
        request_id = self._request_counter

        if progress_callback:
            self._progress_callbacks[request_id] = progress_callback

        for attempt in range(1, 3):
            proto_results = []
            structured_content = None
            is_error = False
            try:
                request_iterator = convert.generate_call_tool_requests(
                    self.request_generator(name, request_id, arguments)
                )
                # read_timeout_seconds takes precedence over session timeout
                timeout_td = (
                    read_timeout_seconds or self._session_read_timeout_seconds
                )
                timeout = timeout_td.total_seconds() if timeout_td else None
                metadata = [
                    (grpc_utils.MCP_TOOL_NAME_KEY, name),
                    (grpc_utils.MCP_PROTOCOL_VERSION_KEY, self.negotiated_version)
                ]
                call = self.grpc_stub.CallTool(
                    request_iterator,
                    timeout=timeout,
                    metadata=metadata,
                )
                self._running_calls[request_id] = call
                async for response in call:

                    if response.common.HasField("progress"):
                        progress_proto = response.common.progress
                        progress_token = progress_proto.progress_token
                        try:
                            progress_token = int(progress_token)
                        except ValueError:
                            logger.warning(
                                "Progress token is not an integer: %s",
                                progress_proto.progress_token,
                            )

                        if progress_token in self._progress_callbacks:
                            callback = self._progress_callbacks[progress_token]
                            await callback(
                                progress_proto.progress,
                                progress_proto.total or None,
                                progress_proto.message or None,
                            )
                        continue

                    if response.content:
                        proto_results.extend(response.content)
                    if response.HasField("structured_content"):
                        structured_content = json_format.MessageToDict(
                            response.structured_content
                        )
                    is_error = is_error or response.is_error

                final_result = convert.proto_result_to_content(
                    proto_results, structured_content, is_error
                )
                # Clean up the running call and progress callback after the call is complete.
                self._running_calls.pop(request_id, None)
                self._progress_callbacks.pop(request_id, None)
                return await self._validate_and_return_result(name, final_result)

            except asyncio.CancelledError as e:
                # Clean up the running call and progress callback on cancellation.
                self._running_calls.pop(request_id, None)
                self._progress_callbacks.pop(request_id, None)
                raise McpError(
                    ErrorData(
                        code=types.REQUEST_CANCELLED,
                        message=f'Tool call "{name}" was cancelled',
                    )
                ) from e
            except json_format.ParseError as e:
                # Clean up the running call and progress callback on parse error.
                self._running_calls.pop(request_id, None)
                self._progress_callbacks.pop(request_id, None)
                error_message = f'Failed to parse tool proto: {e}'
                logger.error(error_message, exc_info=True)
                raise McpError(
                    ErrorData(code=types.PARSE_ERROR, message=error_message)
                ) from e
            except grpc.RpcError as e:
                # Clean up the running call on gRPC error.
                # Pop the call as a new one will be created in the next iteration.
                self._running_calls.pop(request_id, None)
                if attempt == 1:
                    if self._check_and_update_version(e):
                        continue

                # Clean up the progress callback on gRPC error.
                self._progress_callbacks.pop(request_id, None)
                if e.code() == grpc.StatusCode.CANCELLED:
                    raise McpError(
                        ErrorData(
                            code=types.REQUEST_CANCELLED,
                            message=f'Tool call "{name}" was cancelled',
                        )
                    ) from e
                if e.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
                    timeout = timeout_td.total_seconds() if timeout_td else 'N/A'
                    raise McpError(
                        ErrorData(
                            code=types.REQUEST_TIMEOUT,
                            message=(
                                'Timed out while waiting for response to '
                                f'CallTool. Waited {timeout} seconds.'
                            ),
                        )
                    ) from e
                error_message = f'grpc.RpcError - Failed to call tool "{name}": {e.details()}'
                logger.error(error_message, exc_info=True)
                raise McpError(
                    ErrorData(code=types.INTERNAL_ERROR, message=error_message)
                ) from e
            except Exception as e:
                # Clean up the running call and progress callback on unexpected error.
                self._running_calls.pop(request_id, None)
                self._progress_callbacks.pop(request_id, None)
                error_message = (
                    f'An unexpected error occurred during CallTool: {e}'
                )
                logger.error(error_message, exc_info=True)
                raise McpError(
                    ErrorData(code=types.INTERNAL_ERROR, message=error_message)
                ) from e
        # Clean up the progress callback if CallTool fails after retries.
        self._progress_callbacks.pop(request_id, None)
        raise McpError(ErrorData(code=types.INTERNAL_ERROR, message="CallTool failed after retry"))

    async def _validate_and_return_result(
        self, name: str, final_result: types.CallToolResult | None
    ) -> types.CallToolResult:
        """Validate and return the tool result."""
        if final_result is None:
            raise McpError(
                ErrorData(
                    code=types.INTERNAL_ERROR,
                    message="Tool call did not produce a result.",
                )
            )

        # TODO(asheshvidyut): check and verify all the error handling cases
        # b/448303754
        if not final_result.isError:
            try:
                await self._validate_tool_result(name, final_result)
            except RuntimeError as e:
                error_message = f'Tool result validation failed for "{name}": {e}'
                logger.error(error_message, exc_info=True)
                raise McpError(
                    ErrorData(code=types.INTERNAL_ERROR, message=error_message)
                ) from e
        return final_result

    async def _validate_tool_result(self, name: str,
        result: types.CallToolResult) -> None:
        """Validate the structured content of a tool result against its output schema."""
        cached_tools = self._list_tool_cache.get()
        if cached_tools is None:
            # If cache is empty, fetch tools and update cache.
            await self.list_tools()
            cached_tools = self._list_tool_cache.get()

        tool_schema = None
        if cached_tools and name in cached_tools:
            tool = cached_tools[name]
            tool_schema = tool.outputSchema

        if tool_schema is not None:
            await _validate_tool_result(tool_schema, name, result)
        else:
            logger.warning(
                "Tool %s not listed by server, cannot validate any structured"
                " content",
                name,
            )

    async def list_prompts(self,
        cursor: str | None = None) -> types.ListPromptsResult:
        """Send a prompts/list request."""
        ...


    async def get_prompt(self, name: str,
        arguments: dict[str, str] | None = None) -> types.GetPromptResult:
        """Send a prompts/get request."""
        ...


    async def complete(
        self,
        ref: types.ResourceTemplateReference | types.PromptReference,
        argument: dict[str, str],
        context_arguments: dict[str, str] | None = None,
    ) -> types.CompleteResult:
        """Send a completion/complete request."""
        ...


    async def list_tools(
        self,
        cursor: str | None = None,
    ) -> types.ListToolsResult:
        """Send a tools/list request."""
        request = mcp_pb2.ListToolsRequest(
            common=mcp_pb2.RequestFields(
                cursor=cursor,
            )
        )
        try:
            # Send the request using gRPC stub
            timeout = (
                self._session_read_timeout_seconds.total_seconds()
                if self._session_read_timeout_seconds
                else None
            )
            response = await self._call_unary_rpc(
                self.grpc_stub.ListTools, request, timeout
            )

            # Convert gRPC response to ListToolsResult
            tools = convert.tool_protos_to_types(response.tools)
            tools_dict = {tool.name: tool for tool in tools}
            self._list_tool_cache.set(
                tools_dict,
                convert.timedelta_from_ttl(response.ttl),
            )
            return types.ListToolsResult(tools=tools)
        except json_format.ParseError as e:
            error_message = f'Failed to parse tool proto: {e}'
            logger.error(error_message, exc_info=True)
            error_data = ErrorData(
                code=types.PARSE_ERROR,
                message=error_message,
            )
            raise McpError(error_data) from e
        except RuntimeError as e:
            error_message = f'Failed to convert tool proto to type: {e}'
            logger.error(error_message, exc_info=True)
            error_data = ErrorData(
                code=types.INTERNAL_ERROR,
                message=error_message,
            )
            raise McpError(error_data) from e
        except grpc.RpcError as e:
            self._raise_on_deadline_exceeded(e, request.__class__.__name__)
            error_message = f'grpc.RpcError - Failed to list tools: {e}'
            logger.error(error_message, exc_info=True)
            error_data = ErrorData(
                code=types.INTERNAL_ERROR,
                message=error_message,
            )
            raise McpError(error_data) from e
        return result

    async def send_roots_list_changed(self) -> None:
        """Send a roots/list_changed notification."""
        ...
