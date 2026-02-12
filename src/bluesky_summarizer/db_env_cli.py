#!/usr/bin/env python3
"""Database CLI: Environment management."""

import click
import os
from rich.console import Console
from rich.table import Table
from dotenv import load_dotenv

console = Console()


def _read_env_file_values() -> dict[str, str]:
    values: dict[str, str] = {}
    env_file = ".env"
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    values[k.strip()] = v.strip()
    return values


@click.group()
def db():
    """Database environment management commands."""
    pass


def show_db_status():
    """Show current database configuration status."""
    load_dotenv(override=True)
    table = Table(title="Database Status")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    file_values = _read_env_file_values()

    # Determine connection URL: DATABASE_URL takes precedence over DATABASE_PATH
    connection_url = file_values.get("DATABASE_URL") or os.getenv("DATABASE_URL")
    if not connection_url:
        db_path = file_values.get("DATABASE_PATH") or os.getenv(
            "DATABASE_PATH", "./data/bluesky_feed.db"
        )
        connection_url = f"sqlite:///{db_path}"

    # Determine backend label from the URL
    if connection_url.startswith("sqlite"):
        backend_label = "SQLite"
        # Extract file path for existence check
        db_file = connection_url.replace("sqlite:///", "")
        file_exists = "Yes" if os.path.exists(db_file) else "No"
        table.add_row("Backend", backend_label)
        table.add_row("Connection URL", connection_url)
        table.add_row("Database File", db_file)
        table.add_row("File Exists", file_exists)
    else:
        backend_label = connection_url.split("://")[0] if "://" in connection_url else "Unknown"
        table.add_row("Backend", backend_label)
        table.add_row("Connection URL", connection_url)

    console.print(table)


@db.command(name="status")
def db_status():
    """CLI command: show database status."""
    show_db_status()


if __name__ == "__main__":
    db()
