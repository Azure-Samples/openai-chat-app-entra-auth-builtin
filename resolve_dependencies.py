#!/usr/bin/env python3
"""
Regenerate requirements files to ensure compatibility.
This script demonstrates the proper way to resolve dependency conflicts
similar to what Dependabot PR #86 might have encountered.
"""

import subprocess
import sys
import os


def regenerate_requirements():
    """Regenerate requirements files with pip-compile."""

    print("Regenerating requirements files...")

    # Define the files to regenerate
    files_to_regenerate = [
        {
            "input": "src/pyproject.toml",
            "output": "src/requirements.txt",
            "description": "Main application requirements",
        },
        {
            "input": "scripts/requirements.in",
            "output": "scripts/requirements.txt",
            "description": "Scripts requirements",
        },
    ]

    for file_info in files_to_regenerate:
        input_file = file_info["input"]
        output_file = file_info["output"]
        description = file_info["description"]

        print(f"\nRegenerating {description} ({output_file})...")

        if not os.path.exists(input_file):
            print(f"Warning: Input file {input_file} not found, skipping...")
            continue

        try:
            # Use pip-compile to regenerate requirements
            cmd = [sys.executable, "-m", "piptools", "compile", "--output-file", output_file, input_file]

            print(f"Running: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                print(f"✓ Successfully regenerated {output_file}")
                if result.stdout:
                    print("  Output:", result.stdout[:200] + "..." if len(result.stdout) > 200 else result.stdout)
            else:
                print(f"✗ Failed to regenerate {output_file}")
                if result.stderr:
                    print("  Error:", result.stderr[:500])

        except subprocess.TimeoutExpired:
            print(f"✗ Timeout while regenerating {output_file}")
        except Exception as e:
            print(f"✗ Error regenerating {output_file}: {e}")


def verify_requirements():
    """Verify that requirements can be installed."""
    print("\nVerifying requirements...")

    # Check that key requirements files exist
    req_files = ["src/requirements.txt", "requirements-dev.txt"]

    for req_file in req_files:
        if os.path.exists(req_file):
            print(f"✓ Found {req_file}")
        else:
            print(f"✗ Missing {req_file}")


if __name__ == "__main__":
    print("Dependency Conflict Resolution Script")
    print("=====================================")
    print()
    print("This script demonstrates how to resolve dependency conflicts")
    print("by regenerating requirements files with compatible versions.")
    print()

    regenerate_requirements()
    verify_requirements()

    print("\nNext steps:")
    print("1. Test the updated requirements in a fresh virtual environment")
    print("2. Run the test suite to ensure compatibility")
    print("3. Update the PR with the resolved dependencies")
