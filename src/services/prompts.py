"""Prompt templates for LLM-based API analysis."""

from typing import Any

from src.services.parser import ParsedEndpoint, ParsedSpec


def create_overview_prompt(spec: ParsedSpec) -> str:
    """Create a prompt for generating an API overview.

    Args:
        spec: The parsed OpenAPI specification

    Returns:
        str: A prompt for the LLM to generate an overview
    """
    return f"""You are an expert API documentation writer.
    Analyze this API specification and provide a clear, concise overview.

API Details:
- Title: {spec.title}
- Version: {spec.version}
- Description: {spec.description or "No description provided"}

Total Endpoints: {len(spec.endpoints)}

Write a professional summary that covers:
1. The main purpose and functionality of this API
2. Key features and capabilities
3. Notable patterns in the endpoint design
4. Any important technical requirements or considerations

Keep the summary clear, technical, and focused on what developers need to know."""


def create_endpoint_prompt(endpoint: ParsedEndpoint) -> str:
    """Create a prompt for analyzing a single endpoint.

    Args:
        endpoint: The parsed endpoint data

    Returns:
        str: A prompt for the LLM to analyze the endpoint
    """
    params = "\n".join(
        f"- {p.get('name', 'unnamed')}: {p.get('description', 'No description')} "
        f"({'Required' if p.get('required') else 'Optional'})"
        for p in endpoint.parameters
    )

    responses = "\n".join(
        f"- {code}: {details.get('description', 'No description')}"
        for code, details in endpoint.responses.items()
    )

    return f"""Analyze this API endpoint and provide a clear technical description.

Endpoint: {endpoint.method} {endpoint.path}
Summary: {endpoint.summary or "No summary provided"}
Description: {endpoint.description or "No description provided"}

Parameters:
{params or "No parameters"}

Request Body: {"Yes" if endpoint.request_body else "No"}

Responses:
{responses or "No documented responses"}

Provide:
1. A clear explanation of what this endpoint does
2. Required parameters and their purpose
3. Expected responses and what they mean
4. Any important notes for implementation

Keep the description technical and focused on usage."""


def format_spec_for_analysis(spec: ParsedSpec) -> dict[str, Any]:
    """Format the parsed spec into a structure for LLM analysis.

    Args:
        spec: The parsed OpenAPI specification

    Returns:
        dict: A structured format for LLM consumption
    """
    return {
        "overview": create_overview_prompt(spec),
        "endpoints": [
            {
                "path": endpoint.path,
                "method": endpoint.method,
                "analysis": create_endpoint_prompt(endpoint),
            }
            for endpoint in spec.endpoints
        ],
    }
