"""
Command Line Interface for the Bluesky Feed Summarizer.
"""

import logging
import sys
from datetime import datetime, timedelta
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from .config import config
from .utils.dates import resolve_date_range
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
        save_result = db_manager.save_posts(posts)
        progress.update(
            task,
            description=f"Saved {save_result['new']} new posts, updated {save_result['updated']} existing ✓",
        )

    # Display results
    table = Table(title="Fetch Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Date Range", f"{start_date.date()} to {end_date.date()}")
    table.add_row("Posts Fetched", str(len(posts)))
    table.add_row("New Posts Saved", str(save_result["new"]))
    table.add_row("Existing Posts Updated", str(save_result["updated"]))
    table.add_row("Total Posts Processed", str(save_result["total"]))
    table.add_row("Database Path", config.database.path)

    console.print(table)
    return save_result["new"]


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
    "--older-than-days",
    "-d",
    type=int,
    required=True,
    help="Delete posts older than this many days",
)
@click.option(
    "--vacuum/--no-vacuum",
    default=True,
    help="Run VACUUM after pruning to reclaim space (default: True)",
)
def prune(older_than_days: int, vacuum: bool):
    """Prune (delete) posts older than the specified number of days."""
    try:
        if older_than_days <= 0:
            raise click.BadParameter("older-than-days must be positive")

        cutoff = datetime.utcnow() - timedelta(days=older_than_days)
        db_manager = DatabaseManager(config.database.path)
        deleted = db_manager.prune_posts_older_than(cutoff)
        after_count = db_manager.get_total_post_count()

        if vacuum and deleted > 0:
            db_manager.vacuum()
        size_bytes = db_manager.get_db_size_bytes()

        result_table = Table(title="Prune Results")
        result_table.add_column("Metric", style="cyan")
        result_table.add_column("Value", style="green")
        result_table.add_row("Cutoff", cutoff.strftime("%Y-%m-%d %H:%M:%S UTC"))
        result_table.add_row("Deleted Posts", str(deleted))
        result_table.add_row("Remaining Posts", str(after_count))
        result_table.add_row("Database Size (KB)", f"{size_bytes / 1024:.1f}")
        result_table.add_row(
            "Vacuum Performed", "Yes" if vacuum and deleted > 0 else "No"
        )
        console.print(result_table)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Error in prune command")
        sys.exit(1)
    # No return value needed


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
        fetch_start, fetch_end = resolve_date_range(
            start=start_date,
            end=end_date,
            days=days,
            default_days_back=config.app.default_days_back,
        )
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
        summary_start, summary_end = resolve_date_range(
            start=start_date,
            end=end_date,
            days=days,
            default_days_back=config.app.default_days_back,
        )
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
        process_start, process_end = resolve_date_range(
            start=start_date,
            end=end_date,
            days=days,
            default_days_back=config.app.default_days_back,
        )

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
@click.option(
    "--days",
    "-d",
    default=None,
    type=int,
    help="Number of days back to show posts (default: from config)",
)
@click.option(
    "--start-date", type=click.DateTime(["%Y-%m-%d"]), help="Start date (YYYY-MM-DD)"
)
@click.option(
    "--end-date", type=click.DateTime(["%Y-%m-%d"]), help="End date (YYYY-MM-DD)"
)
@click.option(
    "--limit", "-l", default=50, type=int, help="Maximum number of posts to show"
)
@click.option(
    "--author",
    "-a",
    default=None,
    help="Filter by author handle (e.g., user.bsky.social)",
)
def posts(
    days: Optional[int],
    start_date: Optional[datetime],
    end_date: Optional[datetime],
    limit: int,
    author: Optional[str],
):
    """Display saved posts from the database in chronological order."""

    try:
        query_start, query_end = resolve_date_range(
            start=start_date,
            end=end_date,
            days=days,
            default_days_back=config.app.default_days_back,
        )

        console.print(
            f"[blue]Loading posts from {query_start.date()} to {query_end.date()}[/blue]"
        )

        # Initialize database manager
        db_manager = DatabaseManager(config.database.path)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Loading posts from database...", total=None)

            # Get posts from database
            all_posts = db_manager.get_posts_by_date_range(query_start, query_end)

            # Filter by author if specified
            if author:
                all_posts = [
                    post
                    for post in all_posts
                    if author.lower() in post.author_handle.lower()
                ]
                progress.update(
                    task,
                    description=f"Filtered {len(all_posts)} posts by author '{author}' ✓",
                )
            else:
                progress.update(task, description=f"Loaded {len(all_posts)} posts ✓")

            # Sort posts chronologically (oldest first)
            sorted_posts = sorted(all_posts, key=lambda p: p.created_at)

            # Apply limit
            display_posts = sorted_posts[:limit] if limit > 0 else sorted_posts

        if not display_posts:
            console.print("[yellow]No posts found in the specified criteria.[/yellow]")
            return

        # Display summary info
        summary_table = Table(title="Posts Query Summary")
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Value", style="green")

        summary_table.add_row(
            "Date Range", f"{query_start.date()} to {query_end.date()}"
        )
        summary_table.add_row("Total Posts Found", str(len(all_posts)))
        summary_table.add_row("Posts Displayed", str(len(display_posts)))
        if author:
            summary_table.add_row("Author Filter", author)

        console.print(summary_table)
        console.print()

        # Display posts
        for i, post in enumerate(display_posts, 1):
            # Create engagement info
            engagement = (
                f"❤️ {post.like_count} | 🔄 {post.repost_count} | 💬 {post.reply_count}"
            )

            # Format timestamp
            timestamp = post.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")

            # Create post panel
            panel = Panel(
                f"[bold]{post.text}[/bold]\n\n[dim]{engagement}[/dim]",
                title=f"#{i} • @{post.author_handle} • {timestamp}",
                subtitle=f"URI: {post.uri}",
                border_style="blue" if i % 2 == 1 else "green",
                expand=False,
            )
            console.print(panel)

        # Show pagination info if limited
        if len(all_posts) > limit:
            console.print(
                f"\n[yellow]Showing {len(display_posts)} of {len(all_posts)} posts. "
                f"Use --limit to show more.[/yellow]"
            )

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Error in posts command")
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

            # Get total post count
            total_posts = db_manager.get_total_post_count()
            table.add_row("Total Posts", str(total_posts))

        except Exception:
            table.add_row("Latest Summary", "Error reading database")

    console.print(table)


@cli.command()
@click.option(
    "--poll-interval",
    "-i",
    default=30,
    type=int,
    help="Polling interval in seconds (default: 30)",
)
@click.option(
    "--users",
    "-u",
    multiple=True,
    help="Specific user handles to follow (can be used multiple times)",
)
@click.option(
    "--keywords",
    "-k",
    multiple=True,
    help="Keywords to filter posts (can be used multiple times)",
)
@click.option(
    "--stats-interval",
    "-s",
    default=300,
    type=int,
    help="How often to display stats in seconds (default: 300)",
)
def stream(poll_interval: int, users: tuple, keywords: tuple, stats_interval: int):
    """Start live streaming service to continuously monitor Bluesky for new posts."""

    try:
        from .streaming import StreamingService

        # Convert tuples to sets
        user_handles = set(users) if users else None
        keyword_set = set(keywords) if keywords else None

        console.print("[blue]🚀 Starting Bluesky streaming service...[/blue]")

        # Display configuration
        config_table = Table(title="Streaming Configuration")
        config_table.add_column("Setting", style="cyan")
        config_table.add_column("Value", style="green")

        config_table.add_row("Poll Interval", f"{poll_interval} seconds")
        config_table.add_row("Stats Interval", f"{stats_interval} seconds")
        config_table.add_row("Database Path", config.database.path)

        if user_handles:
            config_table.add_row("Following Users", ", ".join(user_handles))
        else:
            config_table.add_row("Following Users", "All users (timeline)")

        if keyword_set:
            config_table.add_row("Keyword Filters", ", ".join(keyword_set))
        else:
            config_table.add_row("Keyword Filters", "None (all posts)")

        console.print(config_table)
        console.print()

        # Create and start the streaming service
        with StreamingService(
            user_handles=user_handles,
            keywords=keyword_set,
            poll_interval=poll_interval,
        ) as service:
            console.print(
                "[green]✅ Streaming service started! Press Ctrl+C to stop.[/green]"
            )
            console.print()

            # Start the service in a background thread
            import threading
            import time

            service_thread = threading.Thread(target=service.start, daemon=True)
            service_thread.start()

            # Wait a moment for service to start
            time.sleep(2)

            # Display stats periodically
            last_stats_time = time.time()

            try:
                while service.is_running:
                    current_time = time.time()

                    # Display stats at interval
                    if current_time - last_stats_time >= stats_interval:
                        stats = service.get_stats()

                        stats_table = Table(title="Streaming Statistics")
                        stats_table.add_column("Metric", style="cyan")
                        stats_table.add_column("Value", style="green")

                        stats_table.add_row(
                            "Status",
                            "🟢 Running" if stats["is_running"] else "🔴 Stopped",
                        )

                        if stats["runtime_seconds"]:
                            runtime_str = f"{stats['runtime_seconds']:.1f} seconds"
                            if stats["runtime_seconds"] > 60:
                                minutes = stats["runtime_seconds"] // 60
                                seconds = stats["runtime_seconds"] % 60
                                runtime_str = f"{minutes:.0f}m {seconds:.0f}s"
                        else:
                            runtime_str = "N/A"

                        stats_table.add_row("Runtime", runtime_str)
                        stats_table.add_row(
                            "Posts Processed", str(stats["posts_processed"])
                        )
                        stats_table.add_row("Posts Saved", str(stats["posts_saved"]))
                        stats_table.add_row(
                            "Processing Rate",
                            f"{stats['posts_per_minute']:.1f} posts/min",
                        )

                        if stats["last_check"]:
                            last_check_str = stats["last_check"].strftime("%H:%M:%S")
                        else:
                            last_check_str = "Never"

                        stats_table.add_row("Last Check", last_check_str)

                        console.print(stats_table)
                        console.print()

                        last_stats_time = current_time

                    time.sleep(1)

            except KeyboardInterrupt:
                console.print(
                    "\n[yellow]📡 Received stop signal, shutting down streaming service...[/yellow]"
                )
                service.stop()

            # Wait for service thread to finish
            service_thread.join(timeout=10)

            # Display final stats
            final_stats = service.get_stats()

            final_table = Table(title="Final Streaming Results")
            final_table.add_column("Metric", style="cyan")
            final_table.add_column("Value", style="green")

            if final_stats["runtime_seconds"]:
                runtime_str = f"{final_stats['runtime_seconds']:.1f} seconds"
                if final_stats["runtime_seconds"] > 60:
                    minutes = final_stats["runtime_seconds"] // 60
                    seconds = final_stats["runtime_seconds"] % 60
                    runtime_str = f"{minutes:.0f}m {seconds:.0f}s"
            else:
                runtime_str = "N/A"

            final_table.add_row("Total Runtime", runtime_str)
            final_table.add_row("Posts Processed", str(final_stats["posts_processed"]))
            final_table.add_row("Posts Saved", str(final_stats["posts_saved"]))
            final_table.add_row(
                "Average Rate", f"{final_stats['posts_per_minute']:.1f} posts/min"
            )

            console.print(final_table)
            console.print("[green]✅ Streaming service stopped successfully.[/green]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Error in stream command")
        sys.exit(1)


@cli.command()
def verify():
    """Verify database integrity and check for duplicate posts."""

    try:
        db_manager = DatabaseManager(config.database.path)

        console.print("[blue]🔍 Verifying database integrity...[/blue]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Analyzing database...", total=None)

            # Get total post count
            total_posts = db_manager.get_total_post_count()
            progress.update(task, description=f"Found {total_posts} total posts ✓")

            # Check for URI uniqueness (should be enforced by database constraint)
            unique_uris = db_manager.get_unique_uri_count()
            progress.update(task, description=f"Verified {unique_uris} unique URIs ✓")

        # Display results
        verification_table = Table(title="Database Verification Results")
        verification_table.add_column("Check", style="cyan")
        verification_table.add_column("Result", style="green")

        verification_table.add_row("Total Posts", str(total_posts))
        verification_table.add_row("Unique URIs", str(unique_uris))

        if total_posts == unique_uris:
            verification_table.add_row(
                "URI Uniqueness", "✅ All posts have unique URIs"
            )
        else:
            verification_table.add_row(
                "URI Uniqueness",
                f"⚠️ Found {total_posts - unique_uris} potential duplicates",
            )

        # Check for posts with same content but different URIs
        duplicate_content = db_manager.get_duplicate_content_count()
        verification_table.add_row(
            "Duplicate Content",
            f"Found {duplicate_content} posts with duplicate text"
            if duplicate_content > 0
            else "✅ No duplicate content found",
        )

        console.print(verification_table)

        if total_posts == unique_uris and duplicate_content == 0:
            console.print(
                "\n[green]✅ Database integrity verified! All posts are unique.[/green]"
            )
        else:
            console.print(
                "\n[yellow]⚠️ Some duplicates or integrity issues found. This is usually normal due to content updates or reposts.[/yellow]"
            )

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Error in verify command")
        sys.exit(1)


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
