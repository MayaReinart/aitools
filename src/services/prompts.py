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
    # Format parameters
    params = "\n".join(
        f"- {p.name} ({p.location}): "
        f"{'Required' if p.required else 'Optional'}, "
        f"Type: {p.api_schema.type if p.api_schema else 'unspecified'}"
        + (f"\n  Description: {p.description}" if p.description else "")
        for p in endpoint.parameters
    )

    # Format request body
    request_body = "No request body"
    if endpoint.request_body:
        rb = endpoint.request_body
        request_body = (
            f"Content-Type: {rb.content_type}\n"
            f"Required: {rb.required}\n"
            + (f"Description: {rb.description}\n" if rb.description else "")
            + (
                f"Schema Type: {rb.api_schema.type}"
                if rb.api_schema
                else "No schema provided"
            )
        )

    # Format responses
    responses = "\n".join(
        f"- {code}: "
        + (f"{resp.description}" if resp.description else "No description")
        + (f"\n  Content-Type: {resp.content_type}" if resp.content_type else "")
        + (
            f"\n  Schema Type: {resp.api_schema.type}"
            if resp.api_schema
            else "No schema provided"
        )
        for code, resp in sorted(endpoint.responses.items())
    )

    return f"""Analyze this API endpoint and provide a clear technical description.

Endpoint: {endpoint.method} {endpoint.path}
Summary: {endpoint.summary or "No summary provided"}
Description: {endpoint.description or "No description provided"}

Parameters:
{params or "No parameters"}

Request Body:
{request_body}

Responses:
{responses or "No documented responses"}

Provide:
1. A clear explanation of what this endpoint does
2. Input requirements:
   - URL parameters and their usage
   - Request body structure (if applicable)
3. Expected responses for different status codes
4. Error conditions and how to handle them
5. Any important implementation notes or best practices

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
