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

    env_label = "local (Local SQLite)"
    db_path = file_values.get("DATABASE_PATH") or os.getenv(
        "DATABASE_PATH", "./data/bluesky_feed.db"
    )
    file_exists = "✓ Yes" if os.path.exists(db_path) else "✗ No"
    table.add_row("Environment", env_label)
    table.add_row("Database Path", db_path)
    table.add_row("File Exists", file_exists)

    # Use top-level shim console if available so tests patching 'db_env_cli.console' capture the call
    try:
        import db_env_cli as _shim  # type: ignore

        _shim.console.print(table)  # type: ignore[attr-defined]
    except Exception:
        console.print(table)


@db.command(name="status")
def db_status():
    """CLI command: show database status."""
    show_db_status()


if __name__ == "__main__":
    db()
