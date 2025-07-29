<!-- Use this file to provide workspace-specific custom instructions to Copilot. For more details, visit https://code.visualstudio.com/docs/copilot/copilot-customization#_use-a-githubcopilotinstructionsmd-file -->

# Bluesky Feed Summarizer Project

This is a Python application that reads Bluesky social media feeds and uses Claude AI to generate daily summaries.

## Project Structure Guidelines

- **Database module** (`src/bluesky_summarizer/database/`): Handle SQLite operations for storing and retrieving feed data
- **Bluesky client** (`src/bluesky_summarizer/bluesky/`): Interact with Bluesky's AT Protocol API
- **AI summarizer** (`src/bluesky_summarizer/ai/`): Use Anthropic's Claude API for text summarization
- **CLI interface** (`src/bluesky_summarizer/cli.py`): Command-line interface using Click
- **Configuration** (`src/bluesky_summarizer/config.py`): Handle environment variables and settings

## Code Style Preferences

- Use type hints for all function parameters and return values
- Follow PEP 8 style guidelines
- Use Pydantic models for data validation where appropriate
- Implement proper error handling and logging
- Write docstrings for all classes and functions
- Use dependency injection patterns for better testability

## Key Dependencies

- `atproto`: For Bluesky API interactions
- `anthropic`: For Claude AI integration
- `click`: For CLI interface
- `pydantic`: For data validation
- `sqlite3`: For database operations (built-in)
- `python-dotenv`: For environment variable management
