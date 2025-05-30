"""OpenAPI specification parser and validator."""

from typing import Any

import yaml
from fastapi import HTTPException, status
from loguru import logger
from pydantic import BaseModel


class ParsedEndpoint(BaseModel):
    """Structured representation of an API endpoint."""

    method: str
    path: str
    summary: str | None
    description: str | None
    parameters: list[dict[str, Any]]
    request_body: dict[str, Any] | None
    responses: dict[str, Any]


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
        # Try to parse as YAML (will also work for JSON as it's a subset of YAML)
        spec = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        logger.error(f"Failed to parse spec: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid YAML/JSON format",
        ) from exc

    # Validate required OpenAPI fields
    if not isinstance(spec, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Spec must be a YAML/JSON object",
        )

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

    # Extract endpoints
    endpoints: list[ParsedEndpoint] = []
    for path, path_item in spec["paths"].items():
        if not isinstance(path_item, dict):
            continue

        for method, operation in path_item.items():
            if not isinstance(operation, dict) or method.upper() not in {
                "GET",
                "POST",
                "PUT",
                "DELETE",
                "PATCH",
                "HEAD",
                "OPTIONS",
            }:
                continue

            endpoints.append(
                ParsedEndpoint(
                    method=method.upper(),
                    path=path,
                    summary=operation.get("summary"),
                    description=operation.get("description"),
                    parameters=operation.get("parameters", []),
                    request_body=operation.get("requestBody"),
                    responses={
                        str(code): details
                        for code, details in operation.get("responses", {}).items()
                    },
                )
            )

    return ParsedSpec(
        title=spec["info"].get("title", "Untitled API"),
        version=spec["info"].get("version", "0.0.0"),
        description=spec["info"].get("description"),
        endpoints=endpoints,
        components=spec.get("components", {}),
    )
