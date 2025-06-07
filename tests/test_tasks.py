"""Tests for background tasks."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.services.llm import SpecAnalysis
from src.services.parser import ParsedSpec
from src.tasks.standalone import analyze_api_task


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
        mock_storage: Mock,
        sample_spec: bytes,
        test_job_id: str,
        parsed_spec: ParsedSpec,
        mock_spec_analysis: SpecAnalysis,
    ) -> None:
        """Test task behavior when no cached spec exists."""
        mock_storage.get_parsed_spec_path.return_value = None

        with (
            patch("src.tasks.standalone.parse_openapi_spec") as mock_parse,
            patch("src.tasks.standalone.get_llm_spec_analysis") as mock_analyze,
        ):
            mock_parse.return_value = parsed_spec
            mock_analyze.return_value = mock_spec_analysis

            result = analyze_api_task(sample_spec.decode(), test_job_id, mock_storage)

            # Verify parsing was called
            mock_parse.assert_called_once_with(sample_spec.decode())
            # Verify spec was cached
            mock_storage.save_parsed_spec.assert_called_once_with(
                parsed_spec.model_dump()
            )

            assert result["spec_info"]["title"] == "Test API"
            assert result["summary"] == mock_spec_analysis

    def test_with_cache(
        self,
        mock_storage: Mock,
        sample_spec: bytes,
        test_job_id: str,
        cached_spec: dict,
        mock_spec_analysis: SpecAnalysis,
        tmp_path: Path,
    ) -> None:
        """Test task behavior when cached spec exists."""
        # Set up mock for cached spec
        mock_storage.get_parsed_spec_path.return_value = tmp_path / "parsed_spec.json"
        with (tmp_path / "parsed_spec.json").open("w") as f:
            json.dump(cached_spec, f)

        with (
            patch("src.tasks.standalone.parse_openapi_spec") as mock_parse,
            patch("src.tasks.standalone.get_llm_spec_analysis") as mock_analyze,
        ):
            mock_analyze.return_value = mock_spec_analysis

            result = analyze_api_task(sample_spec.decode(), test_job_id, mock_storage)

            # Verify parsing was not called
            mock_parse.assert_not_called()
            # Verify cached spec was used
            assert result["spec_info"]["title"] == "Cached API"
            assert result["summary"] == mock_spec_analysis

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

            analyze_api_task(sample_spec.decode(), test_job_id)

            # Verify storage was created with job_id
            mock_storage_class.assert_called_once_with(test_job_id)
            # Verify parsing was called
            mock_parse.assert_called_once_with(sample_spec.decode())
            # Verify spec was cached
            mock_storage.save_parsed_spec.assert_called_once_with(
                parsed_spec.model_dump()
            )
