"""Job data storage utilities."""

from enum import Enum
from pathlib import Path

JOB_DATA_ROOT = Path("job_data")


class JobArtifact(str, Enum):
    """Types of artifacts that can be stored for a job."""

    SPEC = "spec"
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
        return spec_path

    def save_summary(self, summary: dict) -> Path:
        """Save the generated summary."""
        summary_path = self.job_dir / "summary.json"
        summary_path.write_text(str(summary))
        return summary_path

    def save_export(self, content: str | bytes, format_: ExportFormat) -> Path:
        """Save an exported summary file."""
        export_path = self.job_dir / f"summary.{format_}"
        if isinstance(content, str):
            export_path.write_text(content)
        else:
            export_path.write_bytes(content)
        return export_path

    def get_spec_path(self) -> Path | None:
        """Get the path to the spec file if it exists."""
        for ext in ["yaml", "json"]:
            path = self.job_dir / f"spec.{ext}"
            if path.exists():
                return path
        return None

    def get_summary_path(self) -> Path | None:
        """Get the path to the summary file if it exists."""
        path = self.job_dir / "summary.json"
        return path if path.exists() else None

    def get_export_path(self, format_: ExportFormat) -> Path | None:
        """Get the path to an export file if it exists."""
        path = self.job_dir / f"summary.{format_}"
        return path if path.exists() else None

    def ensure_export_exists(self, format_: ExportFormat) -> Path:
        """Ensure an export file exists, creating a placeholder if needed."""
        path = self.job_dir / f"summary.{format_}"
        if not path.exists():
            if format_ == "md":
                path.write_text("# API Summary\n\nTo be implemented")
            elif format_ == "html":
                path.write_text("<h1>API Summary</h1>\n<p>To be implemented</p>")
            elif format_ == "docx":
                path.write_bytes(b"")  # Empty DOCX for now
        return path
