"""Tests for LLM integration with OpenAPI specs."""

from pathlib import Path

import pytest

from src.services.llm import analyze_spec
from src.services.parser import parse_openapi_spec

SAMPLES_PATH = Path(__file__).parent / "samples"


COMPLETION_MIN_LENGTH = 100


@pytest.mark.completion_e2e
def test_analyze_petstore_spec() -> None:
    """Test analyzing the Petstore OpenAPI spec."""
    # Parse the sample spec
    spec = parse_openapi_spec((SAMPLES_PATH / "petstore.yaml").read_text())

    # Analyze the spec using LLM
    analysis = analyze_spec(spec)

    # Verify the structure of the response
    assert isinstance(analysis, dict)
    assert "overview" in analysis
    assert isinstance(analysis["overview"], str)
    # Should have meaningful content
    assert len(analysis["overview"]) > COMPLETION_MIN_LENGTH

    assert "endpoints" in analysis
    assert isinstance(analysis["endpoints"], list)
    assert len(analysis["endpoints"]) > 0

    # Check the first endpoint
    endpoint = analysis["endpoints"][0]
    assert "path" in endpoint
    assert "method" in endpoint
    assert "analysis" in endpoint
    assert isinstance(endpoint["analysis"], str)
    # Should have meaningful content
    assert len(endpoint["analysis"]) > COMPLETION_MIN_LENGTH
