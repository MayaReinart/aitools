"""OpenAI integration for API analysis."""

import hashlib
import time
from functools import lru_cache
from pathlib import Path
from typing import cast

from llama_index.core import (  # type: ignore
    Document,
    StorageContext,
    VectorStoreIndex,
    load_index_from_storage,
)
from llama_index.core.base.response.schema import Response  # type: ignore
from loguru import logger
from openai import OpenAI, RateLimitError
from openai.types.chat import (
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)
from pydantic import BaseModel

from src.core.config import settings
from src.services.parser import ParsedSpec
from src.services.prompts import (
    create_batched_endpoint_prompt,
    create_overview_prompt,
)

client = OpenAI(api_key=settings.OPENAI_API_KEY)


class EndpointAnalysis(BaseModel):
    """Analysis of an API endpoint."""

    path: str
    method: str
    analysis: str | None = None  # Deprecated


class SpecAnalysis(BaseModel):
    """Analysis of an OpenAPI specification."""

    overview: str
    endpoints_analysis: str
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
        config: The configuration for the LLM

    Returns:
        SpecAnalysis: The analysis results
    """
    # Generate API overview
    logger.info("Generating API overview")
    overview_prompt = create_overview_prompt(spec)
    overview = _get_completion(overview_prompt, config)  # type: ignore

    # Analyze each endpoint
    logger.info("Analyzing endpoints")
    endpoint_info: list[EndpointAnalysis] = []
    for endpoint in spec.endpoints:
        endpoint_info.append(
            EndpointAnalysis(
                path=endpoint.path,
                method=endpoint.method,
            )
        )

    endpoints_prompt = create_batched_endpoint_prompt(spec.endpoints)
    endpoints_analysis = _get_completion(endpoints_prompt, config)  # type: ignore

    return SpecAnalysis(
        overview=overview,
        endpoints_analysis=endpoints_analysis,
        endpoints=endpoint_info,
    )


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


def get_llm_spec_analysis_with_vector_store(
    embedding_path: Path, query: str
) -> str | None:
    """
    Analyze an OpenAPI specification using LLM and vector store.

    Args:
        spec: The OpenAPI specification text
        query: The query to analyze

    Returns:
        Response: The LLM response
    """

    # Get the spec embedding
    index = load_index_from_storage(
        persist_dir=embedding_path,
        storage_context=StorageContext.from_defaults(),
    )

    # Query the spec
    result = index.as_query_engine().query(query)
    if not isinstance(result, Response):
        raise TypeError(type(result).__name__)
    return result.response


@lru_cache(maxsize=100)
def _get_spec_hash(spec_path: Path) -> str:
    """Get a hash of the spec file content for caching."""
    return hashlib.sha256(spec_path.read_bytes()).hexdigest()


class EmbeddingCreationError(RuntimeError):
    """Raised when embedding creation fails after all retries."""

    pass


def embed_spec(spec: Path) -> VectorStoreIndex:
    """
    Embed an OpenAPI specification using LLM.
    Uses caching to avoid repeated API calls for the same spec.

    Args:
        spec: Path to the specification file

    Returns:
        VectorStoreIndex: The embedding index
    """
    # Check if we already have an embedding for this spec
    storage = StorageContext.from_defaults()
    cache_dir = Path("cache") / _get_spec_hash(spec)

    if cache_dir.exists():
        try:
            index = load_index_from_storage(
                persist_dir=cache_dir,
                storage_context=storage,
            )
            return cast(VectorStoreIndex, index)
        except Exception as e:
            logger.warning(f"Failed to load cached embedding: {e}")

    # Create new embedding if not cached
    docs = [Document(text=spec.read_text())]

    # Add retry logic for rate limits
    max_retries = 3
    base_delay = 1  # Start with 1 second delay

    # TODO: isolate rate limiting logic and add it to other calls
    for attempt in range(max_retries):
        try:
            index = VectorStoreIndex.from_documents(docs)
            break
        except RateLimitError:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2**attempt)  # Exponential backoff
            logger.warning(f"Rate limit hit, retrying in {delay} seconds...")
            time.sleep(delay)
    else:
        raise EmbeddingCreationError()

    # Cache the embedding
    cache_dir.parent.mkdir(exist_ok=True)
    index.storage_context.persist(cache_dir)

    return index
