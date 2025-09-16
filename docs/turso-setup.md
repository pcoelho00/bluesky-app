# Using Turso (libSQL) Database

This guide explains how to configure your Bluesky Feed Summarizer to use Turso. Turso/libSQL is the only supported database backend for this project.

## What is Turso?

Turso is a distributed SQLite-compatible database service that provides:
- Global edge locations for low latency
- Built-in replication
- Serverless scaling
- libSQL compatibility (SQLite fork)

## Setup Steps

### 1. Create a Turso Account and Database

1. Sign up at [turso.tech](https://turso.tech)
2. Install the Turso CLI:
   ```bash
   curl -sSfL https://get.tur.so/install.sh | bash
   ```
3. Authenticate:
   ```bash
   turso auth login
   ```
4. Create a database:
   ```bash
   turso db create bluesky-feed
   ```
5. Get your database URL:
   ```bash
   turso db show bluesky-feed --url
   ```
6. Create an auth token:
   ```bash
   turso db tokens create bluesky-feed
   ```

### 2. Configure Environment Variables

Update your `.env` file:

```bash
# Turso configuration (required)
TURSO_DATABASE_URL=libsql://your-database-name.turso.io
TURSO_AUTH_TOKEN=your-turso-auth-token

# Keep your other configuration
BLUESKY_HANDLE=your.handle.bsky.social
BLUESKY_PASSWORD=your_app_password
ANTHROPIC_API_KEY=your_anthropic_api_key
```

### 3. Install Dependencies

The `libsql-client` package should already be installed if you've run:
```bash
pip install -r requirements.txt
```

If not, install it manually:
```bash
pip install libsql-client
```

### 4. Test the Connection

Run the status command to verify everything is working:
```bash
python -m bluesky_summarizer status
```

You should see your Turso database configuration in the output.

## What You Get

- ✅ All CLI commands work with Turso out of the box
- ✅ Automatic schema initialization on first run
- ✅ Managed, globally distributed database

## Cost Considerations

Turso offers:
- Free tier: Up to 500 databases, 1GB total storage
- Pay-as-you-go: $1.50/month per additional GB
- Enterprise plans available

For a typical Bluesky feed summarizer usage, the free tier should be sufficient.

## Troubleshooting

### Connection Issues
- Verify your `TURSO_DATABASE_URL` starts with `libsql://`
- Check that your `TURSO_AUTH_TOKEN` is valid
- Ensure your database exists in Turso

### Performance
- Turso has edge locations worldwide for low latency
- First connection may be slightly slower due to TLS negotiation; subsequent operations should be fast

### Debugging
Enable debug logging to see database operations:
```bash
export LOG_LEVEL=DEBUG
python -m bluesky_summarizer status
```
