"""Tests for LLM integration with OpenAPI specs."""

from pathlib import Path
from unittest.mock import ANY, Mock, patch

import pytest
from loguru import logger
from openai import APIError
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.completion_usage import CompletionUsage

from src.services.llm import LLMConfig, SpecAnalysis, get_llm_spec_analysis
from src.services.parser import parse_spec

SAMPLES_PATH = Path(__file__).parent / "samples"


COMPLETION_MIN_LENGTH = 100


def create_mock_chat_completion(content: str) -> ChatCompletion:
    """Create a mock ChatCompletion object."""
    return ChatCompletion(
        id="mock-completion",
        model="gpt-4",
        object="chat.completion",
        created=1234567890,
        choices=[
            {
                "finish_reason": "stop",
                "index": 0,
                "message": ChatCompletionMessage(
                    role="assistant",
                    content=content,
                ),
            }
        ],
        usage=CompletionUsage(
            completion_tokens=100,
            prompt_tokens=100,
            total_tokens=200,
        ),
    )


@pytest.mark.completion_e2e
def test_analyze_petstore_spec() -> None:
    """Test analyzing the Petstore OpenAPI spec."""
    # Parse the sample spec
    spec = parse_spec(SAMPLES_PATH / "petstore.yaml")

    # Analyze the spec using LLM
    analysis = get_llm_spec_analysis(spec)

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


def test_rate_limit_handling() -> None:
    """Test handling of rate limit errors."""
    spec = parse_spec(SAMPLES_PATH / "sample.yaml")

    with patch("src.services.llm.client") as mock_client:
        mock_client.chat.completions.create.side_effect = APIError(
            request=Mock(
                method="POST", url="https://api.openai.com/v1/chat/completions"
            ),
            body=None,
            message="Rate limit exceeded",
        )
        with pytest.raises(APIError) as exc:
            get_llm_spec_analysis(spec)
        assert "Rate limit exceeded" in str(exc.value)


def test_custom_model_config() -> None:
    """Test using custom model configuration."""
    spec = parse_spec(SAMPLES_PATH / "sample.yaml")
    config = LLMConfig(model="gpt-4", temperature=0.7, max_tokens=2000)

    mock_response = create_mock_chat_completion("Test analysis content")

    with patch("src.services.llm.client") as mock_client:
        mock_client.chat.completions.create.return_value = mock_response
        result = get_llm_spec_analysis(spec, config=config)

        # Verify the config was used
        mock_client.chat.completions.create.assert_called_with(
            model="gpt-4", temperature=0.7, max_tokens=2000, messages=ANY
        )

        # Verify the response was processed
        assert isinstance(result, SpecAnalysis)
        assert result.overview == "Test analysis content"


def test_token_limit_handling() -> None:
    """Test handling of large specs that might exceed token limits."""
    # Create a large spec by duplicating endpoints
    large_spec = """
        openapi: 3.0.0
        info:
            title: Large API
            version: 1.0.0
        paths:
    """
    # Add many endpoints to potentially exceed token limits
    for i in range(100):
        large_spec += f"""
            /test{i}:
                get:
                    summary: Test endpoint {i}
                    description: A very long description that takes up tokens...
                    responses:
                        '200':
                            description: Success
                            content:
                                application/json:
                                    schema:
                                        type: object
                                        properties:
                                            message:
                                                type: string
        """

    spec = parse_spec(large_spec)

    responses_count = 100

    # Mock responses for overview and endpoints
    mock_responses = [
        create_mock_chat_completion("API Overview content"),
        *[
            create_mock_chat_completion(f"Endpoint {i} analysis")
            for i in range(responses_count)
        ],
    ]

    with patch("src.services.llm.client") as mock_client:
        mock_client.chat.completions.create.side_effect = mock_responses
        result = get_llm_spec_analysis(spec)

        assert isinstance(result, SpecAnalysis)
        assert result.overview == "API Overview content"
        assert len(result.endpoints) == responses_count
        assert all(
            endpoint.analysis.startswith("Endpoint") for endpoint in result.endpoints
        )


@pytest.mark.parametrize(
    "error_type,error_msg",
    [
        (ValueError, "Invalid request"),
        (TimeoutError, "Request timeout"),
        (ConnectionError, "Network error"),
    ],
)
def test_error_handling(error_type: type[Exception], error_msg: str) -> None:
    """Test handling of various error conditions."""
    spec = parse_spec(SAMPLES_PATH / "sample.yaml")

    with patch("src.services.llm.client") as mock_client:
        mock_client.chat.completions.create.side_effect = error_type(error_msg)
        with pytest.raises(error_type) as exc:
            get_llm_spec_analysis(spec)
        assert error_msg in str(exc.value)
