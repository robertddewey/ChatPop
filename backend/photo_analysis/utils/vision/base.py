"""
Base interface for AI vision providers.
Allows for future support of multiple vision models (Claude, Gemini, etc.)
"""
from abc import ABC, abstractmethod
from typing import BinaryIO, Dict, Any, List
from dataclasses import dataclass


@dataclass
class ChatSuggestion:
    """Individual chat room name suggestion."""
    name: str  # Title Case (e.g., "Curious Cat")
    key: str   # lowercase-with-dashes (e.g., "curious-cat")
    description: str  # Short description


@dataclass
class AnalysisResult:
    """Result from AI vision analysis."""
    suggestions: List[ChatSuggestion]
    raw_response: Dict[str, Any]
    token_usage: Dict[str, int]
    model: str


class VisionProvider(ABC):
    """Abstract base class for AI vision providers."""

    @abstractmethod
    def analyze_image(
        self,
        image_file: BinaryIO,
        prompt: str,
        max_suggestions: int = 10
    ) -> AnalysisResult:
        """
        Analyze an image and generate chat room suggestions.

        Args:
            image_file: Image file to analyze
            prompt: System prompt for analysis
            max_suggestions: Number of suggestions to generate

        Returns:
            AnalysisResult with suggestions and metadata

        Raises:
            ValueError: If image cannot be processed
            RuntimeError: If API call fails
        """
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """
        Get the model identifier.

        Returns:
            Model name (e.g., "gpt-4o", "claude-3-opus")
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the provider is available (API key configured, etc.).

        Returns:
            True if provider can be used, False otherwise
        """
        pass
