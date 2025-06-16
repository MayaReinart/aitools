"""OpenAPI specification parser and validator."""

import json
from collections.abc import Hashable, Mapping
from pathlib import Path
from typing import Any

import yaml
from loguru import logger
from openapi_spec_validator import validate

from src.services.models import OpenAPISchema, ParsedEndpoint, ParsedSpec


class SpecValidationError(Exception):
    """Base class for OpenAPI specification validation errors."""

    MISSING_VERSION = "Missing 'openapi' or 'swagger' version field"
    UNSUPPORTED_VERSION = "Unsupported specification version: {version}"
    INVALID_PATH_ITEM = "Invalid path item at {path}: not a dict"
    INVALID_OPERATION = "Invalid operation at {path} {method}: not a dict"
    INVALID_RESPONSE = "Invalid response at {path} {method}: not a dict"
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
        validate(spec)
        logger.info("Validated OpenAPI 3.0 specification")
    elif spec_type.startswith("2."):
        validate(spec)
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


def _parse_spec_from_text(content: str | dict[str, Any]) -> ParsedSpec:
    """Parse an OpenAPI specification from text content.

    Args:
        content: The specification content as string or dict

    Returns:
        ParsedSpec: The parsed specification

    Raises:
        SpecValidationError: If the specification is invalid
    """
    try:
        # Convert string to dict if needed
        if isinstance(content, str):
            try:
                spec = yaml.safe_load(content)
            except yaml.YAMLError:
                try:
                    spec = json.loads(content)
                except json.JSONDecodeError as e:
                    raise SpecValidationError(
                        SpecValidationError.PARSE_SPEC_ERROR.format(error=e)
                    ) from e
        else:
            spec = content

        # Determine spec type and validate
        spec_type = spec.get("openapi") or spec.get("swagger")
        if not spec_type:
            _raise_missing_version()

        try:
            _validate_spec(spec, spec_type)
        except Exception as e:
            logger.warning(f"Specification validation warning: {e}")
            # Continue processing even with validation warnings

        return _parse_endpoints(spec)

    except Exception as e:
        logger.error(f"Error parsing specification: {e}")
        _raise_validation_error(e)
    return ParsedSpec(
        title="", version="", description=None, endpoints=[], components={}
    )


def parse_spec(spec_path: Path | str | dict[str, Any]) -> ParsedSpec:
    """Parse an OpenAPI specification from a file or content.

    Args:
        spec_path: Path to the specification file, or the spec content itself

    Returns:
        ParsedSpec: The parsed specification

    Raises:
        SpecValidationError: If the specification is invalid
    """
    if isinstance(spec_path, str | dict):
        return _parse_spec_from_text(spec_path)

    try:
        # Read the file
        with spec_path.open() as f:
            if spec_path.suffix.lower() in [".yaml", ".yml"]:
                spec = yaml.safe_load(f)
            else:
                spec = json.load(f)

        return _parse_spec_from_text(spec)

    except Exception as e:
        logger.error(f"Error reading specification file: {e}")
        _raise_validation_error(e)
    return ParsedSpec(
        title="", version="", description=None, endpoints=[], components={}
    )


def _validate_responses(operation: dict[str, Any], path: str, method: str) -> None:
    """Validate operation responses.

    Args:
        operation: The operation to validate
        path: The path of the operation
        method: The HTTP method of the operation
    """
    if "responses" in operation:
        for response in operation["responses"].values():
            if not isinstance(response, dict):
                logger.warning(
                    SpecValidationError.INVALID_RESPONSE.format(
                        path=path, method=method
                    )
                )
                break


def _fix_parameters(operation: dict[str, Any], path: str, method: str) -> None:
    """Fix invalid parameters format if needed.

    Args:
        operation: The operation to fix
        path: The path of the operation
        method: The HTTP method of the operation
    """
    if "parameters" in operation and not isinstance(operation["parameters"], list):
        logger.warning(
            f"Invalid parameters format at {path} {method}, converting to list"
        )
        if isinstance(operation["parameters"], dict):
            operation["parameters"] = list(operation["parameters"].values())
        else:
            operation["parameters"] = []


def _parse_endpoints(validated_spec: dict[str, Any]) -> ParsedSpec:
    """Parse endpoints from validated specification.

    Args:
        validated_spec: The validated specification

    Returns:
        ParsedSpec: The parsed specification with endpoints

    Raises:
        SpecValidationError: If the specification is invalid
    """
    if "info" not in validated_spec:
        raise SpecValidationError("'info'")

    endpoints: list[ParsedEndpoint] = []
    for path, path_item in validated_spec.get("paths", {}).items():
        if not isinstance(path_item, dict):
            logger.warning(SpecValidationError.INVALID_PATH_ITEM.format(path=path))
            continue

        for method, operation in path_item.items():
            if not isinstance(operation, dict):
                logger.warning(
                    SpecValidationError.INVALID_OPERATION.format(
                        path=path, method=method
                    )
                )
                continue

            if not _is_valid_method(method):
                continue

            _validate_responses(operation, path, method)
            _fix_parameters(operation, path, method)

            try:
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
