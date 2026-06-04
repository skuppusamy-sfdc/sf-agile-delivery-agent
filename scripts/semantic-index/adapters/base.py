"""Abstract base for all LLM batch processing adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class BatchRequest:
    """A single request to be processed by an LLM."""
    custom_id: str
    prompt: str
    model: str = ""
    max_tokens: int = 4096
    temperature: float = 0.0
    system: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class BatchResponse:
    """A single response from an LLM."""
    custom_id: str
    status: str  # "success" | "error" | "timeout"
    output: dict[str, Any] | None = None
    raw_text: str = ""
    error: str | None = None
    usage: dict[str, int] | None = None


class BatchAdapter(ABC):
    """Provider-agnostic batch processing interface.

    Implementations handle the specifics of submitting requests to a particular
    LLM provider (Anthropic Batch API, OpenAI Batch API, local models, or
    file-based manual processing).
    """

    @abstractmethod
    def submit(self, requests: list[BatchRequest]) -> str:
        """Submit a batch of requests. Returns a batch_id for tracking."""
        ...

    @abstractmethod
    def poll(self, batch_id: str) -> str:
        """Check batch status. Returns: 'pending' | 'processing' | 'completed' | 'failed'."""
        ...

    @abstractmethod
    def collect(self, batch_id: str) -> list[BatchResponse]:
        """Collect results once batch is completed."""
        ...

    @abstractmethod
    def provider_name(self) -> str:
        """Return identifier for this provider."""
        ...
