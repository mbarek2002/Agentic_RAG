import json
import logging
import re
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from langchain_ollama import ChatOllama
from src.config import Settings
from src.services.ollama.prompts import RAGPromptBuilder

logger = logging.getLogger(__name__)

_CITATION_PATTERN = re.compile(r"\[arXiv:([^\]]+)\]")


class OllamaClient:
    """Client for Ollama: health checks, raw generation, and RAG answer generation."""

    def __init__(self, settings: Settings):
        self.base_url = settings.ollama_host
        self.timeout = settings.ollama_timeout
        self.default_model = settings.ollama_default_model
        self.prompt_builder = RAGPromptBuilder()

    def get_langchain_model(self, model: Optional[str] = None, temperature: float = 0.0) -> ChatOllama:
        """Get a LangChain-compatible chat model backed by this Ollama server.

        Used by the LangGraph agentic RAG nodes, which need a model that
        supports with_structured_output()/bind_tools() rather than this
        client's own generate()/generate_stream() methods.

        Args:
            model: Model name (uses settings.ollama_default_model if None)
            temperature: Sampling temperature

        Returns:
            A ChatOllama instance pointed at this client's Ollama server
        """
        return ChatOllama(model=model or self.default_model, base_url=self.base_url, temperature=temperature)

    async def health_check(self) -> Dict[str, str]:
        """Check if Ollama service is available."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    return {"status": "healthy", "message": "Ollama service is running"}
                return {"status": "unhealthy", "message": f"HTTP {response.status_code}"}
        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return {"status": "unhealthy", "message": str(e)}

    async def list_models(self) -> List[str]:
        """List model names currently available on the Ollama server."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                data = response.json()
                return [model.get("name", "") for model in data.get("models", [])]
        except Exception as e:
            logger.error(f"Failed to list Ollama models: {e}")
            return []

    async def generate(self, prompt: str, model: Optional[str] = None, **options: Any) -> str:
        """Generate a single, non-streaming completion.

        Args:
            prompt: Full prompt text to send to the model
            model: Model name (uses settings.ollama_default_model if None)
            options: Extra Ollama generation options (temperature, top_p, ...)

        Returns:
            The generated text
        """
        payload: Dict[str, Any] = {
            "model": model or self.default_model,
            "prompt": prompt,
            "stream": False,
        }
        if options:
            payload["options"] = options

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status()
            return response.json().get("response", "")

    async def _generate_stream_raw(
        self, prompt: str, model: Optional[str] = None, **options: Any
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream a completion, yielding raw Ollama JSON-line dicts as they arrive.

        Each dict carries at least "response" (the text fragment) and "done"
        (bool), mirroring Ollama's own /api/generate streaming payload shape.
        """
        payload: Dict[str, Any] = {
            "model": model or self.default_model,
            "prompt": prompt,
            "stream": True,
        }
        if options:
            payload["options"] = options

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", f"{self.base_url}/api/generate", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    yield data
                    if data.get("done"):
                        break

    async def generate_stream(self, prompt: str, model: Optional[str] = None, **options: Any) -> AsyncGenerator[str, None]:
        """Stream a completion, yielding text fragments as they arrive.

        Args:
            prompt: Full prompt text to send to the model
            model: Model name (uses settings.ollama_default_model if None)
            options: Extra Ollama generation options (temperature, top_p, ...)

        Yields:
            Text fragments as they are generated by Ollama
        """
        async for data in self._generate_stream_raw(prompt, model=model, **options):
            fragment = data.get("response", "")
            if fragment:
                yield fragment

    async def generate_rag_answer(self, query: str, chunks: List[Dict[str, Any]], model: Optional[str] = None) -> Dict[str, Any]:
        """Generate a RAG answer grounded in retrieved chunks.

        Args:
            query: User's question
            chunks: Retrieved chunks (each with at least chunk_text/arxiv_id, as
                returned by OpenSearchClient.search_unified())
            model: Model name (uses settings.ollama_default_model if None)

        Returns:
            Dict with "answer" (str), "sources" (deduplicated arxiv_ids from the
            retrieved chunks, in order), and "citations" (arxiv_ids the model
            actually cited in [arXiv:id] format within the answer text)
        """
        prompt = self.prompt_builder.create_rag_prompt(query, chunks)
        answer = await self.generate(prompt, model=model, temperature=0.7, top_p=0.9)

        sources = list(dict.fromkeys(chunk.get("arxiv_id") for chunk in chunks if chunk.get("arxiv_id")))
        citations = list(dict.fromkeys(_CITATION_PATTERN.findall(answer)))

        return {
            "answer": answer.strip(),
            "sources": sources,
            "citations": citations,
        }

    async def generate_rag_answer_stream(
        self, query: str, chunks: List[Dict[str, Any]], model: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream a RAG answer grounded in retrieved chunks.

        Args:
            query: User's question
            chunks: Retrieved chunks (each with at least chunk_text/arxiv_id)
            model: Model name (uses settings.ollama_default_model if None)

        Yields:
            Raw Ollama JSON-line dicts, each with "response" (text fragment)
            and "done" (bool) at minimum.
        """
        prompt = self.prompt_builder.create_rag_prompt(query, chunks)
        async for data in self._generate_stream_raw(prompt, model=model, temperature=0.7, top_p=0.9):
            yield data
