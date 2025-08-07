# Bluesky Live Streaming Service

Continuously monitors Bluesky for new posts and updates the database in real-time using periodic polling.

## Quick Start

```bash
# Basic streaming (30-second polling)
bluesky-summarizer stream

# Follow specific users
bluesky-summarizer stream --users alice.bsky.social --users bob.bsky.social

# Filter by keywords
bluesky-summarizer stream --keywords ai --keywords python

# Custom polling interval (60 seconds)
bluesky-summarizer stream --poll-interval 60

# Combine filters
bluesky-summarizer stream --users tech.bsky.social --keywords ai
```
# From the project directory
python -m src.bluesky_summarizer.cli stream --poll-interval 60
```

## Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--poll-interval` | `-i` | 30 | Polling interval in seconds |
| `--users` | `-u` | None | User handles to follow (repeatable) |
| `--keywords` | `-k` | None | Keywords to filter (repeatable) |
| `--stats-interval` | `-s` | 300 | Stats display interval in seconds |

## Filtering

- **User filtering**: `--users alice.bsky.social` - Only save posts from specific users
- **Keyword filtering**: `--keywords ai --keywords python` - Only save posts containing keywords  
- **Combined filtering**: Both user AND keyword filters must match

## Performance Tips

- **Polling intervals**: 30-60 seconds recommended (balance freshness vs API usage)
- **Filtering**: Use filters to reduce volume and processing
## Troubleshooting

**Authentication Failed**: Check `BLUESKY_HANDLE` and `BLUESKY_PASSWORD` environment variables

**No Posts Saved**: Check your filters - they might be too restrictive

**Debug Mode**: Use `bluesky-summarizer stream --verbose` for detailed logging

## Integration

Works alongside other commands:
```bash
# Stream in one terminal
bluesky-summarizer stream

# Generate summaries in another terminal  
bluesky-summarizer summarize --days 1
```
- Consider the database location in your file system permissions

## Examples

```bash
# Monitor timeline with default settings
bluesky-summarizer stream

# Follow tech users with 2-minute polling
bluesky-summarizer stream --poll-interval 120 --users tech.bsky.social

# AI/ML content monitoring
bluesky-summarizer stream --keywords ai --keywords "machine learning" --keywords python

# High-frequency monitoring for breaking news
bluesky-summarizer stream --poll-interval 10 --keywords breaking --keywords news
```
