"""
Command Line Interface for the Bluesky Feed Summarizer.
"""

import logging
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from .config import config
from .database import DatabaseManager
from .bluesky import BlueSkyClient
from .ai import ClaudeSummarizer


# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Rich console for beautiful output
console = Console()


def _fetch_posts_logic(
    start_date: datetime, end_date: datetime, limit: Optional[int] = None
) -> int:
    """Core logic for fetching posts. Returns number of saved posts."""
    fetch_limit = limit or config.app.max_posts_per_fetch

    console.print(
        f"[blue]Fetching posts from {start_date.date()} to {end_date.date()}[/blue]"
    )

    # Initialize components
    db_manager = DatabaseManager(config.database.path)
    bluesky_client = BlueSkyClient(config.bluesky.handle, config.bluesky.password)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Authenticate
        task = progress.add_task("Authenticating with Bluesky...", total=None)
        if not bluesky_client.authenticate():
            console.print("[red]Failed to authenticate with Bluesky[/red]")
            raise RuntimeError("Failed to authenticate with Bluesky")
        progress.update(task, description="Authenticated ✓")

        # Fetch posts
        progress.update(task, description="Fetching timeline posts...")
        posts = bluesky_client.fetch_timeline_posts(start_date, end_date, fetch_limit)
        progress.update(task, description=f"Fetched {len(posts)} posts ✓")

        # Save to database
        progress.update(task, description="Saving posts to database...")
        saved_count = db_manager.save_posts(posts)
        progress.update(task, description=f"Saved {saved_count} new posts ✓")

    # Display results
    table = Table(title="Fetch Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Date Range", f"{start_date.date()} to {end_date.date()}")
    table.add_row("Posts Fetched", str(len(posts)))
    table.add_row("New Posts Saved", str(saved_count))
    table.add_row("Database Path", config.database.path)

    console.print(table)
    return saved_count


def _summarize_posts_logic(
    start_date: datetime, end_date: datetime, model: str, save: bool = True
) -> str:
    """Core logic for summarizing posts. Returns summary text."""
    console.print(
        f"[blue]Generating summary for {start_date.date()} to {end_date.date()}[/blue]"
    )

    # Initialize components
    db_manager = DatabaseManager(config.database.path)
    summarizer = ClaudeSummarizer(config.anthropic.api_key, model)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Get posts from database
        task = progress.add_task("Loading posts from database...", total=None)
        posts = db_manager.get_posts_by_date_range(start_date, end_date)
        progress.update(task, description=f"Loaded {len(posts)} posts ✓")

        if not posts:
            console.print(
                "[yellow]No posts found in the specified date range.[/yellow]"
            )
            return "No posts found in the specified date range."

        # Generate summary
        progress.update(task, description="Generating AI summary...")
        summary = summarizer.summarize_posts(posts, start_date, end_date)
        progress.update(task, description="Summary generated ✓")

        # Save summary if requested
        if save:
            progress.update(task, description="Saving summary to database...")
            summary_id = db_manager.save_summary(summary)
            progress.update(task, description=f"Summary saved (ID: {summary_id}) ✓")

    # Display summary
    panel = Panel(
        summary.summary_text,
        title=f"📝 Feed Summary ({start_date.date()} to {end_date.date()})",
        subtitle=f"Generated with {model} • {len(posts)} posts analyzed",
        border_style="blue",
    )
    console.print(panel)
    return summary.summary_text


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def cli(verbose: bool):
    """Bluesky Feed Summarizer - Generate AI summaries of your Bluesky timeline."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
@click.option(
    "--days",
    "-d",
    default=None,
    type=int,
    help="Number of days back to fetch (default: from config)",
)
@click.option(
    "--start-date", type=click.DateTime(["%Y-%m-%d"]), help="Start date (YYYY-MM-DD)"
)
@click.option(
    "--end-date", type=click.DateTime(["%Y-%m-%d"]), help="End date (YYYY-MM-DD)"
)
@click.option(
    "--limit",
    "-l",
    default=None,
    type=int,
    help="Maximum number of posts to fetch per request",
)
def fetch(
    days: Optional[int],
    start_date: Optional[datetime],
    end_date: Optional[datetime],
    limit: Optional[int],
):
    """Fetch posts from Bluesky timeline and save to database."""

    try:
        # Determine date range
        if start_date and end_date:
            fetch_start = start_date
            fetch_end = end_date
        elif days:
            fetch_end = datetime.now(timezone.utc)
            fetch_start = fetch_end - timedelta(days=days)
        else:
            fetch_end = datetime.now(timezone.utc)
            fetch_start = fetch_end - timedelta(days=config.app.default_days_back)

        _fetch_posts_logic(fetch_start, fetch_end, limit)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Error in fetch command")
        sys.exit(1)


@cli.command()
@click.option(
    "--days",
    "-d",
    default=None,
    type=int,
    help="Number of days back to summarize (default: from config)",
)
@click.option(
    "--start-date", type=click.DateTime(["%Y-%m-%d"]), help="Start date (YYYY-MM-DD)"
)
@click.option(
    "--end-date", type=click.DateTime(["%Y-%m-%d"]), help="End date (YYYY-MM-DD)"
)
@click.option(
    "--model",
    "-m",
    default="claude-3-7-sonnet-latest",
    help="Claude model to use for summarization",
)
@click.option(
    "--save/--no-save", default=True, help="Save summary to database (default: True)"
)
def summarize(
    days: Optional[int],
    start_date: Optional[datetime],
    end_date: Optional[datetime],
    model: str,
    save: bool,
):
    """Generate AI summary of posts in the database."""

    try:
        # Determine date range
        if start_date and end_date:
            summary_start = start_date
            summary_end = end_date
        elif days:
            summary_end = datetime.now(timezone.utc)
            summary_start = summary_end - timedelta(days=days)
        else:
            summary_end = datetime.now(timezone.utc)
            summary_start = summary_end - timedelta(days=config.app.default_days_back)

        _summarize_posts_logic(summary_start, summary_end, model, save)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Error in summarize command")
        sys.exit(1)


@cli.command()
@click.option(
    "--days",
    "-d",
    default=None,
    type=int,
    help="Number of days back to process (default: from config)",
)
@click.option(
    "--start-date", type=click.DateTime(["%Y-%m-%d"]), help="Start date (YYYY-MM-DD)"
)
@click.option(
    "--end-date", type=click.DateTime(["%Y-%m-%d"]), help="End date (YYYY-MM-DD)"
)
@click.option(
    "--limit",
    "-l",
    default=None,
    type=int,
    help="Maximum number of posts to fetch per request",
)
@click.option(
    "--model",
    "-m",
    default="claude-3-7-sonnet-latest",
    help="Claude model to use for summarization",
)
def run(
    days: Optional[int],
    start_date: Optional[datetime],
    end_date: Optional[datetime],
    limit: Optional[int],
    model: str,
):
    """Fetch posts and generate summary in one command."""

    console.print(
        "[bold blue]🚀 Running complete feed summarization process[/bold blue]"
    )

    try:
        # Determine date range
        if start_date and end_date:
            process_start = start_date
            process_end = end_date
        elif days:
            process_end = datetime.now(timezone.utc)
            process_start = process_end - timedelta(days=days)
        else:
            process_end = datetime.now(timezone.utc)
            process_start = process_end - timedelta(days=config.app.default_days_back)

        # Run fetch
        console.print("\n[bold]Step 1: Fetching posts[/bold]")
        _fetch_posts_logic(process_start, process_end, limit)

        # Run summarize
        console.print("\n[bold]Step 2: Generating summary[/bold]")
        _summarize_posts_logic(process_start, process_end, model, save=True)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Error in run command")
        sys.exit(1)


@cli.command()
@click.option(
    "--limit", "-l", default=10, type=int, help="Number of recent summaries to show"
)
def history(limit: int):
    """Show recent summaries from the database."""

    try:
        db_manager = DatabaseManager(config.database.path)

        # This would need to be implemented in DatabaseManager
        # For now, just show the latest summary
        latest_summary = db_manager.get_latest_summary()

        if not latest_summary:
            console.print("[yellow]No summaries found in database.[/yellow]")
            return

        panel = Panel(
            latest_summary.summary_text,
            title=f"📝 Latest Summary ({latest_summary.start_date.date()} to {latest_summary.end_date.date()})",
            subtitle=f"Generated with {latest_summary.model_used} • {latest_summary.post_count} posts • {latest_summary.created_at}",
            border_style="green",
        )
        console.print(panel)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Error in history command")
        sys.exit(1)


@cli.command()
def status():
    """Show application status and configuration."""

    table = Table(title="Bluesky Feed Summarizer Status")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    # Try to load config, but handle missing environment variables gracefully
    try:
        bluesky_handle = config.bluesky.handle
    except ValueError:
        bluesky_handle = "❌ Not configured (set BLUESKY_HANDLE)"

    try:
        db_path = config.database.path
    except ValueError:
        db_path = "./data/bluesky_feed.db"  # default value

    try:
        default_days = str(config.app.default_days_back)
        max_posts = str(config.app.max_posts_per_fetch)
    except ValueError:
        default_days = "1"  # default value
        max_posts = "100"  # default value

    table.add_row("Bluesky Handle", bluesky_handle)
    table.add_row("Database Path", db_path)
    table.add_row("Default Days Back", default_days)
    table.add_row("Max Posts Per Fetch", max_posts)

    # Check if database exists
    import os

    db_exists = os.path.exists(db_path)
    table.add_row("Database Exists", "✓ Yes" if db_exists else "✗ No")

    if db_exists:
        try:
            db_manager = DatabaseManager(db_path)
            latest_summary = db_manager.get_latest_summary()
            if latest_summary:
                table.add_row(
                    "Latest Summary",
                    latest_summary.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                )
            else:
                table.add_row("Latest Summary", "None")
        except Exception:
            table.add_row("Latest Summary", "Error reading database")

    console.print(table)


def main():
    """Main entry point for the CLI application."""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        logger.exception("Unexpected error in main")
        sys.exit(1)


if __name__ == "__main__":
    main()
