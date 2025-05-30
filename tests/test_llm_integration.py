"""Tests for LLM integration with OpenAPI specs."""

from pathlib import Path

import pytest
from loguru import logger

from src.services.llm import SpecAnalysis, analyze_spec
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
    assert isinstance(analysis, SpecAnalysis)
    assert analysis.overview
    logger.debug(analysis.overview)
    # Should have meaningful content
    assert len(analysis.overview) > COMPLETION_MIN_LENGTH

    assert analysis.endpoints
    assert len(analysis.endpoints) > 0

    # Check the first endpoint
    endpoint = analysis.endpoints[0]
    assert endpoint.path
    assert endpoint.method
    assert endpoint.analysis
    # Should have meaningful content
    assert len(endpoint.analysis) > COMPLETION_MIN_LENGTH
