#!/usr/bin/env python
"""Generate ANTLR4 parser for Python from grammar file."""
import os
import subprocess
import sys
from pathlib import Path

# Project root (this file is in src/fileseq/grammar/)
ROOT = Path(__file__).parent.parent.parent.parent
GRAMMAR_DIR = Path(__file__).parent  # Current directory
OUTPUT_DIR = GRAMMAR_DIR.parent / "parser"  # ../parser
ANTLR_JAR = ROOT / "tools" / "antlr-4.13.1-complete.jar"
GRAMMAR_FILE = "fileseq.g4"

def main():
    """Generate parser from grammar file."""
    if not ANTLR_JAR.exists():
        print(f"Error: ANTLR JAR not found: {ANTLR_JAR}", file=sys.stderr)
        return 1

    if not GRAMMAR_DIR.exists():
        print(f"Error: Grammar directory not found: {GRAMMAR_DIR}", file=sys.stderr)
        return 1

    if not (GRAMMAR_DIR / GRAMMAR_FILE).exists():
        print(f"Error: Grammar file not found: {GRAMMAR_DIR / GRAMMAR_FILE}", file=sys.stderr)
        return 1

    # Create output directory if needed
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Run ANTLR from grammar directory to avoid nested paths
    cmd = [
        "java",
        "-jar", str(ANTLR_JAR),
        "-Dlanguage=Python3",
        "-visitor",
        "-o", str(OUTPUT_DIR),
        GRAMMAR_FILE
    ]

    print(f"Generating Python parser from {GRAMMAR_FILE}...")
    print(f"Output directory: {OUTPUT_DIR}")

    try:
        result = subprocess.run(cmd, cwd=str(GRAMMAR_DIR))
    except FileNotFoundError:
        print("\n✗ Error: Java not found in PATH", file=sys.stderr)
        print("\nTo fix this:", file=sys.stderr)
        print("  macOS:   export PATH=\"/opt/homebrew/opt/openjdk@21/bin:$PATH\"", file=sys.stderr)
        print("  Linux:   export PATH=\"/usr/lib/jvm/java-21-openjdk/bin:$PATH\"", file=sys.stderr)
        print("  Windows: Add Java bin directory to System PATH", file=sys.stderr)
        return 1

    if result.returncode == 0:
        print(f"✓ Parser generated successfully in {OUTPUT_DIR}")
    else:
        print(f"✗ Parser generation failed with exit code {result.returncode}", file=sys.stderr)

    return result.returncode

if __name__ == "__main__":
    sys.exit(main())
