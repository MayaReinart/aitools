"""OpenAI integration for API analysis."""

from llama_index import Document, VectorStoreIndex  # type: ignore
from loguru import logger
from openai import OpenAI
from openai.types.chat import (
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)
from pydantic import BaseModel

from src.core.config import settings
from src.services.parser import ParsedSpec
from src.services.prompts import format_spec_for_analysis

client = OpenAI(api_key=settings.OPENAI_API_KEY)


class EndpointAnalysis(BaseModel):
    """Analysis of an API endpoint."""

    path: str
    method: str
    analysis: str


class SpecAnalysis(BaseModel):
    """Analysis of an OpenAPI specification."""

    overview: str
    endpoints: list[EndpointAnalysis]


class LLMConfig(BaseModel):
    """Configuration for the LLM."""

    model: str = "gpt-4o-mini"
    temperature: float = 0.3
    max_tokens: int = 2000


def get_llm_spec_analysis(
    spec: ParsedSpec, config: LLMConfig | None = None
) -> SpecAnalysis:
    """
    Analyze an OpenAPI specification using LLM.

    Args:
        spec: The parsed OpenAPI specification

    Returns:
        dict: Analysis results including overview and endpoint details
    """
    spec_analysis = format_spec_for_analysis(spec)

    # Generate API overview
    logger.info("Generating API overview")
    overview = _get_completion(spec_analysis["overview"], config)

    # Analyze each endpoint
    logger.info("Analyzing endpoints")
    endpoint_analyses: list[EndpointAnalysis] = []
    for endpoint in spec_analysis["endpoints"]:
        logger.info(f"Analyzing endpoint: {endpoint['method']} {endpoint['path']}")
        endpoint_analysis = _get_completion(endpoint["analysis"], config)
        endpoint_analyses.append(
            EndpointAnalysis(
                path=endpoint["path"],
                method=endpoint["method"],
                analysis=endpoint_analysis,
            )
        )

    return SpecAnalysis(overview=overview, endpoints=endpoint_analyses)


def _get_completion(prompt: str, config: LLMConfig | None = None) -> str:
    """
    Get a completion from OpenAI.

    Args:
        prompt: The prompt to send
        model: The model to use

    Returns:
        str: The generated text
    """
    system_prompt = (
        "You are an expert in API documentation and technical writing. "
        "Provide clear, concise, and technically accurate responses."
    )

    messages: list[
        ChatCompletionSystemMessageParam | ChatCompletionUserMessageParam
    ] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    if config is None:
        config = LLMConfig()

    try:
        response = client.chat.completions.create(
            model=config.model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
        content = response.choices[0].message.content
        return content.strip() if content else ""
    except Exception as e:
        logger.error(f"Error getting completion: {e}")
        raise


def get_llm_spec_analysis_with_vector_store(spec: str, query: str) -> str:
    """
    Analyze an OpenAPI specification using LLM and vector store.
    """
    docs = [Document(text=spec)]

    index = VectorStoreIndex.from_documents(docs)
    engine = index.as_query_engine()

    return engine.query(query)
