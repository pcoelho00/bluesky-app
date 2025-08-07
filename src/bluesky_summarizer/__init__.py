"""
Bluesky Feed Summarizer

A Python application that reads Bluesky feeds and generates AI-powered summaries.
"""

__version__ = "1.0.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

# Import main components for easier access
from .database import DatabaseManager
from .bluesky import BlueSkyClient
from .ai import ClaudeSummarizer
from .streaming import StreamingService
from .config import config

__all__ = [
    "DatabaseManager",
    "BlueSkyClient",
    "ClaudeSummarizer",
    "StreamingService",
    "config",
]
