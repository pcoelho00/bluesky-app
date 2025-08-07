#!/usr/bin/env python3
"""
Example usage of the Bluesky streaming service.

This script demonstrates how to integrate the streaming service
with periodic summarization for a complete monitoring workflow.

NOTE: Run this script from the parent directory:
    cd /home/pedrocoelho/bluesky-app
    python examples/example_workflow.py
"""

import subprocess
import os


def run_command(cmd: list[str]) -> int:
    """Run a command and return the exit code."""
    print(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 1


def main():
    """Example workflow: stream posts and generate periodic summaries."""
    # Ensure we're in the correct directory
    if not os.path.exists("src/bluesky_summarizer"):
        print("❌ Error: Please run this script from the bluesky-app root directory:")
        print("   cd /home/pedrocoelho/bluesky-app")
        print("   python examples/example_workflow.py")
        return 1

    print("🚀 Bluesky Monitoring Workflow Example")
    print("=" * 50)

    # Example 1: Start streaming with specific users
    print("\n1. Starting streaming service for tech users...")
    print("   (This would run continuously - stopping after a few seconds for demo)")

    cmd = [
        "python",
        "-m",
        "src.bluesky_summarizer.cli",
        "stream",
        "--poll-interval",
        "60",
        "--users",
        "tech.bsky.social",
        "--keywords",
        "ai",
        "--keywords",
        "python",
    ]

    # In a real scenario, you'd run this in the background or in a separate terminal
    print(f"Command: {' '.join(cmd)}")
    print("(In practice, this would run continuously)")

    # Example 2: Generate summary from accumulated data
    print("\n2. Generating summary from recent posts...")
    summary_cmd = [
        "python",
        "-m",
        "src.bluesky_summarizer.cli",
        "summarize",
        "--days",
        "1",
        "--save",
    ]

    exit_code = run_command(summary_cmd)
    if exit_code != 0:
        print("❌ Summary generation failed")
        return exit_code

    # Example 3: Check status
    print("\n3. Checking system status...")
    status_cmd = ["python", "-m", "src.bluesky_summarizer.cli", "status"]
    run_command(status_cmd)

    # Example 4: View recent posts
    print("\n4. Viewing recent posts...")
    posts_cmd = ["python", "-m", "src.bluesky_summarizer.cli", "posts", "--limit", "5"]
    run_command(posts_cmd)

    print("\n✅ Workflow example completed!")
    print("\nNext steps:")
    print("1. Run 'bluesky-summarizer stream' in one terminal")
    print("2. Run periodic summaries in another terminal")
    print("3. Monitor with 'bluesky-summarizer status' and 'bluesky-summarizer posts'")


if __name__ == "__main__":
    main()
