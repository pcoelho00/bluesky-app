#!/usr/bin/env python3
"""Standalone database environment management CLI."""

import click
import os
import sys
from rich.console import Console
from rich.table import Table
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

console = Console()


def get_database_environment() -> str:
    """Get the current database environment."""
    return os.getenv("DB_ENVIRONMENT", "local")


def set_database_environment(environment: str) -> None:
    """Set the database environment in .env file."""
    if environment not in ["local", "production"]:
        raise ValueError("Environment must be either 'local' or 'production'")

    # Read current .env file
    env_file = ".env"
    env_lines = []

    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            env_lines = f.readlines()

    # Update or add DB_ENVIRONMENT
    found = False
    for i, line in enumerate(env_lines):
        if line.strip().startswith("DB_ENVIRONMENT="):
            env_lines[i] = f"DB_ENVIRONMENT={environment}\n"
            found = True
            break

    if not found:
        env_lines.append(f"DB_ENVIRONMENT={environment}\n")

    # Write back to .env file
    with open(env_file, "w") as f:
        f.writelines(env_lines)

    # Update current environment variable
    os.environ["DB_ENVIRONMENT"] = environment


@click.group()
def db():
    """Database environment management commands."""
    pass


@db.command(name="switch")
@click.argument("environment", type=click.Choice(["local", "production"]))
def db_switch(environment):
    """Switch between local and production database environments."""
    try:
        current_env = get_database_environment()

        if current_env == environment:
            console.print(
                f"[yellow]Already using {environment} database environment[/yellow]"
            )
            return

        # Validate production environment has required settings
        if environment == "production":
            turso_url = os.getenv("TURSO_DATABASE_URL")
            turso_token = os.getenv("TURSO_AUTH_TOKEN")

            if not turso_url or not turso_token:
                console.print(
                    "[red]Error: Production environment requires TURSO_DATABASE_URL "
                    "and TURSO_AUTH_TOKEN to be set in your .env file[/red]"
                )
                console.print(
                    "[yellow]Please add these variables to your .env file:[/yellow]"
                )
                console.print("TURSO_DATABASE_URL=libsql://your-database-name.turso.io")
                console.print("TURSO_AUTH_TOKEN=your-turso-auth-token")
                sys.exit(1)

        # Update environment
        set_database_environment(environment)

        # Show confirmation
        db_type = "Turso (Cloud)" if environment == "production" else "SQLite (Local)"
        console.print(
            f"[green]✓ Switched to {environment} database environment ({db_type})[/green]"
        )

        # Show current status
        show_db_status()

    except Exception as e:
        console.print(f"[red]Error switching database environment: {e}[/red]")
        sys.exit(1)


@db.command(name="status")
def db_status():
    """Show current database environment status."""
    show_db_status()


def show_db_status():
    """Helper function to show database status."""
    current_env = get_database_environment()

    table = Table(title="Database Environment Status")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    # Current environment
    env_display = f"{current_env} ({'Turso Cloud' if current_env == 'production' else 'Local SQLite'})"
    table.add_row("Current Environment", env_display)

    # Database details
    if current_env == "production":
        turso_url = os.getenv("TURSO_DATABASE_URL", "❌ Not configured")
        turso_token = (
            "✓ Configured" if os.getenv("TURSO_AUTH_TOKEN") else "❌ Not configured"
        )
        table.add_row("Turso URL", turso_url)
        table.add_row("Turso Token", turso_token)
    else:
        db_path = os.getenv("DATABASE_PATH", "./data/bluesky_feed.db")
        db_exists = "✓ Yes" if os.path.exists(db_path) else "✗ No"
        table.add_row("Database Path", db_path)
        table.add_row("Database Exists", db_exists)

    console.print(table)


if __name__ == "__main__":
    db()
