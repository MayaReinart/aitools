"""Job data storage utilities."""

from enum import Enum
from pathlib import Path

from loguru import logger

JOB_DATA_ROOT = Path("job_data")


class JobArtifact(str, Enum):
    """Types of artifacts that can be stored for a job."""

    SPEC = "spec"
    PARSED_SPEC = "parsed_spec"
    SUMMARY = "summary"
    EXPORT = "export"


class SpecFormat(str, Enum):
    """Formats for uploaded specs."""

    YAML = "yaml"
    JSON = "json"


class ExportFormat(str, Enum):
    """Formats for exported summaries."""

    MARKDOWN = "md"
    HTML = "html"
    DOCX = "docx"


class JobStorage:
    """Handles storage and retrieval of job-related data."""

    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        self.job_dir = JOB_DATA_ROOT / job_id
        self.job_dir.mkdir(parents=True, exist_ok=True)

    def save_spec(self, content: str, format_: SpecFormat) -> Path:
        """Save the uploaded spec file."""
        spec_path = self.job_dir / f"spec.{format_}"
        spec_path.write_text(content)
        logger.info(f"Saved {self.job_id} spec to {spec_path}")
        return spec_path

    def save_summary(self, summary: dict) -> Path:
        """Save the generated summary."""
        summary_path = self.job_dir / "summary.json"
        summary_path.write_text(str(summary))
        logger.info(f"Saved {self.job_id} summary to {summary_path}")
        return summary_path

    def save_export(self, content: str | bytes, format_: ExportFormat) -> Path:
        """Save an exported summary file."""
        export_path = self.job_dir / f"summary.{format_}"
        if isinstance(content, str):
            export_path.write_text(content)
        else:
            export_path.write_bytes(content)
        logger.info(f"Saved {self.job_id} export to {export_path}")
        return export_path

    def save_parsed_spec(self, parsed_spec: dict) -> Path:
        """Save the parsed OpenAPI spec."""
        parsed_spec_path = self.job_dir / "parsed_spec.json"
        parsed_spec_path.write_text(str(parsed_spec))
        logger.info(f"Saved {self.job_id} parsed spec to {parsed_spec_path}")
        return parsed_spec_path

    def get_spec_path(self) -> Path | None:
        """Get the path to the spec file if it exists."""
        for ext in ["yaml", "json"]:
            path = self.job_dir / f"spec.{ext}"
            if ext_path := _get_and_log_path(path, self.job_id, JobArtifact.SPEC):
                return ext_path
        return None

    def get_summary_path(self) -> Path | None:
        """Get the path to the summary file if it exists."""
        path = self.job_dir / "summary.json"
        return _get_and_log_path(path, self.job_id, JobArtifact.SUMMARY)

    def get_export_path(self, format_: ExportFormat) -> Path | None:
        """Get the path to an export file if it exists."""
        path = self.job_dir / f"summary.{format_}"
        return _get_and_log_path(path, self.job_id, JobArtifact.EXPORT)

    def get_parsed_spec_path(self) -> Path | None:
        """Get the path to the parsed spec file if it exists."""
        path = self.job_dir / "parsed_spec.json"
        return _get_and_log_path(path, self.job_id, JobArtifact.PARSED_SPEC)

    def ensure_export_exists(self, format_: ExportFormat) -> Path:
        """Ensure an export file exists, creating a placeholder if needed."""
        path = self.job_dir / f"summary.{format_}"
        logger.info(f"Checking if {self.job_id} {format_} export exists at {path}")

        if path.exists():
            return path

        logger.info(f"Creating {self.job_id} {format_} export at {path}")

        path.touch()
        if format_ == ExportFormat.MARKDOWN:
            path.write_text("# API Summary\n\nTo be implemented")
        elif format_ == ExportFormat.HTML:
            path.write_text("<h1>API Summary</h1>\n<p>To be implemented</p>")
        elif format_ == ExportFormat.DOCX:
            path.write_bytes(b"")  # Empty DOCX for now

        return path


def _get_and_log_path(path: Path, job_id: str, artifact: JobArtifact) -> Path | None:
    """Get a path and log it.

    Args:
        path: The path to get.
        job_id: The job ID.
        artifact: The artifact type: SPEC, SUMMARY, or EXPORT.
    """
    if path.exists():
        logger.info(f"Found {job_id} {artifact} at {path}")
        return path

    logger.warning(f"No {job_id} {artifact} found at {path}")
    return None
