"""Prompt templates for LLM analysis."""

from src.services.models import ParsedEndpoint, ParsedSpec


def create_overview_prompt(spec: ParsedSpec) -> str:
    """Create a prompt for API overview analysis.

    Args:
        spec: The parsed OpenAPI specification

    Returns:
        Formatted prompt for overview analysis
    """
    return f"""Analyze this API specification and provide a comprehensive overview.

API: {spec.title} (v{spec.version})
Description: {spec.description or 'No description provided'}

Endpoints:
{_format_endpoints(spec.endpoints)}

Provide:
1. A high-level overview of the API's purpose and functionality
2. Key features and capabilities
3. Common use cases
4. Notable patterns or conventions
5. Potential integration considerations

Keep the description technical and focused on usage."""


def create_endpoint_prompt(endpoint: ParsedEndpoint) -> str:
    """Create a prompt for endpoint analysis.

    Args:
        endpoint: The parsed endpoint information

    Returns:
        Formatted prompt for endpoint analysis
    """
    return f"""Analyze this API endpoint and provide detailed documentation.

{_format_endpoint(endpoint)}

Provide:
1. Purpose and functionality
2. Request/response patterns
3. Error handling
4. Security considerations
5. Integration examples

Keep the description technical and focused on usage."""


def _format_endpoints(endpoints: list[ParsedEndpoint]) -> str:
    """Format a list of endpoints for prompt inclusion.

    Args:
        endpoints: List of parsed endpoints

    Returns:
        Formatted string of endpoints
    """
    return "\n".join(_format_endpoint(endpoint) for endpoint in endpoints)


def _format_endpoint(endpoint: ParsedEndpoint) -> str:
    """Format a single endpoint for prompt inclusion.

    Args:
        endpoint: The parsed endpoint information

    Returns:
        Formatted string of endpoint details
    """
    lines = [
        f"\n{endpoint.method} {endpoint.path}",
        f"Summary: {endpoint.summary or 'No summary provided'}",
    ]

    if endpoint.description:
        lines.append(f"Description: {endpoint.description}")

    if endpoint.parameters:
        lines.append("\nParameters:")
        for param in endpoint.parameters:
            lines.append(
                f"- {param.name} ({param.location})"
                f"{' (required)' if param.required else ''}"
            )
            if param.description:
                lines.append(f"  {param.description}")

    if endpoint.request_body:
        lines.append("\nRequest Body:")
        lines.append(f"Content Type: {endpoint.request_body.content_type}")
        if endpoint.request_body.description:
            lines.append(f"Description: {endpoint.request_body.description}")

    if endpoint.responses:
        lines.append("\nResponses:")
        for status, response in endpoint.responses.items():
            lines.append(f"- {status}: {response.description or 'No description'}")
            if response.content_type:
                lines.append(f"  Content Type: {response.content_type}")

    return "\n".join(lines)
