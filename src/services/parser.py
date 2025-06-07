"""OpenAPI specification parser and validator."""

from typing import Any

import yaml
from fastapi import HTTPException, status
from loguru import logger
from openapi_spec_validator import validate
from prance import ResolvingParser  # type: ignore[import-untyped]
from pydantic import ConfigDict, Field

from src.core.models import BaseModel


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

    method: str
    path: str
    summary: str | None = None
    description: str | None = None
    parameters: list[ParsedParameter] = Field(default_factory=list)
    request_body: ParsedRequestBody | None = None
    responses: dict[str, ParsedResponse] = Field(default_factory=dict)

    @classmethod
    def from_operation(
        cls: type["ParsedEndpoint"], method: str, path: str, operation: dict
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
    def _parse_parameters(params: list[Any]) -> list[ParsedParameter]:
        """Parse operation parameters."""
        parameters = []
        for param in params:
            if not isinstance(param, dict):
                continue
            parameters.append(
                ParsedParameter(
                    name=param.get("name", ""),
                    location=param.get("in", "query"),
                    required=param.get("required", False),
                    api_schema=OpenAPISchema(**param.get("schema", {})),
                    description=param.get("description"),
                )
            )
        return parameters

    @staticmethod
    def _parse_request_body(
        body: dict | None, method: str, path: str
    ) -> ParsedRequestBody | None:
        """Parse operation request body."""
        if not body:
            return None

        if not isinstance(body, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid request body at {path} {method}: {body}",
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
        parsed_responses = {}
        for status_code, response_info in responses.items():
            if not isinstance(response_info, dict):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid response at {path} {method}: {response_info}",
                )

            content_type, api_schema = parse_schema(response_info.get("content", {}))
            parsed_responses[str(status_code)] = ParsedResponse(
                status_code=str(status_code),
                description=response_info.get("description"),
                content_type=content_type if content_type else None,
                api_schema=api_schema,
            )
        return parsed_responses


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


class ParsedSpec(BaseModel):
    """Structured representation of an OpenAPI spec."""

    title: str
    version: str
    description: str | None
    endpoints: list[ParsedEndpoint]
    components: dict[str, Any]


def parse_openapi_spec(content: str) -> ParsedSpec:
    """
    Parse and validate an OpenAPI specification.

    Args:
        content: The raw OpenAPI spec content (JSON or YAML)

    Returns:
        ParsedSpec: A structured representation of the spec

    Raises:
        HTTPException: If the spec is invalid or missing required fields
    """
    try:
        # Convert dict/list to YAML string if needed
        if isinstance(content, dict | list):
            content = yaml.dump(content)

        # Parse and validate basic structure
        spec = _parse_yaml(content)

        # Attempt to resolve references
        validated_spec = _resolve_references(content, spec)

        # Validate the resolved spec
        _validate_spec(validated_spec)

        return _parse_endpoints(validated_spec)

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to parse OpenAPI spec")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse OpenAPI spec: {exc}",
        ) from exc


def _parse_yaml(content: str) -> dict[str, Any]:
    try:
        spec = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        logger.error(f"Failed to parse YAML: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid YAML/JSON format: {exc}",
        ) from exc

    # Validate basic structure
    if not isinstance(spec, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Spec must be a YAML/JSON object",
        )

    # Validate required OpenAPI fields
    if "openapi" not in spec:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing 'openapi' version field",
        )

    if "info" not in spec:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing 'info' section",
        )

    if "paths" not in spec:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing 'paths' section",
        )

    return spec


def _resolve_references(content: str, fallback_spec: dict) -> dict[str, Any]:
    """Resolve OpenAPI spec references with fallback to basic spec."""
    try:
        parser = ResolvingParser(
            spec_string=content,
            backend="openapi-spec-validator",
            strict=False,
        )
    except Exception as resolve_error:
        logger.warning(
            f"Reference resolution failed, using basic spec: {resolve_error}"
        )
        return fallback_spec
    else:
        return parser.specification


def _validate_spec(spec: dict[str, Any]) -> None:
    """Validate OpenAPI spec structure."""
    try:
        spec_str = yaml.dump(spec) if isinstance(spec, dict) else spec
        validate(yaml.safe_load(spec_str))
    except Exception as validation_error:
        logger.warning(f"OpenAPI validation failed: {validation_error}")


def _parse_endpoints(validated_spec: dict[str, Any]) -> ParsedSpec:
    """Parse endpoints from an OpenAPI specification."""
    endpoints: list[ParsedEndpoint] = []
    for path, path_item in validated_spec.get("paths", {}).items():
        if not isinstance(path_item, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid path item at {path}: not a dict",
            )

        for method, operation in path_item.items():
            if not isinstance(operation, dict):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid operation at {path} {method}: not a dict",
                )
            if not _is_valid_method(method):
                continue

            endpoints.append(ParsedEndpoint.from_operation(method, path, operation))

    return ParsedSpec(
        title=validated_spec["info"].get("title", "Untitled API"),
        version=validated_spec["info"].get("version", "0.0.0"),
        description=validated_spec["info"].get("description"),
        endpoints=endpoints,
        components=validated_spec.get("components", {}),
    )


def _is_valid_method(method: str) -> bool:
    """Check if a method is a valid HTTP method."""
    return method.upper() in {
        "GET",
        "POST",
        "PUT",
        "DELETE",
        "PATCH",
        "HEAD",
        "OPTIONS",
    }
