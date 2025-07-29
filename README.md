Completely written with AI, use at your own risk.

# Bluesky Feed Summarizer

A Python application that reads your Bluesky social media feed and uses Claude AI to generate intelligent daily summaries. The application separates the logic of reading and saving feed data to a SQLite database from the AI summarization functionality, with flexible date range options.

## Features

- 🔄 **Fetch Bluesky Posts**: Automatically retrieve posts from your Bluesky timeline
- 💾 **SQLite Storage**: Efficiently store posts in a local SQLite database
- 🤖 **AI Summarization**: Generate intelligent summaries using Claude AI
- 📅 **Flexible Date Ranges**: Specify custom date ranges for fetching and summarizing
- 🖥️ **CLI Interface**: Easy-to-use command-line interface with rich output
- ⚙️ **Configurable**: Customizable settings via environment variables

## Installation

### Prerequisites

- Python 3.8 or higher
- Bluesky account with app password
- Anthropic API key for Claude

### Setup

1. **Clone or navigate to the project directory**:
   ```bash
   cd /home/pedrocoelho/bluesky-app
   ```

2. **Install the package in development mode**:
   ```bash
   pip install -e .
   ```

3. **Copy the environment template and configure**:
   ```bash
   cp .env.example .env
   ```

4. **Edit the `.env` file with your credentials**:
   ```bash
   # Bluesky credentials
   BLUESKY_HANDLE=your.handle.bsky.social
   BLUESKY_PASSWORD=your_app_password

   # Claude AI credentials
   ANTHROPIC_API_KEY=your_anthropic_api_key

   # Database settings (optional)
   DATABASE_PATH=./data/bluesky_feed.db
   DEFAULT_DAYS_BACK=1
   MAX_POSTS_PER_FETCH=100
   ```

### Getting Your Credentials

#### Bluesky App Password
1. Go to [Bluesky Settings](https://bsky.app/settings)
2. Navigate to "Privacy and Security" > "App Passwords"
3. Create a new app password for this application

#### Anthropic API Key
1. Sign up at [Anthropic](https://www.anthropic.com/)
2. Navigate to your API dashboard
3. Generate a new API key

## Usage

### Quick Start

**Fetch today's posts and generate a summary**:
```bash
bluesky-summarizer run
```

**Fetch posts from the last 3 days and summarize**:
```bash
bluesky-summarizer run --days 3
```

### Detailed Commands

#### Fetch Posts Only
```bash
# Fetch posts from the last day (default)
bluesky-summarizer fetch

# Fetch posts from the last 7 days
bluesky-summarizer fetch --days 7

# Fetch posts for a specific date range
bluesky-summarizer fetch --start-date 2024-01-01 --end-date 2024-01-02

# Limit the number of posts per fetch request
bluesky-summarizer fetch --limit 50
```

#### Generate Summaries Only
```bash
# Summarize posts from the last day (default)
bluesky-summarizer summarize

# Summarize posts from the last 3 days
bluesky-summarizer summarize --days 3

# Use a specific Claude model
bluesky-summarizer summarize --model claude-3-haiku-20240307

# Generate summary without saving to database
bluesky-summarizer summarize --no-save
```

#### View Summary History
```bash
# Show the latest summary
bluesky-summarizer history

# Show multiple recent summaries
bluesky-summarizer history --limit 5
```

#### Check Application Status
```bash
bluesky-summarizer status
```

### Advanced Usage

#### Custom Date Ranges
```bash
# Process a specific week
bluesky-summarizer run --start-date 2024-01-01 --end-date 2024-01-07

# Fetch posts from last month and summarize
bluesky-summarizer run --days 30
```

#### Different Claude Models
The application supports various Claude models:
- `claude-3-7-sonnet-latest` (default, balanced performance)
- `claude-3-haiku-20240307` (faster, more cost-effective)
- `claude-3-opus-20240229` (highest quality, slower)

```bash
bluesky-summarizer summarize --model claude-3-opus-20240229
```

## Project Structure

```
src/bluesky_summarizer/
├── __init__.py                 # Package initialization
├── config.py                   # Configuration management
├── cli.py                      # Command-line interface
├── database/                   # Database operations
│   ├── __init__.py
│   ├── models.py              # Data models (Post, Summary)
│   └── operations.py          # Database manager
├── bluesky/                   # Bluesky API client
│   ├── __init__.py
│   └── client.py              # BlueSky API client
└── ai/                        # AI summarization
    ├── __init__.py
    └── summarizer.py          # Claude AI summarizer
```

## Configuration

All configuration is managed through environment variables. See `.env.example` for all available options:

- **BLUESKY_HANDLE**: Your Bluesky handle
- **BLUESKY_PASSWORD**: Your Bluesky app password
- **ANTHROPIC_API_KEY**: Your Anthropic API key
- **DATABASE_PATH**: Path to SQLite database file
- **DEFAULT_DAYS_BACK**: Default number of days to look back
- **MAX_POSTS_PER_FETCH**: Maximum posts per API request

## Database Schema

The application uses SQLite with two main tables:

### Posts Table
- `id`: Primary key
- `uri`: Unique post identifier
- `cid`: Content identifier
- `author_handle`: Post author's handle
- `author_did`: Post author's decentralized identifier
- `text`: Post content
- `created_at`: When the post was created
- `like_count`, `repost_count`, `reply_count`: Engagement metrics
- `indexed_at`: When the post was saved to database

### Summaries Table
- `id`: Primary key
- `start_date`, `end_date`: Date range of summarized posts
- `post_count`: Number of posts summarized
- `summary_text`: Generated summary
- `model_used`: Claude model used for generation
- `created_at`: When the summary was created

## Error Handling

The application includes comprehensive error handling:

- **Network Issues**: Automatic retry logic for API calls
- **Authentication Errors**: Clear error messages for credential issues
- **Database Errors**: Graceful handling of database connection issues
- **Rate Limiting**: Respects API rate limits

## WSL Compatibility

This application is fully compatible with Windows Subsystem for Linux (WSL). The SQLite database and all file operations work seamlessly in the WSL environment.

## Development

### Running Tests
```bash
# Run all tests
python run_tests.py

# Or run tests with pytest directly
python -m pytest test_bluesky_summarizer.py -v

# Run specific test categories
python -m pytest test_bluesky_summarizer.py::TestDatetimeComparison -v
```

The test suite covers:
- **Timezone handling**: Ensures datetime comparisons work correctly
- **Pydantic models**: Validates data models and type safety
- **Database operations**: Tests SQLite storage and retrieval
- **Bluesky client**: Mocks API interactions and data conversion
- **AI summarization**: Tests Claude integration with mock responses
- **Integration**: End-to-end workflow validation

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite: `python run_tests.py`
6. Submit a pull request

## Troubleshooting

### Common Issues

**Authentication Failed**:
- Verify your Bluesky handle and app password
- Ensure you're using an app password, not your regular password

**API Key Errors**:
- Check that your Anthropic API key is valid
- Verify you have sufficient API credits

**Database Permissions**:
- Ensure the database directory is writable
- Check file permissions in WSL environments

**No Posts Found**:
- Verify the date range includes when you were active on Bluesky
- Check if your timeline has posts in the specified period

### Logs

Enable verbose logging for debugging:
```bash
bluesky-summarizer --verbose run
```

## License

MIT License - see LICENSE file for details.

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review the application logs with `--verbose` flag
3. Open an issue with detailed error information
