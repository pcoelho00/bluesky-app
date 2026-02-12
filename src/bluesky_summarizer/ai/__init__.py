"""AI summarization module using multiple providers."""

from __future__ import annotations

from .claude_summarizer import ClaudeSummarizer

__all__ = ["ClaudeSummarizer", "OpenAISummarizer", "GeminiSummarizer"]


def __getattr__(name: str):
    if name == "OpenAISummarizer":
        from .openai_summarizer import OpenAISummarizer

        return OpenAISummarizer
    if name == "GeminiSummarizer":
        from .gemini_summarizer import GeminiSummarizer

        return GeminiSummarizer
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
