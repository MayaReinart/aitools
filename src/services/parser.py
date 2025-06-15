"""OpenAPI specification parser and validator."""

import json
from collections.abc import Hashable, Mapping
from pathlib import Path
from typing import Any

import yaml
from loguru import logger
from openapi_spec_validator import validate_spec

from src.services.models import OpenAPISchema, ParsedEndpoint, ParsedSpec


class SpecValidationError(Exception):
    """Base class for OpenAPI specification validation errors."""

    MISSING_VERSION = "Missing 'openapi' or 'swagger' version field"
    UNSUPPORTED_VERSION = "Unsupported specification version: {version}"
    INVALID_PATH_ITEM = "Invalid path item at {path}: not a dict"
    INVALID_OPERATION = "Invalid operation at {path} {method}: not a dict"
    PARSE_SCHEMA_ERROR = "Failed to parse schema from content: {content}"
    PARSE_SPEC_ERROR = "Failed to parse specification: {error}"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def parse_schema(content: dict[str, Any]) -> tuple[str, OpenAPISchema | None]:
    """Parse schema from content dictionary.

    Args:
        content: Content dictionary containing schema information

    Returns:
        Tuple of content type and parsed schema
    """

    def _raise_parse_schema_error(content: dict) -> tuple[str, OpenAPISchema | None]:
        raise SpecValidationError(
            SpecValidationError.PARSE_SCHEMA_ERROR.format(content=content)
        )

    if not content:
        return "", None

    content_type = next(iter(content.keys()))
    schema_info = content[content_type]
    if not schema_info or "schema" not in schema_info:
        return content_type, None

    schema_data = schema_info["schema"]
    if isinstance(schema_data, dict):
        return content_type, OpenAPISchema(**schema_data)
    if schema_data is None:
        return content_type, None
    return _raise_parse_schema_error(content)


def _validate_spec(spec: Mapping[Hashable, Any], spec_type: str) -> None:
    """Validate an OpenAPI specification.

    Args:
        spec: The specification to validate
        spec_type: The type of specification (openapi or swagger)

    Raises:
        SpecValidationError: If the specification is invalid
    """
    if spec_type.startswith("3."):
        validate_spec(spec)
        logger.info("Validated OpenAPI 3.0 specification")
    elif spec_type.startswith("2."):
        validate_spec(spec)
        logger.info("Validated Swagger 2.0 specification")
    else:
        raise SpecValidationError(
            SpecValidationError.UNSUPPORTED_VERSION.format(version=spec_type)
        )


def _raise_validation_error(error: Exception) -> None:
    """Raise a validation error with the given error message.

    Args:
        error: The error to wrap

    Raises:
        SpecValidationError: The wrapped error
    """
    raise SpecValidationError(
        SpecValidationError.PARSE_SPEC_ERROR.format(error=error)
    ) from error


def _raise_missing_version() -> None:
    """Raise a missing version error."""
    raise SpecValidationError(SpecValidationError.MISSING_VERSION)


def parse_spec(spec_path: Path) -> ParsedSpec:
    """Parse an OpenAPI specification from a file.

    Args:
        spec_path: Path to the specification file

    Returns:
        ParsedSpec: The parsed specification

    Raises:
        SpecValidationError: If the specification is invalid
    """
    try:
        # Read the file
        with spec_path.open() as f:
            if spec_path.suffix.lower() in [".yaml", ".yml"]:
                spec = yaml.safe_load(f)
            else:
                spec = json.load(f)

        # Determine spec type and validate
        spec_type = spec.get("openapi") or spec.get("swagger")

        if not spec_type:
            _raise_missing_version()

        try:
            _validate_spec(spec, spec_type)
        except Exception as e:
            logger.warning(f"Specification validation warning: {e}")
            # Continue processing even with validation warnings

    except Exception as e:
        logger.error(f"Error parsing specification: {e}")
        _raise_validation_error(e)

    return _parse_endpoints(spec)


def _parse_endpoints(validated_spec: dict[str, Any]) -> ParsedSpec:
    """Parse endpoints from validated specification.

    Args:
        validated_spec: The validated specification

    Returns:
        ParsedSpec: The parsed specification with endpoints
    """
    endpoints: list[ParsedEndpoint] = []
    for path, path_item in validated_spec.get("paths", {}).items():
        if not isinstance(path_item, dict):
            logger.warning(f"Invalid path item at {path}: not a dict")
            continue

        for method, operation in path_item.items():
            if not isinstance(operation, dict):
                logger.warning(f"Invalid operation at {path} {method}: not a dict")
                continue

            if not _is_valid_method(method):
                continue

            try:
                # Fix invalid parameters format if needed
                if "parameters" in operation and not isinstance(
                    operation["parameters"], list
                ):
                    logger.warning(
                        f"Invalid parameters format at {path} {method}, "
                        "converting to list"
                    )
                    if isinstance(operation["parameters"], dict):
                        operation["parameters"] = list(operation["parameters"].values())
                    else:
                        operation["parameters"] = []

                endpoints.append(ParsedEndpoint.from_operation(method, path, operation))
            except Exception as e:
                logger.warning(f"Failed to parse endpoint {path} {method}: {e}")
                continue

    if not endpoints:
        logger.warning("No valid endpoints found in specification")

    return ParsedSpec(
        title=validated_spec["info"].get("title", "Untitled API"),
        version=validated_spec["info"].get("version", "1.0.0"),
        description=validated_spec["info"].get("description"),
        endpoints=endpoints,
        components=validated_spec.get("components", {}),
    )


def _is_valid_method(method: str) -> bool:
    """Check if a method is valid.

    Args:
        method: The HTTP method to check

    Returns:
        True if the method is valid
    """
    return method.upper() in {
        "GET",
        "POST",
        "PUT",
        "DELETE",
        "PATCH",
        "HEAD",
        "OPTIONS",
    }
