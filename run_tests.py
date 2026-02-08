#!/usr/bin/env python3
"""Test runner script for LLM-MD-CLI."""

import subprocess
import sys
from pathlib import Path

def run_tests(test_path="tests/unit", verbose=True, coverage=False):
    """Run pytest with configured options."""
    cmd = ["python", "-m", "pytest", test_path]
    
    if verbose:
        cmd.append("-v")
    
    if coverage:
        cmd.extend(["--cov=cli", "--cov=backend", "--cov-report=term-missing"])
    
    print(f"Running: {' '.join(cmd)}")
    print("=" * 60)
    
    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    return result.returncode

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run LLM-MD-CLI tests")
    parser.add_argument(
        "--path", "-p",
        default="tests/unit",
        help="Test path to run (default: tests/unit)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=True,
        help="Verbose output"
    )
    parser.add_argument(
        "--coverage", "-c",
        action="store_true",
        help="Generate coverage report"
    )
    parser.add_argument(
        "--integration",
        action="store_true",
        help="Run integration tests (requires running backend)"
    )
    
    args = parser.parse_args()
    
    if args.integration:
        test_path = "tests/integration"
        print("⚠️  Running integration tests - make sure backend is running!")
    else:
        test_path = args.path
    
    return run_tests(test_path, args.verbose, args.coverage)

if __name__ == "__main__":
    sys.exit(main())
