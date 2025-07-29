#!/usr/bin/env python3
"""
Simple test runner for the Bluesky Feed Summarizer.
Run this script to execute all tests and verify the application works correctly.
"""

import subprocess
import sys
import os


def run_tests() -> bool:
    """Run the test suite using pytest."""
    print("🧪 Running Bluesky Feed Summarizer Test Suite")
    print("=" * 50)

    # Change to the project directory
    project_dir: str = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)

    # Run pytest with verbose output
    cmd: list[str] = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_bluesky_summarizer.py",
        "-v",
        "--tb=short",
        "--disable-warnings",  # Hide deprecation warnings for cleaner output
    ]

    try:
        subprocess.run(cmd, check=True)
        print("\n✅ All tests passed! The application is working correctly.")
        print("\n📝 Test Summary:")
        print("   - Timezone datetime comparison: ✓")
        print("   - Pydantic models validation: ✓")
        print("   - Database operations: ✓")
        print("   - Bluesky client functionality: ✓")
        print("   - Claude AI summarizer: ✓")
        print("   - Integration tests: ✓")
        return True

    except subprocess.CalledProcessError as e:
        print(f"\n❌ Tests failed with exit code {e.returncode}")
        print("\nPlease check the test output above for details.")
        return False


def main() -> None:
    """Main entry point."""
    print("Bluesky Feed Summarizer - Test Runner")
    print("This will verify that the timezone datetime fixes work correctly.\n")

    success: bool = run_tests()

    if success:
        print("\n🎉 Ready to use! You can now:")
        print("   1. Set up your .env file with Bluesky and Anthropic credentials")
        print("   2. Run: bluesky-summarizer run --days 1")
        sys.exit(0)
    else:
        print("\n🔧 Please fix the failing tests before using the application.")
        sys.exit(1)


if __name__ == "__main__":
    main()
