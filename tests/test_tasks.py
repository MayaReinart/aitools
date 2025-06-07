"""Tests for background tasks."""

import json
from unittest.mock import Mock, patch

import pytest
from redis import Redis

from src.core.models import TaskState
from src.services.llm import SpecAnalysis
from src.services.parser import ParsedSpec
from src.tasks.standalone import analyze_api_task, handle_success


@pytest.fixture
def parsed_spec() -> ParsedSpec:
    """Create a parsed spec for testing."""
    return ParsedSpec(
        title="Test API",
        version="1.0.0",
        description=None,
        endpoints=[],
        components={},
    )


@pytest.fixture
def cached_spec() -> dict:
    """Create a cached spec for testing."""
    return {
        "title": "Cached API",
        "version": "1.0.0",
        "description": None,
        "endpoints": [],
        "components": {},
    }


class TestAnalyzeAPITask:
    """Tests for analyze_api_task."""

    def test_no_cache(
        self,
        sample_spec: bytes,
        test_job_id: str,
        parsed_spec: ParsedSpec,
        mock_spec_analysis: SpecAnalysis,
    ) -> None:
        """Test task behavior with no cached results."""
        with (
            patch("src.tasks.standalone.parse_openapi_spec") as mock_parse,
            patch("src.tasks.standalone.get_llm_spec_analysis") as mock_analyze,
        ):
            mock_parse.return_value = parsed_spec
            mock_analyze.return_value = mock_spec_analysis

            result = analyze_api_task(sample_spec.decode(), test_job_id)

            # Verify parsing was called
            mock_parse.assert_called_once_with(sample_spec.decode())
            # Verify analysis was called
            mock_analyze.assert_called_once_with(parsed_spec)
            # Verify result contains the analysis
            assert isinstance(result["summary"], SpecAnalysis)
            assert result["summary"] == mock_spec_analysis
            assert result["job_id"] == test_job_id

    def test_with_cache(
        self,
        sample_spec: bytes,
        test_job_id: str,
        parsed_spec: ParsedSpec,
        mock_spec_analysis: SpecAnalysis,
        mock_storage: Mock,
    ) -> None:
        """Test task behavior with cached results."""
        with (
            patch("src.tasks.standalone.parse_openapi_spec") as mock_parse,
            patch("src.tasks.standalone.get_llm_spec_analysis") as mock_analyze,
        ):
            mock_parse.return_value = parsed_spec
            mock_analyze.return_value = mock_spec_analysis

            result = analyze_api_task(
                sample_spec.decode(), test_job_id, storage=mock_storage
            )

            # Verify parsing was called
            mock_parse.assert_called_once_with(sample_spec.decode())
            # Verify analysis was called
            mock_analyze.assert_called_once_with(parsed_spec)
            # Verify result contains the analysis
            assert isinstance(result["summary"], SpecAnalysis)
            assert result["summary"] == mock_spec_analysis
            assert result["job_id"] == test_job_id

    def test_no_storage_provided(
        self,
        sample_spec: bytes,
        test_job_id: str,
        parsed_spec: ParsedSpec,
        mock_spec_analysis: SpecAnalysis,
    ) -> None:
        """Test task behavior when no storage is provided."""
        with (
            patch("src.tasks.standalone.JobStorage") as mock_storage_class,
            patch("src.tasks.standalone.parse_openapi_spec") as mock_parse,
            patch("src.tasks.standalone.get_llm_spec_analysis") as mock_analyze,
        ):
            mock_storage = Mock()
            mock_storage_class.return_value = mock_storage
            mock_storage.get_parsed_spec_path.return_value = None
            mock_parse.return_value = parsed_spec
            mock_analyze.return_value = mock_spec_analysis

            result = analyze_api_task(sample_spec.decode(), test_job_id)

            # Verify storage was created with job_id
            mock_storage_class.assert_called_once_with(test_job_id)
            # Verify parsing was called
            mock_parse.assert_called_once_with(sample_spec.decode())
            # Verify spec was cached
            mock_storage.save_parsed_spec.assert_called_once_with(
                parsed_spec.model_dump()
            )
            # Verify result contains the analysis
            assert isinstance(result["summary"], SpecAnalysis)
            assert result["summary"] == mock_spec_analysis
            assert result["job_id"] == test_job_id

    def test_handle_success_integration(
        self,
        test_job_id: str,
    ) -> None:
        """Integration test for success handler with real Redis."""
        test_data = {"test": "data"}
        result = {"job_id": test_job_id, **test_data}
        handle_success(result=result)

        # Verify state was saved in Redis
        redis = Redis.from_url("redis://localhost:6379/0")
        key = f"task_state:{test_job_id}"
        saved_state = redis.get(key)
        assert saved_state is not None
        state_data = json.loads(saved_state)
        assert state_data["state"] == TaskState.SUCCESS.value
        assert state_data["job_id"] == test_job_id
        assert (
            state_data["result"] == result
        )  # Compare with full result including job_id
