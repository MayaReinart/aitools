"""Tests for the OpenAPI parser."""

from pathlib import Path

import pytest
from fastapi import HTTPException, status

from src.services.parser import ParsedSpec, parse_openapi_spec

SAMPLES_PATH = Path(__file__).parent / "samples"


class TestOpenAPIParser:
    """Tests for OpenAPI specification parsing."""

    def test_parse_valid_spec(self) -> None:
        """Test parsing a valid OpenAPI spec."""
        with Path.open(SAMPLES_PATH / "sample.yaml", "r") as f:
            spec = f.read()

        result: ParsedSpec = parse_openapi_spec(spec)
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
        with pytest.raises(HTTPException) as exc:
            parse_openapi_spec("invalid: yaml: :")
        assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid YAML/JSON format" in exc.value.detail

    @pytest.mark.parametrize(
        "spec,expected_error",
        [
            ("info:", "Missing 'openapi' version field"),
            ("openapi: 3.0.0", "Missing 'info' section"),
            (
                """
                openapi: 3.0.0
                info:
                    title: Test
                """,
                "Missing 'paths' section",
            ),
        ],
        ids=["missing_openapi", "missing_info", "missing_paths"],
    )
    def test_missing_required_fields(self, spec: str, expected_error: str) -> None:
        """Test spec missing required OpenAPI fields."""
        with pytest.raises(HTTPException) as exc:
            parse_openapi_spec(spec)
        assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
        assert expected_error in exc.value.detail

    def test_empty_spec(self) -> None:
        """Test parsing an empty spec."""
        with pytest.raises(HTTPException) as exc:
            parse_openapi_spec("")
        assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Spec must be a YAML/JSON object" in exc.value.detail

    def test_invalid_operation_object(self) -> None:
        """Test handling of invalid operation objects."""
        spec = """
            openapi: 3.0.0
            info:
                title: Test API
                version: 1.0.0
            paths:
                /test:
                    get: not_an_object
        """
        result = parse_openapi_spec(spec)
        assert len(result.endpoints) == 0

    def test_malformed_responses(self) -> None:
        """Test handling of malformed response objects."""
        spec = """
            openapi: 3.0.0
            info:
                title: Test API
                version: 1.0.0
            paths:
                /test:
                    get:
                        responses:
                            '200': not_an_object
        """
        result = parse_openapi_spec(spec)
        assert len(result.endpoints) == 0

    def test_component_references(self) -> None:
        """Test parsing of component references."""
        spec = """
            openapi: 3.0.0
            info:
                title: Test API
                version: 1.0.0
            paths:
                /test:
                    get:
                        responses:
                            '200':
                                $ref: '#/components/schemas/TestResponse'
            components:
                schemas:
                    TestResponse:
                        type: object
                        properties:
                            message:
                                type: string
        """
        result = parse_openapi_spec(spec)
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
        spec = f"""
            openapi: 3.0.0
            info:
                title: Test API
                version: 1.0.0
            paths:
                /test:
                    {method.lower()}:
                        responses:
                            '200':
                                description: OK
        """
        result = parse_openapi_spec(spec)
        if is_valid:
            assert len(result.endpoints) == 1
            assert result.endpoints[0].method == method.upper()
        else:
            assert len(result.endpoints) == 0
