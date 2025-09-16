"""
Bluesky Feed Summarizer

A Python application that reads Bluesky feeds and generates AI-powered summaries.
"""

__version__ = "1.0.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

# Avoid importing heavy submodules at package import time to reduce side effects
# and environment variable requirements during tests that only need CLI helpers.

__all__ = ["__version__", "__author__", "__email__"]
