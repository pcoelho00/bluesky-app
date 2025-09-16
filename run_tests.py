#!/usr/bin/env python3
"""
Custom test runner for database environment functionality.
This bypasses pytest collection issues while testing all components.
"""

import os
import sys
import tempfile
import shutil

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Add src to path
sys.path.insert(0, "src")


def run_tests():
    """Run all database environment tests."""
    print("🧪 Running Database Environment Tests")
    print("=" * 50)

    # Test 1: DatabaseConfig functionality
    print("\n📋 Testing DatabaseConfig...")
    try:
        from bluesky_summarizer.config import DatabaseConfig

        # Test local environment
        config = DatabaseConfig(
            db_path="./test.db",
            url="libsql://test.turso.io",
            auth_token="token123",
            environment="local",
        )
        assert not config.is_turso, "Local environment should not be Turso"

        # Test production environment
        config = DatabaseConfig(
            db_path="./test.db",
            url="libsql://test.turso.io",
            auth_token="token123",
            environment="production",
        )
        assert config.is_turso, "Production environment with valid URL should be Turso"

        print("   ✅ DatabaseConfig tests passed")
    except Exception as e:
        print(f"   ❌ DatabaseConfig tests failed: {e}")
        return False

    # Test 2: Environment switching functions
    print("\n🔄 Testing environment switching...")
    try:
        from bluesky_summarizer.config import (
            get_database_environment,
            set_database_environment,
        )

        # Create temporary directory for test
        temp_dir = tempfile.mkdtemp()
        original_cwd = os.getcwd()
        os.chdir(temp_dir)

        try:
            # Test setting and getting environment
            set_database_environment("local")
            assert get_database_environment() == "local", (
                "Should return local environment"
            )

            set_database_environment("production")
            assert get_database_environment() == "production", (
                "Should return production environment"
            )

            # Test .env file creation
            assert os.path.exists(".env"), ".env file should be created"

            with open(".env", "r") as f:
                content = f.read()
            assert "DB_ENVIRONMENT=production" in content, (
                ".env should contain production setting"
            )

            print("   ✅ Environment switching tests passed")
        finally:
            os.chdir(original_cwd)
            shutil.rmtree(temp_dir)
    except Exception as e:
        print(f"   ❌ Environment switching tests failed: {e}")
        return False

    # Test 3: Database factory
    print("\n🏭 Testing database factory...")
    try:
        from bluesky_summarizer.database.factory import create_database_manager
        from bluesky_summarizer.database.operations import DatabaseManager
        from bluesky_summarizer.config import DatabaseConfig

        # Test local database creation
        config = DatabaseConfig(db_path="./test_factory.db", environment="local")

        manager = create_database_manager(config)
        assert isinstance(manager, DatabaseManager), (
            "Should return DatabaseManager for local"
        )

        # Clean up
        if os.path.exists("./test_factory.db"):
            os.unlink("./test_factory.db")

        print("   ✅ Database factory tests passed")
    except Exception as e:
        print(f"   ❌ Database factory tests failed: {e}")
        return False

    # Test 4: CLI functionality (basic import test)
    print("\n🖥️  Testing CLI imports...")
    try:
        # Test that CLI functions can be imported
        import bluesky_summarizer.db_env_cli as db_env_cli

        assert hasattr(db_env_cli, "db_switch"), "CLI should have db_switch function"
        assert hasattr(db_env_cli, "db_status"), "CLI should have db_status function"
        assert hasattr(db_env_cli, "show_db_status"), (
            "CLI should have show_db_status function"
        )

        print("   ✅ CLI import tests passed")
    except Exception as e:
        print(f"   ❌ CLI import tests failed: {e}")
        return False

    # Test 5: Integration test
    print("\n🔗 Testing integration...")
    try:
        temp_dir = tempfile.mkdtemp()
        original_cwd = os.getcwd()
        os.chdir(temp_dir)

        try:
            # Create .env file with all settings
            with open(".env", "w") as f:
                f.write("""
BLUESKY_HANDLE=test.bsky.social
BLUESKY_PASSWORD=test_password
ANTHROPIC_API_KEY=test_api_key
DB_ENVIRONMENT=local
DATABASE_PATH=./test.db
TURSO_DATABASE_URL=libsql://test.turso.io
TURSO_AUTH_TOKEN=test_token
""")

            # Test environment switching
            from bluesky_summarizer.config import set_database_environment, get_config

            set_database_environment("local")
            config = get_config()
            assert config.database.environment == "local"
            assert not config.database.is_turso

            set_database_environment("production")
            config = get_config()
            assert config.database.environment == "production"
            assert config.database.is_turso

            print("   ✅ Integration tests passed")
        finally:
            os.chdir(original_cwd)
            shutil.rmtree(temp_dir)
    except Exception as e:
        print(f"   ❌ Integration tests failed: {e}")
        return False

    print("\n🎉 All tests passed!")
    print("\n📝 Test Summary:")
    print("   ✅ DatabaseConfig functionality")
    print("   ✅ Environment switching functions")
    print("   ✅ Database factory")
    print("   ✅ CLI imports")
    print("   ✅ Integration tests")

    return True


def run_cli_demo():
    """Run a demo of the CLI functionality."""
    print("\n" + "=" * 50)
    print("🖥️  CLI Demo")
    print("=" * 50)

    print("\n📋 Available CLI Commands:")
    print("   python db_env_cli.py status")
    print("   python db_env_cli.py switch local")
    print("   python db_env_cli.py switch production")

    print("\n🔧 Current Environment:")
    try:
        import subprocess

        result = subprocess.run(
            ["python", "db_env_cli.py", "status"],
            capture_output=True,
            text=True,
            cwd=".",
        )
        if result.returncode == 0:
            print(result.stdout)
        else:
            print(f"   ❌ Error running CLI: {result.stderr}")
    except Exception as e:
        print(f"   ❌ Could not run CLI demo: {e}")


if __name__ == "__main__":
    success = run_tests()

    if success:
        run_cli_demo()

        print("\n" + "=" * 50)
        print("🚀 Ready to use!")
        print("=" * 50)
        print("\nUse these commands to manage your database environment:")
        print("   python db_env_cli.py status        # Check current environment")
        print("   python db_env_cli.py switch local  # Use local SQLite")
        print("   python db_env_cli.py switch production  # Use Turso cloud")
    else:
        print("\n❌ Some tests failed. Please check the implementation.")
        sys.exit(1)
