"""Tests for background tasks."""

import json
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import UUID

import pytest

from src.core.storage import JobStorage
from src.services.parser import ParsedSpec
from src.tasks.tasks import summarize_doc_task


@pytest.fixture
def job_id() -> str:
    """Create a test job ID."""
    return str(UUID("12345678-1234-5678-1234-567812345678"))


@pytest.fixture
def sample_spec() -> str:
    """Create a sample OpenAPI spec."""
    return """
    openapi: 3.0.0
    info:
      title: Test API
      version: 1.0.0
    paths: {}
    """


@pytest.fixture
def mock_storage(job_id: str) -> Mock:
    """Create a mock storage instance."""
    storage = Mock(spec=JobStorage)
    storage.job_id = job_id
    return storage


class TestSummarizeDocTask:
    """Tests for summarize_doc_task."""

    def test_no_cache(self, mock_storage: Mock, sample_spec: str, job_id: str) -> None:
        """Test task behavior when no cached spec exists."""
        mock_storage.get_parsed_spec_path.return_value = None

        parsed_spec = ParsedSpec(
            title="Test API",
            version="1.0.0",
            description=None,
            endpoints=[],
            components={},
        )

        with (
            patch("src.tasks.tasks.parse_openapi_spec") as mock_parse,
            patch("src.tasks.tasks.get_llm_spec_analysis") as mock_analyze,
        ):
            mock_parse.return_value = parsed_spec
            mock_analyze.return_value = {"summary": "Test summary"}

            result = summarize_doc_task(sample_spec, job_id, mock_storage)

            # Verify parsing was called
            mock_parse.assert_called_once_with(sample_spec)
            # Verify spec was cached
            mock_storage.save_parsed_spec.assert_called_once_with(
                parsed_spec.model_dump()
            )

            assert result["spec_info"]["title"] == "Test API"
            assert result["summary"] == {"summary": "Test summary"}

    def test_with_cache(
        self, mock_storage: Mock, sample_spec: str, job_id: str, tmp_path: Path
    ) -> None:
        """Test task behavior when cached spec exists."""
        cached_spec = {
            "title": "Cached API",
            "version": "1.0.0",
            "description": None,
            "endpoints": [],
            "components": {},
        }

        # Set up mock for cached spec
        mock_storage.get_parsed_spec_path.return_value = tmp_path / "parsed_spec.json"
        with (tmp_path / "parsed_spec.json").open("w") as f:
            json.dump(cached_spec, f)

        with (
            patch("src.tasks.tasks.parse_openapi_spec") as mock_parse,
            patch("src.tasks.tasks.get_llm_spec_analysis") as mock_analyze,
        ):
            mock_analyze.return_value = {"summary": "Test summary"}

            result = summarize_doc_task(sample_spec, job_id, mock_storage)

            # Verify parsing was not called
            mock_parse.assert_not_called()
            # Verify cached spec was used
            assert result["spec_info"]["title"] == "Cached API"
            assert result["summary"] == {"summary": "Test summary"}

    def test_no_storage_provided(self, sample_spec: str, job_id: str) -> None:
        """Test task behavior when no storage is provided."""
        parsed_spec = ParsedSpec(
            title="Test API",
            version="1.0.0",
            description=None,
            endpoints=[],
            components={},
        )

        with (
            patch("src.tasks.tasks.JobStorage") as mock_storage_class,
            patch("src.tasks.tasks.parse_openapi_spec") as mock_parse,
            patch("src.tasks.tasks.get_llm_spec_analysis") as mock_analyze,
        ):
            mock_storage = Mock()
            mock_storage_class.return_value = mock_storage
            mock_storage.get_parsed_spec_path.return_value = None
            mock_parse.return_value = parsed_spec
            mock_analyze.return_value = {"summary": "Test summary"}

            summarize_doc_task(sample_spec, job_id)

            # Verify storage was created with job_id
            mock_storage_class.assert_called_once_with(job_id)
            # Verify parsing was called
            mock_parse.assert_called_once_with(sample_spec)
            # Verify spec was cached
            mock_storage.save_parsed_spec.assert_called_once_with(
                parsed_spec.model_dump()
            )
