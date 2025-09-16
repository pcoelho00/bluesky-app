# Architecture Overview

This document describes the Turso-only architecture of the Bluesky Feed Summarizer.

## Components

- CLI (`bluesky-summarizer`): Entry points for `run`, `fetch`, `summarize`, `posts`, `history`, `status`, `verify`, and `stream`.
- Bluesky client (`src/bluesky_summarizer/bluesky/client.py`): Retrieves posts from Bluesky.
- Database layer (`src/bluesky_summarizer/database/turso_operations.py`): Turso/libSQL client and database manager, responsible for schema initialization and CRUD operations.
- AI summarizer (`src/bluesky_summarizer/ai/summarizer.py`): Uses Anthropic Claude to generate summaries.
- Config (`src/bluesky_summarizer/config.py`): Loads environment variables and runtime settings.
- Streaming service (`src/bluesky_summarizer/streaming/service.py`): Polls Bluesky and persists posts continuously.

## Persistence

Production runs exclusively on Turso/libSQL:

- Connection: `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN` are required.
- Client: Uses the libSQL Python client to connect and execute SQL.
- Schema: Automatically created on first use. Main tables are `posts` and `summaries`.
- Uniqueness: Post uniqueness enforced by `uri`.

## Data Flow

1. CLI parses options and loads config.
2. Database manager connects to Turso and ensures schema.
3. Bluesky client fetches posts for the chosen time window.
4. Posts are upserted into `posts` (duplicate URIs are updated, not reinserted).
5. Summarizer aggregates relevant posts and calls Claude to produce structured text.
6. Summary is stored in `summaries` (unless `--no-save`), and printed to the console.

## Environment Variables

- `BLUESKY_HANDLE`, `BLUESKY_PASSWORD`
- `ANTHROPIC_API_KEY`
- `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`
- Optional tuning: `DEFAULT_DAYS_BACK`, `MAX_POSTS_PER_FETCH`

## Operational Notes

- Turso/libSQL is the only supported backend in production.
- The CLI `status` command reports Turso connection configuration and health checks.
- The system uses idempotent upserts for posts to avoid duplicates and counts new vs updated rows for progress feedback.

## Testing

- Unit tests exercise the database manager contract and CLI commands.
- Mocking the libSQL client is supported by patching the client factory used by the database manager.

## Future Enhancements

- Add export/import utilities for backup and migration.
- Add more integrity checks and maintenance commands.