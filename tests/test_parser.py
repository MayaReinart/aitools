"""Tests for the OpenAPI parser."""

from pathlib import Path

import pytest
from fastapi import HTTPException, status

from src.services.parser import parse_openapi_spec

SAMPLES_PATH = Path(__file__).parent / "samples"


class TestOpenAPIParser:
    """Tests for OpenAPI specification parsing."""

    def test_parse_valid_spec(self) -> None:
        """Test parsing a valid OpenAPI spec."""
        with Path.open(SAMPLES_PATH / "sample.yaml", "r") as f:
            spec = f.read()

        result = parse_openapi_spec(spec)
        assert result["title"] == "Test API"
        assert result["version"] == "1.0.0"
        assert result["description"] == "A test API"
        assert len(result["endpoints"]) == 1

        endpoint = result["endpoints"][0]
        assert endpoint["method"] == "GET"
        assert endpoint["path"] == "/test"
        assert endpoint["summary"] == "Test endpoint"
        assert len(endpoint["parameters"]) == 1

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
