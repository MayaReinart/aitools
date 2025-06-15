"""Data models for API specification parsing and analysis."""

import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class OpenAPISchema(BaseModel):
    """OpenAPI schema object model."""

    type: str | None = None
    format: str | None = None
    description: str | None = None
    items: dict[str, Any] | None = None
    properties: dict[str, Any] | None = None
    required: list[str] | None = None
    enum: list[Any] | None = None
    default: Any | None = None


class ParsedParameter(BaseModel):
    """Parsed parameter information."""

    name: str
    location: str
    required: bool = False
    api_schema: OpenAPISchema | None = None
    description: str | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ParsedRequestBody(BaseModel):
    """Parsed request body information."""

    required: bool = False
    content_type: str
    api_schema: OpenAPISchema | None = None
    description: str | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ParsedResponse(BaseModel):
    """Parsed response information."""

    status_code: str
    description: str | None = None
    content_type: str | None = None
    api_schema: OpenAPISchema | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ParsedEndpoint(BaseModel):
    """Parsed endpoint information."""

    # Error messages
    INVALID_BODY = "Invalid request body at {path} {method}: {body}"
    INVALID_RESPONSE = "Invalid response at {path} {method}: {response}"

    method: str
    path: str
    summary: str | None = None
    description: str | None = None
    parameters: list[ParsedParameter] = Field(default_factory=list)
    request_body: ParsedRequestBody | None = None
    responses: dict[str, ParsedResponse] = Field(default_factory=dict)

    @classmethod
    def from_operation(
        cls: type["ParsedEndpoint"], method: str, path: str, operation: dict[str, Any]
    ) -> "ParsedEndpoint":
        """Create an endpoint from an OpenAPI operation object."""
        return cls(
            method=method.upper(),
            path=path,
            summary=operation.get("summary"),
            description=operation.get("description"),
            parameters=cls._parse_parameters(operation.get("parameters", [])),
            request_body=cls._parse_request_body(
                operation.get("requestBody"), method, path
            ),
            responses=cls._parse_responses(
                operation.get("responses", {}), method, path
            ),
        )

    @staticmethod
    def _parse_parameters(
        params: list[Any] | dict[str, Any] | None,
    ) -> list[ParsedParameter]:
        """Parse operation parameters.

        Args:
            params: List of parameters or dict of parameters

        Returns:
            List of parsed parameters
        """
        parameters: list[ParsedParameter] = []

        # Handle case where params is None
        if params is None:
            return parameters

        # Handle case where params is a dict (convert to list)
        if isinstance(params, dict):
            params = list(params.values())

        # Handle case where params is not a list
        if not isinstance(params, list):
            logger.warning(f"Invalid parameters format: {params}")
            return parameters

        for param in params:
            if not isinstance(param, dict):
                logger.warning(f"Invalid parameter format: {param}")
                continue

            try:
                parameters.append(
                    ParsedParameter(
                        name=param.get("name", ""),
                        location=param.get("in", "query"),
                        required=param.get("required", False),
                        api_schema=OpenAPISchema(**param.get("schema", {})),
                        description=param.get("description"),
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to parse parameter: {e}")
                continue

        return parameters

    @staticmethod
    def _parse_request_body(
        body: dict[str, Any] | None, method: str, path: str
    ) -> ParsedRequestBody | None:
        """Parse operation request body."""
        if not body:
            return None

        if not isinstance(body, dict):
            raise TypeError(
                ParsedEndpoint.INVALID_BODY.format(path=path, method=method, body=body)
            )

        content_type, api_schema = parse_schema(body["content"])
        return ParsedRequestBody(
            required=body.get("required", False),
            content_type=content_type,
            api_schema=api_schema,
            description=body.get("description"),
        )

    @staticmethod
    def _parse_responses(
        responses: dict[str, Any], method: str, path: str
    ) -> dict[str, ParsedResponse]:
        """Parse operation responses."""
        parsed_responses: dict[str, ParsedResponse] = {}
        for status_code, response_info in responses.items():
            if not isinstance(response_info, dict):
                raise TypeError(
                    ParsedEndpoint.INVALID_RESPONSE.format(
                        path=path, method=method, response=response_info
                    )
                )

            content_type, api_schema = parse_schema(response_info.get("content", {}))
            parsed_responses[str(status_code)] = ParsedResponse(
                status_code=str(status_code),
                description=response_info.get("description"),
                content_type=content_type if content_type else None,
                api_schema=api_schema,
            )
        return parsed_responses


class ParsedSpec(BaseModel):
    """Structured representation of an OpenAPI spec."""

    title: str
    version: str
    description: str | None
    endpoints: list[ParsedEndpoint]
    components: dict[str, Any]


def parse_schema(content: dict[str, Any]) -> tuple[str, OpenAPISchema | None]:
    """Parse a schema from a content dictionary."""
    if not content:
        return "", None

    content_type, schema_info = next(iter(content.items()), ("", {}))
    if not isinstance(schema_info, dict) or "schema" not in schema_info:
        return content_type, None

    schema_data = schema_info["schema"]
    return content_type, OpenAPISchema(**schema_data) if isinstance(
        schema_data, dict
    ) else None
