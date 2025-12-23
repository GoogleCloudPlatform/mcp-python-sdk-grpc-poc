"""Utilities for converting between MCP types and protobuf messages."""

import base64
import json
import logging
from collections.abc import AsyncGenerator, Iterable, Sequence
from datetime import timedelta
from typing import Any, TypeAlias, cast

import jsonschema

from google.protobuf import duration_pb2  # isort: skip
from google.protobuf import json_format  # isort: skip
from google.protobuf import struct_pb2  # isort: skip
from pydantic import AnyUrl

from mcp import types
from mcp.proto import mcp_pb2
from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.shared.exceptions import McpError
from mcp.types import ErrorData, Role

logger = logging.getLogger(__name__)


def ttl_from_timedelta(ttl_timedelta: timedelta) -> duration_pb2.Duration:
    """Converts a timedelta to a duration_pb2.Duration proto."""
    ttl_float = ttl_timedelta.total_seconds()
    seconds = int(ttl_float)
    nanos = int((ttl_float - seconds) * 1_000_000_000)
    return duration_pb2.Duration(seconds=seconds, nanos=nanos)


def timedelta_from_ttl(ttl: duration_pb2.Duration) -> timedelta:
    """Converts a TTL proto to a timedelta."""
    return timedelta(seconds=ttl.seconds + ttl.nanos / 1e9)


def resource_type_to_proto(resource: types.Resource) -> mcp_pb2.Resource:
    """Converts a types.Resource object to a Resource protobuf message."""
    proto_annotations = None
    if resource.annotations:
        audience: list[mcp_pb2.Role] = []
        if resource.annotations.audience:
            for role in resource.annotations.audience:
                if role == "user":
                    audience.append(mcp_pb2.ROLE_USER)
                elif role == "assistant":
                    audience.append(mcp_pb2.ROLE_ASSISTANT)
        proto_annotations = mcp_pb2.Annotations(
            audience=audience,
            priority=resource.annotations.priority if resource.annotations.priority is not None else 0.0,
        )

    return mcp_pb2.Resource(
        uri=str(resource.uri),
        name=resource.name,
        title=resource.title,
        description=resource.description,
        mime_type=resource.mimeType,
        size=resource.size if resource.size is not None else 0,
        annotations=proto_annotations,
    )


def resource_types_to_protos(
    resources: list[types.Resource],
) -> list[mcp_pb2.Resource]:
    """Converts a list of types.Resource to a list of Resource protos."""
    return [resource_type_to_proto(resource) for resource in resources]


def resource_proto_to_type(resource_proto: mcp_pb2.Resource) -> types.Resource:
    """Converts a Resource protobuf message to a types.Resource object."""
    annotations = None
    if resource_proto.HasField("annotations"):
        audience: list[Role] = []
        for role in resource_proto.annotations.audience:
            if role == mcp_pb2.ROLE_USER:
                audience.append("user")
            elif role == mcp_pb2.ROLE_ASSISTANT:
                audience.append("assistant")
        annotations = types.Annotations(
            audience=audience,
            priority=resource_proto.annotations.priority,
        )

    return types.Resource(
        uri=AnyUrl(resource_proto.uri),
        name=resource_proto.name,
        title=resource_proto.title,
        description=resource_proto.description,
        mimeType=resource_proto.mime_type,
        size=resource_proto.size if resource_proto.size != 0 else None,
        annotations=annotations,
    )


def resource_protos_to_types(
    resource_protos: list[mcp_pb2.Resource],
) -> list[types.Resource]:
    """Converts a list of Resource protos to a list of types.Resource."""
    return [resource_proto_to_type(resource) for resource in resource_protos]


def resource_template_type_to_proto(
    resource_template: types.ResourceTemplate,
) -> mcp_pb2.ResourceTemplate:
    """Converts a types.ResourceTemplate object to a ResourceTemplate protobuf message."""
    proto_annotations = None
    if resource_template.annotations:
        audience: list[mcp_pb2.Role] = []
        if resource_template.annotations.audience:
            for role in resource_template.annotations.audience:
                if role == "user":
                    audience.append(mcp_pb2.ROLE_USER)
                elif role == "assistant":
                    audience.append(mcp_pb2.ROLE_ASSISTANT)
        proto_annotations = mcp_pb2.Annotations(
            audience=audience,
            priority=resource_template.annotations.priority
            if resource_template.annotations.priority is not None
            else 0.0,
        )

    return mcp_pb2.ResourceTemplate(
        uri_template=str(resource_template.uriTemplate),
        name=resource_template.name,
        title=resource_template.title,
        description=resource_template.description,
        mime_type=resource_template.mimeType,
        annotations=proto_annotations,
    )


def resource_template_types_to_protos(
    resource_templates: list[types.ResourceTemplate],
) -> list[mcp_pb2.ResourceTemplate]:
    """Converts types.ResourceTemplate list to ResourceTemplate proto list."""
    # Keeping selected fields as proto does not have all the fields of
    # types.ResourceTemplate
    typed_templates = [
        types.ResourceTemplate(
            uriTemplate=t.uriTemplate,
            name=t.name,
            title=t.title,
            description=t.description,
            mimeType=t.mimeType,
        )
        for t in resource_templates
    ]
    return [resource_template_type_to_proto(resource_template) for resource_template in typed_templates]


def resource_template_proto_to_type(
    resource_template_proto: mcp_pb2.ResourceTemplate,
) -> types.ResourceTemplate:
    """Converts a ResourceTemplate protobuf message to a types.ResourceTemplate object."""
    annotations = None
    if resource_template_proto.HasField("annotations"):
        audience: list[Role] = []
        for role in resource_template_proto.annotations.audience:
            if role == mcp_pb2.ROLE_USER:
                audience.append("user")
            elif role == mcp_pb2.ROLE_ASSISTANT:
                audience.append("assistant")
        annotations = types.Annotations(
            audience=audience,
            priority=resource_template_proto.annotations.priority,
        )

    return types.ResourceTemplate(
        uriTemplate=resource_template_proto.uri_template,
        name=resource_template_proto.name,
        title=resource_template_proto.title,
        description=resource_template_proto.description,
        mimeType=resource_template_proto.mime_type,
        annotations=annotations,
    )


def resource_template_protos_to_types(
    resource_template_protos: list[mcp_pb2.ResourceTemplate],
) -> list[types.ResourceTemplate]:
    """Converts a list of ResourceTemplate protos to a list of types.ResourceTemplate."""
    return [resource_template_proto_to_type(resource_template) for resource_template in resource_template_protos]


def read_resource_content_to_proto(
    uri: str,
    contents: list[ReadResourceContents],
) -> list[mcp_pb2.ResourceContents]:
    """Converts a ReadResourceContents to a mcp_pb2.ResourceContents."""

    resource_contents: list[mcp_pb2.ResourceContents] = []
    for content_item in contents:
        resource_content = mcp_pb2.ResourceContents(
            uri=uri,
            mime_type=content_item.mime_type,
        )
        if isinstance(content_item.content, str):
            resource_content.text = content_item.content
        else:  # isinstance(content_item.content, bytes)
            resource_content.blob = content_item.content
        resource_contents.append(resource_content)
    return resource_contents


def tool_proto_to_type(tool_proto: mcp_pb2.Tool) -> types.Tool:
    """Converts a Tool protobuf message to a types.Tool object."""
    try:
        input_schema = json_format.MessageToDict(tool_proto.input_schema)
        output_schema = json_format.MessageToDict(tool_proto.output_schema)
    except json_format.ParseError as e:
        error_message = f"Failed to parse tool schema for {tool_proto.name}: {e}"
        logger.error(error_message, exc_info=True)
        raise e

    return types.Tool(
        name=tool_proto.name,
        description=tool_proto.description,
        inputSchema=input_schema,
        outputSchema=output_schema,
    )


def tool_type_to_proto(tool: types.Tool) -> mcp_pb2.Tool:
    """Converts a types.Tool object to a Tool protobuf message."""
    input_schema_dict = getattr(tool, "inputSchema", {})
    input_schema = struct_pb2.Struct()
    if input_schema_dict:
        try:
            json_format.ParseDict(input_schema_dict, input_schema)
        except json_format.ParseError as e:
            error_message = f"Failed to parse inputSchema for tool {tool.name}: {e}"
            logger.error(error_message, exc_info=True)
            raise e

    output_schema_dict = getattr(tool, "outputSchema", {})
    output_schema = struct_pb2.Struct()
    if output_schema_dict:
        try:
            json_format.ParseDict(output_schema_dict, output_schema)
        except json_format.ParseError as e:
            error_message = f"Failed to parse outputSchema for tool {tool.name}: {e}"
            logger.error(error_message, exc_info=True)
            raise e

    # TODO(asheshvidyut): Add annotations once usecase is clear
    return mcp_pb2.Tool(
        name=tool.name,
        title=tool.title,
        description=tool.description,
        input_schema=input_schema,
        output_schema=output_schema,
    )


def tool_types_to_protos(tools: list[types.Tool]) -> list[mcp_pb2.Tool]:
    """Converts a list of types.Tool to a list of Tool protos."""
    return [tool_type_to_proto(tool) for tool in tools]


def tool_protos_to_types(tool_protos: list[mcp_pb2.Tool]) -> list[types.Tool]:
    """Converts a list of Tool protos to a list of types.Tool."""
    return [tool_proto_to_type(tool_proto) for tool_proto in tool_protos]


def _populate_content_from_content_block(
    content_block: types.ContentBlock, result: mcp_pb2.CallToolResponse.Content
) -> bool:
    """Populates the result proto from a single content block."""
    if isinstance(content_block, types.TextContent):
        result.text.text = content_block.text
        return True
    elif isinstance(content_block, types.ImageContent):
        result.image.data = base64.b64decode(content_block.data)
        result.image.mime_type = content_block.mimeType
        return True
    elif isinstance(content_block, types.AudioContent):
        result.audio.data = base64.b64decode(content_block.data)
        result.audio.mime_type = content_block.mimeType
        return True
    elif isinstance(content_block, types.EmbeddedResource):
        resource_contents = content_block.resource
        result.embedded_resource.contents.uri = str(resource_contents.uri)
        result.embedded_resource.contents.mime_type = resource_contents.mimeType or ""
        if isinstance(resource_contents, types.TextResourceContents):
            result.embedded_resource.contents.text = resource_contents.text
            return True
        elif isinstance(resource_contents, types.BlobResourceContents):  # type: ignore
            result.embedded_resource.contents.blob = base64.b64decode(resource_contents.blob)
            return True
    elif isinstance(content_block, types.ResourceLink):  # type: ignore
        result.resource_link.uri = str(content_block.uri)
        if content_block.name:
            result.resource_link.name = content_block.name
        return True
    return False


def unstructured_tool_output_to_proto(
    tool_output: Sequence[types.ContentBlock],
) -> list[mcp_pb2.CallToolResponse.Content]:
    """Converts unstructured tool output to a list of CallToolResponse protos."""
    logger.info("unstructured_tool_output_to_proto: tool_output=%s", tool_output)
    if not tool_output:
        return []

    items = tool_output
    contents: list[mcp_pb2.CallToolResponse.Content] = []
    for item in items:
        content_item = mcp_pb2.CallToolResponse.Content()
        if _populate_content_from_content_block(item, content_item):
            contents.append(content_item)
        else:
            logger.error("Item is not a valid content block: %s", item)
            return []
    return contents


def proto_result_to_content(
    proto_results: list[mcp_pb2.CallToolResponse.Content],
    structured_content: dict[str, Any] | None = None,
    is_error: bool = False,
) -> types.CallToolResult:
    """Converts a CallToolResponse.Content proto to a types.CallToolResult."""
    content: list[types.ContentBlock] = []
    for proto_result in proto_results:
        if proto_result.HasField("text"):
            content.append(types.TextContent(type="text", text=proto_result.text.text))
        elif proto_result.HasField("image"):
            content.append(
                types.ImageContent(
                    type="image",
                    data=base64.b64encode(proto_result.image.data).decode("utf-8"),
                    mimeType=proto_result.image.mime_type,
                )
            )
        elif proto_result.HasField("audio"):
            content.append(
                types.AudioContent(
                    type="audio",
                    data=base64.b64encode(proto_result.audio.data).decode("utf-8"),
                    mimeType=proto_result.audio.mime_type,
                )
            )
        elif proto_result.HasField("embedded_resource"):
            resource_contents = proto_result.embedded_resource.contents
            res_content = None
            if resource_contents.text:
                res_content = types.TextResourceContents(
                    uri=AnyUrl(resource_contents.uri),
                    mimeType=resource_contents.mime_type,
                    text=resource_contents.text,
                )
            elif resource_contents.blob:
                res_content = types.BlobResourceContents(
                    uri=AnyUrl(resource_contents.uri),
                    mimeType=resource_contents.mime_type,
                    blob=base64.b64encode(resource_contents.blob).decode("utf-8"),
                )
            if res_content:
                content.append(types.EmbeddedResource(type="resource", resource=res_content))
        elif proto_result.HasField("resource_link"):
            content.append(
                types.ResourceLink(
                    name=proto_result.resource_link.name,
                    type="resource_link",
                    uri=AnyUrl(proto_result.resource_link.uri),
                )
            )
    return types.CallToolResult(
        content=content,
        structuredContent=structured_content,
        isError=is_error,
    )


UnstructuredContent: TypeAlias = Iterable[types.ContentBlock]
StructuredContent: TypeAlias = dict[str, Any]
CombinationContent: TypeAlias = tuple[UnstructuredContent, StructuredContent]
ToolResult: TypeAlias = UnstructuredContent | StructuredContent | CombinationContent


class ToolOutputValidationError(Exception):
    """Exception raised for tool output validation errors."""


def normalize_and_validate_tool_results(
    results: ToolResult, tool: types.Tool | None
) -> tuple[Sequence[types.ContentBlock] | None, StructuredContent | None]:
    """Normalizes and validates tool results."""
    unstructured_content: UnstructuredContent | None
    maybe_structured_content: StructuredContent | None
    if isinstance(results, tuple) and len(results) == 2:
        # tool returned both structured and unstructured content
        unstructured_content, maybe_structured_content = cast(CombinationContent, results)
    elif isinstance(results, dict):
        # tool returned structured content only
        maybe_structured_content = cast(StructuredContent, results)
        unstructured_content = [types.TextContent(type="text", text=json.dumps(results, indent=2))]
    elif hasattr(results, "__iter__"):
        # tool returned unstructured content only
        unstructured_content = cast(UnstructuredContent, results)
        maybe_structured_content = None
    else:
        raise ToolOutputValidationError(f"Unexpected return type from tool: {type(results).__name__}")

    # output validation
    if tool and tool.outputSchema:
        if maybe_structured_content is None:
            raise ToolOutputValidationError(
                "Output validation error: outputSchema defined but no structured output returned"
            )
        else:
            try:
                jsonschema.validate(instance=maybe_structured_content, schema=tool.outputSchema)
            except jsonschema.ValidationError as e:
                raise ToolOutputValidationError(f"Output validation error: {e.message}") from e

    return (list(unstructured_content) if unstructured_content else None), maybe_structured_content


async def generate_call_tool_request(
    request_params: types.CallToolRequestParams | types.ProgressNotification,
) -> mcp_pb2.CallToolRequest:
    """Generates CallToolRequest protos from a stream of request params."""
    request = mcp_pb2.CallToolRequest()

    if isinstance(request_params, types.CallToolRequestParams):
        name = request_params.name
        arguments = request_params.arguments
        meta = request_params.meta
        if meta and meta.progressToken is not None:
            logger.info(
                "Forwarding progressToken %s for tool %s",
                meta.progressToken,
                name,
            )
            request.common.progress.progress_token = str(meta.progressToken)
        args_struct = None
        if arguments:
            try:
                args_struct = json_format.ParseDict(arguments, struct_pb2.Struct())
            except json_format.ParseError as e:
                error_message = f'Failed to parse tool arguments for "{name}": {e}'
                logger.error(error_message, exc_info=True)
                raise McpError(ErrorData(code=types.PARSE_ERROR, message=error_message)) from e
        request.request.name = name
        if args_struct:
            request.request.arguments.CopyFrom(args_struct)

    elif isinstance(request_params, types.ProgressNotification):  # type: ignore
        progress_token = request_params.params.progressToken
        progress = request_params.params.progress
        total = request_params.params.total
        message = request_params.params.message

        request.common.progress.progress_token = str(progress_token)
        request.common.progress.progress = progress
        if total is not None:
            request.common.progress.total = total
        if message is not None:
            request.common.progress.message = message

    return request


async def generate_call_tool_requests(
    request_params_iterable: AsyncGenerator[
        types.CallToolRequestParams | types.ProgressNotification, None
    ],
) -> AsyncGenerator[mcp_pb2.CallToolRequest, None]:
    """Generates CallToolRequest protos from a stream of request params."""
    async for request_params in request_params_iterable:
        yield await generate_call_tool_request(request_params)
