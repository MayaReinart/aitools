"""Tests for the OpenAPI parser."""

from pathlib import Path

import pytest

from src.services.parser import ParsedSpec, SpecValidationError, parse_spec

SAMPLES_PATH = Path(__file__).parent / "samples"


class TestOpenAPIParser:
    """Tests for OpenAPI specification parsing."""

    def test_parse_valid_spec(self) -> None:
        """Test parsing a valid OpenAPI spec."""
        result: ParsedSpec = parse_spec(SAMPLES_PATH / "valid_spec.yaml")
        assert result.title == "Test API"
        assert result.version == "1.0.0"
        assert result.description == "A test API"
        assert len(result.endpoints) == 1

        endpoint = result.endpoints[0]
        assert endpoint.method == "GET"
        assert endpoint.path == "/test"
        assert endpoint.summary == "Test endpoint"
        assert len(endpoint.parameters) == 1

    def test_invalid_yaml(self) -> None:
        """Test parsing invalid YAML."""
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(SAMPLES_PATH / "invalid.yaml")
        assert "Failed to parse specification" in str(exc.value)

    @pytest.mark.parametrize(
        "spec_file,expected_error",
        [
            ("missing_openapi.yaml", "Missing 'openapi' or 'swagger' version field"),
            ("missing_info.yaml", "'info'"),
        ],
    )
    def test_missing_required_fields(self, spec_file: str, expected_error: str) -> None:
        """Test spec missing required OpenAPI fields."""
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(SAMPLES_PATH / spec_file)
        assert expected_error in str(exc.value)

    def test_empty_spec(self) -> None:
        """Test parsing an empty spec."""
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(SAMPLES_PATH / "empty.yaml")
        assert "Failed to parse specification" in str(exc.value)

    def test_invalid_operation_object(self) -> None:
        """Test handling of invalid operation objects."""
        result = parse_spec(SAMPLES_PATH / "invalid_operation.yaml")
        assert len(result.endpoints) == 0

    def test_malformed_responses(self) -> None:
        """Test handling of malformed response objects."""
        result = parse_spec(SAMPLES_PATH / "malformed_responses.yaml")
        assert len(result.endpoints) == 0

    def test_component_references(self) -> None:
        """Test parsing of component references."""
        result = parse_spec(SAMPLES_PATH / "component_refs.yaml")
        assert result.components
        assert "schemas" in result.components
        assert "TestResponse" in result.components["schemas"]

    @pytest.mark.parametrize(
        "method,is_valid",
        [
            ("GET", True),
            ("POST", True),
            ("PUT", True),
            ("DELETE", True),
            ("PATCH", True),
            ("HEAD", True),
            ("OPTIONS", True),
            ("TRACE", False),
            ("CONNECT", False),
            ("INVALID", False),
        ],
    )
    def test_valid_methods(self, method: str, is_valid: bool) -> None:
        """Test validation of HTTP methods."""
        result = parse_spec(SAMPLES_PATH / f"method_{method.lower()}.yaml")
        if is_valid:
            assert len(result.endpoints) == 1
            assert result.endpoints[0].method == method.upper()
        else:
            assert len(result.endpoints) == 0
