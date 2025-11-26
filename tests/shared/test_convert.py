"""Test conversion utilities."""

from datetime import timedelta
import unittest
import unittest.mock
import pytest

from google.protobuf import json_format
from google.protobuf import duration_pb2
from google.protobuf.struct_pb2 import Struct

from mcp.shared import convert
from mcp.shared.exceptions import McpError
from mcp import types
from mcp.proto import mcp_pb2


def test_ttl_from_timedelta():
  """Test ttl_from_timedelta."""
  delta = timedelta(seconds=1, microseconds=500000)
  ttl_proto = convert.ttl_from_timedelta(delta)
  assert ttl_proto == duration_pb2.Duration(seconds=1, nanos=500000000)

  delta = timedelta(microseconds=500000)
  ttl_proto = convert.ttl_from_timedelta(delta)
  assert ttl_proto == duration_pb2.Duration(seconds=0, nanos=500000000)

  delta = timedelta(seconds=1)
  ttl_proto = convert.ttl_from_timedelta(delta)
  assert ttl_proto == duration_pb2.Duration(seconds=1, nanos=0)

  delta = timedelta(seconds=0)
  ttl_proto = convert.ttl_from_timedelta(delta)
  assert ttl_proto == duration_pb2.Duration(seconds=0, nanos=0)


def test_timedelta_from_ttl():
  """Test timedelta_from_ttl."""
  ttl_proto = duration_pb2.Duration(seconds=1, nanos=500000000)
  delta = convert.timedelta_from_ttl(ttl_proto)
  assert delta == timedelta(seconds=1, microseconds=500000)

  ttl_proto = duration_pb2.Duration(seconds=0, nanos=500000000)
  delta = convert.timedelta_from_ttl(ttl_proto)
  assert delta == timedelta(microseconds=500000)

  ttl_proto = duration_pb2.Duration(seconds=1, nanos=0)
  delta = convert.timedelta_from_ttl(ttl_proto)
  assert delta == timedelta(seconds=1)

  ttl_proto = duration_pb2.Duration(seconds=0, nanos=0)
  delta = convert.timedelta_from_ttl(ttl_proto)
  assert delta == timedelta(seconds=0)


def test_resource_type_to_proto_valid():
  """Test conversion of a valid types.Resource to a proto message."""
  resource_type = types.Resource(
      uri=types.AnyUrl("test://resource"),
      name="test_resource",
      title="Test Resource",
      description="A test resource",
      mimeType="text/plain",
      size=123,
      annotations=types.Annotations(audience=["user"], priority=0.5),
  )
  expected_resource_proto = mcp_pb2.Resource(
      uri="test://resource",
      name="test_resource",
      title="Test Resource",
      description="A test resource",
      mime_type="text/plain",
      size=123,
      annotations=mcp_pb2.Annotations(audience=[mcp_pb2.ROLE_USER], priority=0.5),
  )

  converted_resource_proto = convert.resource_type_to_proto(resource_type)
  assert converted_resource_proto == expected_resource_proto


def test_resource_types_to_protos():
  """Test conversion of a list of types.Resource objects."""
  resource_types = [
      types.Resource(
          uri=types.AnyUrl("test://resource1"),
          name="resource1",
          title="Resource 1",
          description="Resource 1",
          mimeType="text/plain",
          size=100,
      ),
      types.Resource(
          uri=types.AnyUrl("test://resource2"),
          name="resource2",
          title="Resource 2",
          description="Resource 2",
          mimeType="application/json",
          size=200,
      ),
  ]
  expected_protos = [
      mcp_pb2.Resource(
          uri="test://resource1",
          name="resource1",
          title="Resource 1",
          description="Resource 1",
          mime_type="text/plain",
          size=100,
      ),
      mcp_pb2.Resource(
          uri="test://resource2",
          name="resource2",
          title="Resource 2",
          description="Resource 2",
          mime_type="application/json",
          size=200,
      ),
  ]

  converted_protos = convert.resource_types_to_protos(resource_types)
  for converted_proto, expected_proto in zip(converted_protos, expected_protos):
    assert converted_proto == expected_proto


def test_resource_proto_to_type():
    """Test conversion of a Resource proto to a types.Resource object."""
    resource_proto = mcp_pb2.Resource(
        uri="test://resource",
        name="test_resource",
        title="Test Resource",
        description="A test resource",
        mime_type="text/plain",
        size=123,
        annotations=mcp_pb2.Annotations(audience=[mcp_pb2.ROLE_USER], priority=0.5),
    )
    expected_resource_type = types.Resource(
        uri=types.AnyUrl("test://resource"),
        name="test_resource",
        title="Test Resource",
        description="A test resource",
        mimeType="text/plain",
        size=123,
        annotations=types.Annotations(audience=["user"], priority=0.5),
    )

    converted_resource_type = convert.resource_proto_to_type(resource_proto)
    assert converted_resource_type == expected_resource_type


def test_resource_protos_to_types():
    """Test conversion of a list of Resource protos to types.Resource objects."""
    resource_protos = [
        mcp_pb2.Resource(
            uri="test://resource1",
            name="resource1",
            title="Resource 1",
            description="Resource 1",
            mime_type="text/plain",
            size=100,
        ),
        mcp_pb2.Resource(
            uri="test://resource2",
            name="resource2",
            title="Resource 2",
            description="Resource 2",
            mime_type="application/json",
            size=200,
        ),
    ]
    expected_types = [
        types.Resource(
            uri=types.AnyUrl("test://resource1"),
            name="resource1",
            title="Resource 1",
            description="Resource 1",
            mimeType="text/plain",
            size=100,
        ),
        types.Resource(
            uri=types.AnyUrl("test://resource2"),
            name="resource2",
            title="Resource 2",
            description="Resource 2",
            mimeType="application/json",
            size=200,
        ),
    ]

    converted_types = convert.resource_protos_to_types(resource_protos)
    assert converted_types == expected_types


def test_resource_template_type_to_proto_valid():
    """Test conversion of a valid types.ResourceTemplate to a proto message."""
    resource_template_type = types.ResourceTemplate(
        uriTemplate="test://template/{name}",
        name="test_template",
        title="Test Template",
        description="A test template",
        mimeType="text/plain",
        annotations=types.Annotations(audience=["user"], priority=0.5),
    )
    expected_resource_template_proto = mcp_pb2.ResourceTemplate(
        uri_template="test://template/{name}",
        name="test_template",
        title="Test Template",
        description="A test template",
        mime_type="text/plain",
        annotations=mcp_pb2.Annotations(
            audience=[mcp_pb2.ROLE_USER], priority=0.5
        ),
    )

    converted_resource_template_proto = convert.resource_template_type_to_proto(
        resource_template_type
    )
    assert converted_resource_template_proto == expected_resource_template_proto


def test_resource_template_types_to_protos():
    """Test conversion of a list of types.ResourceTemplate objects."""
    resource_template_types = [
        types.ResourceTemplate(
            uriTemplate="test://template1/{id}",
            name="template1",
            title="Template 1",
            description="Template 1",
            mimeType="text/plain",
        ),
        types.ResourceTemplate(
            uriTemplate="test://template2/{id}",
            name="template2",
            title="Template 2",
            description="Template 2",
            mimeType="application/json",
        ),
    ]
    expected_protos = [
        mcp_pb2.ResourceTemplate(
            uri_template="test://template1/{id}",
            name="template1",
            title="Template 1",
            description="Template 1",
            mime_type="text/plain",
        ),
        mcp_pb2.ResourceTemplate(
            uri_template="test://template2/{id}",
            name="template2",
            title="Template 2",
            description="Template 2",
            mime_type="application/json",
        ),
    ]

    converted_protos = convert.resource_template_types_to_protos(
        resource_template_types
    )
    for converted_proto, expected_proto in zip(converted_protos, expected_protos):
        assert converted_proto == expected_proto


def test_resource_template_proto_to_type():
    """Test conversion of a ResourceTemplate proto to a types.ResourceTemplate object."""
    resource_template_proto = mcp_pb2.ResourceTemplate(
        uri_template="test://template/{name}",
        name="test_template",
        title="Test Template",
        description="A test template",
        mime_type="text/plain",
        annotations=mcp_pb2.Annotations(
            audience=[mcp_pb2.ROLE_USER], priority=0.5
        ),
    )
    expected_resource_template_type = types.ResourceTemplate(
        uriTemplate="test://template/{name}",
        name="test_template",
        title="Test Template",
        description="A test template",
        mimeType="text/plain",
        annotations=types.Annotations(audience=["user"], priority=0.5),
    )

    converted_resource_template_type = convert.resource_template_proto_to_type(
        resource_template_proto
    )
    assert converted_resource_template_type == expected_resource_template_type


def test_resource_template_protos_to_types():
    """Test conversion of a list of ResourceTemplate protos to types.ResourceTemplate objects."""
    resource_template_protos = [
        mcp_pb2.ResourceTemplate(
            uri_template="test://template1/{id}",
            name="template1",
            title="Template 1",
            description="Template 1",
            mime_type="text/plain",
        ),
        mcp_pb2.ResourceTemplate(
            uri_template="test://template2/{id}",
            name="template2",
            title="Template 2",
            description="Template 2",
            mime_type="application/json",
        ),
    ]
    expected_types = [
        types.ResourceTemplate(
            uriTemplate="test://template1/{id}",
            name="template1",
            title="Template 1",
            description="Template 1",
            mimeType="text/plain",
        ),
        types.ResourceTemplate(
            uriTemplate="test://template2/{id}",
            name="template2",
            title="Template 2",
            description="Template 2",
            mimeType="application/json",
        ),
    ]

    converted_types = convert.resource_template_protos_to_types(
        resource_template_protos
    )
    assert converted_types == expected_types


from mcp.server.lowlevel.helper_types import ReadResourceContents

class MockReadResourceContents(ReadResourceContents):
    def __init__(self, content: str | bytes, mime_type: str | None = None):
        self.content = content
        self.mime_type = mime_type

def test_read_resource_content_to_proto_text():
    """Test read_resource_content_to_proto with text content."""
    uri = "test://resource"
    content = [MockReadResourceContents(content="hello", mime_type="text/plain")]
    proto = convert.read_resource_content_to_proto(uri, content)
    assert proto[0].uri == uri
    assert proto[0].mime_type == "text/plain"
    assert proto[0].text == "hello"
    assert not proto[0].blob

def test_read_resource_content_to_proto_blob():
    """Test read_resource_content_to_proto with blob content."""
    uri = "test://resource"
    content = [MockReadResourceContents(content=b"hello", mime_type="application/octet-stream")]
    proto = convert.read_resource_content_to_proto(uri, content)
    assert proto[0].uri == uri
    assert proto[0].mime_type == "application/octet-stream"
    assert proto[0].blob == b"hello"
    assert not proto[0].text


def test_tool_proto_to_type_valid():
  """Test conversion of a valid tool proto to types.Tool."""
  input_schema = {"type": "object", "properties": {"a": {"type": "string"}}}
  output_schema = {"type": "object", "properties": {"b": {"type": "number"}}}
  tool_proto = mcp_pb2.Tool(
      name="test_tool",
      description="A test tool",
      input_schema=json_format.ParseDict(input_schema, Struct()),
      output_schema=json_format.ParseDict(output_schema, Struct()),
  )
  expected_tool_type = types.Tool(
      name="test_tool",
      description="A test tool",
      inputSchema=input_schema,
      outputSchema=output_schema,
  )

  converted_tool = convert.tool_proto_to_type(tool_proto)

  assert converted_tool == expected_tool_type


def test_tool_proto_to_type_empty_schemas():
  """Test conversion with empty input and output schemas."""
  tool_proto = mcp_pb2.Tool(
      name="empty_tool",
      description="No schemas",
      input_schema=json_format.ParseDict({}, Struct()),
      output_schema=json_format.ParseDict({}, Struct()),
  )
  expected_tool_type = types.Tool(
      name="empty_tool",
      description="No schemas",
      inputSchema={},
      outputSchema={},
  )

  converted_tool = convert.tool_proto_to_type(tool_proto)

  assert converted_tool == expected_tool_type


def test_tool_proto_to_type_invalid_schema_json():
  """Test error handling with invalid JSON in schema."""
  # Create a proto with a schema that will cause json_format.MessageToDict to fail.
  # This is a bit tricky as Struct naturally handles valid JSON.
  # We'll mock json_format.MessageToDict to simulate a ParseError.
  input_schema = {"type": "object", "properties": {"a": {"type": "string"}}}
  output_schema = {"type": "object", "properties": {"b": {"type": "number"}}}
  tool_proto = mcp_pb2.Tool(
      name="bad_tool",
      description="Bad schema tool",
      input_schema=json_format.ParseDict(input_schema, Struct()),
      output_schema=json_format.ParseDict(output_schema, Struct()),
  )

  with pytest.raises(json_format.ParseError) as excinfo:
    with unittest.mock.patch.object(
        json_format,
        "MessageToDict",
        side_effect=json_format.ParseError("Invalid JSON"),
    ):
      convert.tool_proto_to_type(tool_proto)

  assert str(excinfo.value) == "Invalid JSON"


def test_tool_type_to_proto_valid():
  """Test conversion of a valid types.Tool to a proto message."""
  input_schema = {"type": "object", "properties": {"a": {"type": "string"}}}
  output_schema = {"type": "object", "properties": {"b": {"type": "number"}}}
  tool_type = types.Tool(
      name="test_tool",
      description="A test tool",
      inputSchema=input_schema,
      outputSchema=output_schema,
  )
  expected_tool_proto = mcp_pb2.Tool(
      name="test_tool",
      description="A test tool",
      input_schema=json_format.ParseDict(input_schema, Struct()),
      output_schema=json_format.ParseDict(output_schema, Struct()),
  )

  converted_tool_proto = convert.tool_type_to_proto(tool_type)
  assert converted_tool_proto == expected_tool_proto


def test_tool_type_to_proto_invalid_input_schema():
  """Test error handling with invalid input schema in tool_type_to_proto."""
  tool_type = types.Tool(
      name="bad_input_tool",
      description="Tool with bad input schema",
      inputSchema={"type": "invalid"},
      outputSchema={},
  )

  with pytest.raises(json_format.ParseError) as excinfo:
    with unittest.mock.patch.object(
        json_format,
        "ParseDict",
        side_effect=[json_format.ParseError("Invalid input schema"), None],
    ):
      convert.tool_type_to_proto(tool_type)

  assert str(excinfo.value) == "Invalid input schema"


def test_tool_type_to_proto_invalid_output_schema():
  """Test error handling with invalid output schema in tool_type_to_proto."""
  tool_type = types.Tool(
      name="bad_output_tool",
      description="Tool with bad output schema",
      inputSchema={},
      outputSchema={"type": "invalid"},
  )

  with pytest.raises(json_format.ParseError) as excinfo:
    with unittest.mock.patch.object(
        json_format,
        "ParseDict",
        side_effect=json_format.ParseError("Invalid output schema"),
    ):
      convert.tool_type_to_proto(tool_type)

  assert str(excinfo.value) == "Invalid output schema"


def test_tool_types_to_protos():
  """Test conversion of a list of types.Tool objects."""
  tool_types = [
      types.Tool(
          name="tool1", description="Tool 1", inputSchema={}, outputSchema={}
      ),
      types.Tool(
          name="tool2",
          description="Tool 2",
          inputSchema={"type": "string"},
          outputSchema={"type": "number"},
      ),
  ]
  expected_protos = [
      mcp_pb2.Tool(
          name="tool1",
          description="Tool 1",
          input_schema=json_format.ParseDict({}, Struct()),
          output_schema=json_format.ParseDict({}, Struct()),
      ),
      mcp_pb2.Tool(
          name="tool2",
          description="Tool 2",
          input_schema=json_format.ParseDict({"type": "string"}, Struct()),
          output_schema=json_format.ParseDict({"type": "number"}, Struct()),
      ),
  ]

  converted_protos = convert.tool_types_to_protos(tool_types)
  for converted_proto, expected_proto in zip(converted_protos, expected_protos):
    assert converted_proto == expected_proto


def test_tool_protos_to_types():
  """Test conversion of a list of proto messages."""
  tool_protos = [
      mcp_pb2.Tool(
          name="tool1",
          description="Tool 1",
          input_schema=json_format.ParseDict({}, Struct()),
          output_schema=json_format.ParseDict({}, Struct()),
      ),
      mcp_pb2.Tool(
          name="tool2",
          description="Tool 2",
          input_schema=json_format.ParseDict({"type": "string"}, Struct()),
          output_schema=json_format.ParseDict({"type": "number"}, Struct()),
      ),
  ]
  expected_types = [
      types.Tool(
          name="tool1",
          description="Tool 1",
          inputSchema={},
          outputSchema={},
      ),
      types.Tool(
          name="tool2",
          description="Tool 2",
          inputSchema={"type": "string"},
          outputSchema={"type": "number"},
      ),
  ]

  converted_types = convert.tool_protos_to_types(tool_protos)
  assert converted_types == expected_types


def test_tool_output_to_proto_text_content_object():
  """Test conversion of tool output as a TextContent object."""
  tool_output = types.TextContent(type="text", text="hello from object")
  converted_proto = convert.unstructured_tool_output_to_proto([tool_output])
  assert len(converted_proto) == 1
  assert converted_proto[0].text.text == "hello from object"


def test_tool_output_to_proto_image_content_object():
  """Test conversion of tool output as an ImageContent object."""
  tool_output = types.ImageContent(type="image", data="aGVsbG8=", mimeType="image/png")
  converted_proto = convert.unstructured_tool_output_to_proto([tool_output])
  assert len(converted_proto) == 1
  assert converted_proto[0].image.data == b"hello"
  assert converted_proto[0].image.mime_type == "image/png"


def test_tool_output_to_proto_audio_content_object():
  """Test conversion of tool output as an AudioContent object."""
  tool_output = types.AudioContent(type="audio", data="aGVsbG8=", mimeType="audio/mpeg")
  converted_proto = convert.unstructured_tool_output_to_proto([tool_output])
  assert len(converted_proto) == 1
  assert converted_proto[0].audio.data == b"hello"
  assert converted_proto[0].audio.mime_type == "audio/mpeg"





def test_tool_output_to_proto_embedded_text_resource_object():
  """Test conversion of tool output as an EmbeddedResource object with text."""
  tool_output = types.EmbeddedResource(
      type="resource",
      resource=types.TextResourceContents(
          uri=types.AnyUrl("test://resource"), mimeType="text/plain", text="hello"
      ),
  )
  converted_proto = convert.unstructured_tool_output_to_proto([tool_output])
  assert len(converted_proto) == 1
  assert converted_proto[0].embedded_resource.contents.uri == "test://resource"
  assert converted_proto[0].embedded_resource.contents.mime_type == "text/plain"
  assert converted_proto[0].embedded_resource.contents.text == "hello"


def test_tool_output_to_proto_embedded_blob_resource_object():
  """Test conversion of tool output as an EmbeddedResource object with blob."""
  tool_output = types.EmbeddedResource(
      type="resource",
      resource=types.BlobResourceContents(
          uri=types.AnyUrl("test://resource"), mimeType="app/foo", blob="aGVsbG8="
      ),
  )
  converted_proto = convert.unstructured_tool_output_to_proto([tool_output])
  assert len(converted_proto) == 1
  assert converted_proto[0].embedded_resource.contents.uri == "test://resource"
  assert converted_proto[0].embedded_resource.contents.mime_type == "app/foo"
  assert converted_proto[0].embedded_resource.contents.blob == b"hello"





def test_tool_output_to_proto_resource_link_object():
  """Test conversion of tool output as a ResourceLink object."""
  tool_output = types.ResourceLink(type="resource_link", name="", uri=types.AnyUrl("test://link"))
  converted_proto = convert.unstructured_tool_output_to_proto([tool_output])
  assert len(converted_proto) == 1
  assert converted_proto[0].resource_link.uri == "test://link"


def test_tool_output_to_proto_list_of_content_blocks():
    """Test conversion of tool output as a list of ContentBlock objects."""
    tool_output = [
        types.TextContent(type="text", text="hello"),
        types.ImageContent(type="image", data="aGVsbG8=", mimeType="image/png"),
        types.AudioContent(type="audio", data="YXVkaW8=", mimeType="audio/mpeg"),
        types.ResourceLink(type="resource_link", name="link", uri=types.AnyUrl("test://link")),
        types.EmbeddedResource(
            type="resource",
            resource=types.TextResourceContents(
                uri=types.AnyUrl("test://resource"), mimeType="text/plain", text="resource"
            ),
        ),
    ]
    converted_proto = convert.unstructured_tool_output_to_proto(tool_output)
    assert len(converted_proto) == 5
    assert converted_proto[0].text.text == "hello"
    assert converted_proto[1].image.data == b"hello"
    assert converted_proto[1].image.mime_type == "image/png"
    assert converted_proto[2].audio.data == b"audio"
    assert converted_proto[2].audio.mime_type == "audio/mpeg"
    assert converted_proto[3].resource_link.uri == "test://link"
    assert converted_proto[3].resource_link.name == "link"
    assert converted_proto[4].embedded_resource.contents.uri == "test://resource"
    assert converted_proto[4].embedded_resource.contents.mime_type == "text/plain"
    assert converted_proto[4].embedded_resource.contents.text == "resource"


def test_tool_output_to_proto_none():
  """Test conversion of tool output as None."""
  converted_proto = convert.unstructured_tool_output_to_proto([])
  assert converted_proto == []


def test_tool_output_to_proto_invalid_block_type():
  """Test tool_output_to_proto with an invalid content block type."""
  tool_output = MockInvalidContentBlock()
  result = convert.unstructured_tool_output_to_proto([tool_output])  # type: ignore[arg-type]
  assert len(result) == 0


class MockInvalidContentBlock:
  def __str__(self):
    return "MockInvalidContentBlock()"



def test_normalize_and_validate_tool_results_invalid_type():
    """Test normalize_and_validate_tool_results with invalid result type."""
    with pytest.raises(convert.ToolOutputValidationError):
        convert.normalize_and_validate_tool_results(123, None)


def test_normalize_and_validate_tool_results_missing_structured_output():
    """Test normalize_and_validate_tool_results with missing structured output."""
    tool = types.Tool(
        name="test_tool",
        description="Test tool",
        inputSchema={},
        outputSchema={"type": "object"},
    )
    with pytest.raises(convert.ToolOutputValidationError):
        convert.normalize_and_validate_tool_results(
            [types.TextContent(type="text", text="hello")], tool
        )


def test_normalize_and_validate_tool_results_invalid_structured_output():
    """Test normalize_and_validate_tool_results with invalid structured output."""
    tool = types.Tool(
        name="test_tool",
        description="Test tool",
        inputSchema={},
        outputSchema={"type": "object", "properties": {"a": {"type": "string"}}},
    )
    with pytest.raises(convert.ToolOutputValidationError):
        convert.normalize_and_validate_tool_results({"a": 123}, tool)


def test_proto_result_to_content_text():
  """Test conversion of proto result with text to types.CallToolResult."""
  proto_result = mcp_pb2.CallToolResponse.Content()
  proto_result.text.text = "hello"
  types_result = convert.proto_result_to_content([proto_result])
  assert types_result.content == [types.TextContent(type="text", text="hello")]
  assert types_result.structuredContent is None
  assert types_result.isError is False


def test_proto_result_to_content_image():
  """Test conversion of proto result with image to types.CallToolResult."""
  proto_result = mcp_pb2.CallToolResponse.Content()
  proto_result.image.data = b"hello"
  proto_result.image.mime_type = "image/png"
  types_result = convert.proto_result_to_content([proto_result])
  assert types_result.content == [
      types.ImageContent(type="image", data="aGVsbG8=", mimeType="image/png")
  ]
  assert types_result.structuredContent is None
  assert types_result.isError is False


def test_proto_result_to_content_audio():
  """Test conversion of proto result with audio to types.CallToolResult."""
  proto_result = mcp_pb2.CallToolResponse.Content()
  proto_result.audio.data = b"hello"
  proto_result.audio.mime_type = "audio/mpeg"
  types_result = convert.proto_result_to_content([proto_result])
  assert types_result.content == [
      types.AudioContent(type="audio", data="aGVsbG8=", mimeType="audio/mpeg")
  ]
  assert types_result.structuredContent is None
  assert types_result.isError is False


def test_proto_result_to_content_embedded_resource_text():
  """Test conversion of proto result with text resource to types.CallToolResult."""
  proto_result = mcp_pb2.CallToolResponse.Content()
  proto_result.embedded_resource.contents.uri = "test://resource"
  proto_result.embedded_resource.contents.mime_type = "text/plain"
  proto_result.embedded_resource.contents.text = "hello"
  types_result = convert.proto_result_to_content([proto_result])
  assert types_result.content[0].type == "resource"
  assert str(types_result.content[0].resource.uri) == "test://resource"
  assert types_result.content[0].resource.mimeType == "text/plain"
  assert types_result.content[0].resource.text == "hello"  # type: ignore[attr-defined]
  assert types_result.structuredContent is None
  assert types_result.isError is False


def test_proto_result_to_content_embedded_resource_blob():
  """Test conversion of proto result with blob resource to types.CallToolResult."""
  proto_result = mcp_pb2.CallToolResponse.Content()
  proto_result.embedded_resource.contents.uri = "test://resource"
  proto_result.embedded_resource.contents.mime_type = "application/octet-stream"
  proto_result.embedded_resource.contents.blob = b"blob"
  types_result = convert.proto_result_to_content([proto_result])
  assert types_result.content[0].type == "resource"
  assert str(types_result.content[0].resource.uri) == "test://resource"
  assert types_result.content[0].resource.mimeType == "application/octet-stream"
  assert types_result.content[0].resource.blob == "YmxvYg=="  # type: ignore[attr-defined]
  assert types_result.structuredContent is None
  assert types_result.isError is False


def test_proto_result_to_content_resource_link():
  """Test conversion of proto result with resource link to types.CallToolResult."""
  proto_result = mcp_pb2.CallToolResponse.Content()
  proto_result.resource_link.uri = "test://link"
  proto_result.resource_link.name = "Test Link"
  types_result = convert.proto_result_to_content([proto_result])
  assert types_result.content == [
      types.ResourceLink(type="resource_link", uri=types.AnyUrl("test://link"), name="Test Link")
  ]
  assert types_result.structuredContent is None
  assert types_result.isError is False


def test_proto_result_to_content_resource_link_no_name():
  """Test conversion of proto result with resource link but no name."""
  proto_result = mcp_pb2.CallToolResponse.Content()
  proto_result.resource_link.uri = "test://link"
  types_result = convert.proto_result_to_content([proto_result])
  assert types_result.content == [
      types.ResourceLink(type="resource_link", uri=types.AnyUrl("test://link"), name="")
  ]
  assert types_result.structuredContent is None
  assert types_result.isError is False


def test_proto_result_to_content_structured_content():
  """Test conversion of proto result with structured content to types.CallToolResult."""
  types_result = convert.proto_result_to_content(
      [], structured_content={"key": "value"}
  )
  assert types_result.content == []
  assert types_result.structuredContent == {"key": "value"}
  assert types_result.isError is False


def test_proto_result_to_content_error():
  """Test conversion of proto result with error to types.CallToolResult."""
  types_result = convert.proto_result_to_content([], is_error=True)
  assert types_result.content == []
  assert types_result.structuredContent is None
  assert types_result.isError is True


@pytest.mark.anyio
async def test_generate_call_tool_requests_call():
  """Test generation of call tool requests."""
  async def requests_gen():
    yield types.CallToolRequestParams(
        name="test_tool",
        arguments={"arg1": "value1"},
    )

  generator = convert.generate_call_tool_requests(requests_gen())
  request = await generator.__anext__()
  assert request.request.name == "test_tool"
  assert request.request.arguments == json_format.ParseDict(
      {"arg1": "value1"}, Struct()
  )


@pytest.mark.anyio
async def test_generate_call_tool_requests_progress():
  """Test generation of progress notification requests."""
  async def requests_gen():
    yield types.ProgressNotification(
        method="notifications/progress",
        params=types.ProgressNotificationParams(
            progressToken="token1", progress=50, total=100, message="In progress"
        )
    )

  generator = convert.generate_call_tool_requests(requests_gen())
  request = await generator.__anext__()
  assert request.common.progress.progress_token == "token1"
  assert request.common.progress.progress == 50
  assert request.common.progress.total == 100
  assert request.common.progress.message == "In progress"


@pytest.mark.anyio
async def test_generate_call_tool_requests_progress_minimal():
  """Test generation of progress notification requests with minimal fields."""
  async def requests_gen():
    yield types.ProgressNotification(
        method="notifications/progress",
        params=types.ProgressNotificationParams(
            progressToken="token1", progress=50, total=None, message=None
        )
    )

  generator = convert.generate_call_tool_requests(requests_gen())
  request = await generator.__anext__()
  assert request.common.progress.progress_token == "token1"
  assert request.common.progress.progress == 50
  assert request.common.progress.total == 0
  assert request.common.progress.message == ""


@pytest.mark.anyio
async def test_generate_call_tool_requests_progress_no_message():
  """Test generation of progress notification requests with no message."""
  async def requests_gen():
    yield types.ProgressNotification(
        method="notifications/progress",
        params=types.ProgressNotificationParams(
            progressToken="token1", progress=50, total=100, message=None
        )
    )

  generator = convert.generate_call_tool_requests(requests_gen())
  request = await generator.__anext__()
  assert request.common.progress.progress_token == "token1"
  assert request.common.progress.progress == 50
  assert request.common.progress.total == 100
  assert request.common.progress.message == ""


@pytest.mark.anyio
async def test_generate_call_tool_requests_progress_no_total():
  """Test generation of progress notification requests with no total."""
  async def requests_gen():
    yield types.ProgressNotification(
        method="notifications/progress",
        params=types.ProgressNotificationParams(
            progressToken="token1", progress=50, total=None, message="In progress"
        )
    )

  generator = convert.generate_call_tool_requests(requests_gen())
  request = await generator.__anext__()
  assert request.common.progress.progress_token == "token1"
  assert request.common.progress.progress == 50
  assert request.common.progress.total == 0
  assert request.common.progress.message == "In progress"


@pytest.mark.anyio
async def test_generate_call_tool_requests_bad_args():
  """Test generation of call tool requests with bad arguments."""
  async def requests_gen():
    yield types.CallToolRequestParams(
        name="test_tool",
        arguments={"arg1": set()}, # set is not serializable to JSON
    )

  generator = convert.generate_call_tool_requests(requests_gen())
  with pytest.raises(McpError):
    await generator.__anext__()
