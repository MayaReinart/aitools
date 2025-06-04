"""OpenAPI specification parser and validator."""

from typing import Any

import yaml
from fastapi import HTTPException, status
from loguru import logger
from prance import BaseParser, ValidationError  # type: ignore[import-untyped]
from pydantic import BaseModel


class ParsedEndpoint(BaseModel):
    """Structured representation of an API endpoint."""

    method: str
    path: str
    summary: str | None = None
    description: str | None = None
    parameters: list[dict[str, Any]] = []
    request_body: dict[str, Any] | None = None
    responses: dict[str, Any]

    @classmethod
    def from_operation(
        cls: type["ParsedEndpoint"], method: str, path: str, operation: dict[str, Any]
    ) -> "ParsedEndpoint":
        """Create ParsedEndpoint from OpenAPI operation object.

        Args:
            method: HTTP method
            path: URL path
            operation: OpenAPI operation object
        """
        responses = {
            str(code): details
            for code, details in operation.get("responses", {}).items()
        }

        # Handle parameters separately to ensure correct typing
        parameters = operation.get("parameters", [])
        if not isinstance(parameters, list):
            parameters = []

        return cls(
            method=method.upper(),
            path=path,
            parameters=parameters,
            **{k: operation.get(k) for k in ["summary", "description", "requestBody"]},
            responses=responses,
        )


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
    # First step: Parse YAML and validate basic structure
    spec = _parse_yaml(content)

    # Second step: Full OpenAPI validation with Prance
    try:
        parser = BaseParser(spec_string=content, backend="openapi-spec-validator")
        validated_spec = parser.specification
    except ValidationError as exc:
        logger.error(f"Unexpected error during OpenAPI validation: {exc}")
        # Fall back to using the PyYAML parsed spec
        logger.warning("Falling back to basic YAML parsed spec")
        validated_spec = spec

    # Third step: Extract endpoints using the validated spec
    return _parse_endpoints(validated_spec)


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


def _parse_endpoints(validated_spec: dict[str, Any]) -> ParsedSpec:
    endpoints: list[ParsedEndpoint] = []
    for path, path_item in validated_spec.get("paths", {}).items():
        if not isinstance(path_item, dict):
            logger.warning(f"Skipping invalid path item at {path}: not a dict")
            continue

        for method, operation in path_item.items():
            if not _is_valid_operation(operation) or not _is_valid_method(method):
                logger.debug(f"Skipping invalid operation at {path} {method}")
                continue

            endpoints.append(ParsedEndpoint.from_operation(method, path, operation))

    return ParsedSpec(
        title=validated_spec["info"].get("title", "Untitled API"),
        version=validated_spec["info"].get("version", "0.0.0"),
        description=validated_spec["info"].get("description"),
        endpoints=endpoints,
        components=validated_spec.get("components", {}),
    )


def _is_valid_operation(operation: dict[str, Any]) -> bool:
    """Check if an operation is valid according to OpenAPI spec."""
    return (
        isinstance(operation, dict)
        and "responses" in operation  # Responses are required in OpenAPI
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
