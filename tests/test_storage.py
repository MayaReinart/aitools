"""Tests for storage functionality."""

from pathlib import Path

import pytest

from src.core.storage import JobStorage


@pytest.fixture
def job_storage(tmp_path: Path) -> JobStorage:
    """Create a temporary JobStorage instance."""
    job_id = "test-job"
    storage = JobStorage(job_id)
    # Override the job data root for testing
    storage.job_dir = tmp_path / job_id
    storage.job_dir.mkdir(parents=True, exist_ok=True)
    return storage


class TestJobStorage:
    """Tests for JobStorage class."""

    def test_save_parsed_spec(self, job_storage: JobStorage) -> None:
        """Test saving a parsed spec."""
        parsed_spec = {"title": "Test API", "version": "1.0.0", "endpoints": []}

        path = job_storage.save_parsed_spec(parsed_spec)
        assert path.exists()
        assert path.name == "parsed_spec.json"

        # Verify content
        saved_content = path.read_text()
        assert str(parsed_spec) in saved_content

    def test_get_parsed_spec_path_exists(self, job_storage: JobStorage) -> None:
        """Test getting path to existing parsed spec."""
        # Create a parsed spec file
        parsed_spec = {"title": "Test API"}
        job_storage.save_parsed_spec(parsed_spec)

        path = job_storage.get_parsed_spec_path()
        assert path is not None
        assert path.exists()
        assert path.name == "parsed_spec.json"

    def test_get_parsed_spec_path_not_exists(self, job_storage: JobStorage) -> None:
        """Test getting path to non-existent parsed spec."""
        path = job_storage.get_parsed_spec_path()
        assert path is None
