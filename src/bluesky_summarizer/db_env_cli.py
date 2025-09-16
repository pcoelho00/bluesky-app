#!/usr/bin/env python3
"""Database CLI: Environment management compatible with legacy tests."""

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
    """Show current database configuration status with environment label."""
    load_dotenv(override=True)
    table = Table(title="Turso Database Status")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    file_values = _read_env_file_values()
    env = file_values.get("DB_ENVIRONMENT") or os.getenv("DB_ENVIRONMENT", "local")
    if env == "production":
        env_label = "production (Turso Cloud)"
        turso_url = file_values.get("TURSO_DATABASE_URL") or os.getenv(
            "TURSO_DATABASE_URL", "✗ Not configured"
        )
        turso_token = (
            "✓ Configured"
            if (file_values.get("TURSO_AUTH_TOKEN") or os.getenv("TURSO_AUTH_TOKEN"))
            else "✗ Not configured"
        )
        table.add_row("Environment", env_label)
        table.add_row("Turso URL", turso_url)
        table.add_row("Turso Token", turso_token)
    else:
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


@db.command(
    name="switch", help="Switch between local and production database environments"
)
@click.argument("environment", type=click.Choice(["local", "production"]))
def db_switch(environment: str):
    """Switch database environment and update .env accordingly (test-compatible)."""
    load_dotenv(override=True)
    file_values = _read_env_file_values()
    current = file_values.get("DB_ENVIRONMENT") or os.getenv("DB_ENVIRONMENT", "local")
    if current == environment:
        console.print(f"Already using {environment} database environment")
        show_db_status()
        return

    env_file = ".env"
    existing: dict[str, str] = dict(file_values)
    # Load existing .env content preserving other variables
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    existing[k.strip()] = v.strip()

    if environment == "production":
        # Prefer values from .env file; only fall back to process env if not present in file
        turso_url = existing.get("TURSO_DATABASE_URL") or os.getenv(
            "TURSO_DATABASE_URL"
        )
        turso_token = existing.get("TURSO_AUTH_TOKEN") or os.getenv("TURSO_AUTH_TOKEN")
        if not turso_url or not turso_token:
            console.print(
                "[red]Error: Production environment requires TURSO_DATABASE_URL and TURSO_AUTH_TOKEN[/red]"
            )
            raise SystemExit(1)
        existing["DB_ENVIRONMENT"] = "production"
        console.print("Switched to production database environment")
    else:
        existing["DB_ENVIRONMENT"] = "local"
        console.print("Switched to local database environment")

    # Write back .env preserving other keys
    with open(env_file, "w") as f:
        for k, v in existing.items():
            f.write(f"{k}={v}\n")

    load_dotenv(override=True)
    show_db_status()


if __name__ == "__main__":
    db()
