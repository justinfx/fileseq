#!/usr/bin/env python
"""Generate ANTLR4 parser for Python from grammar file."""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
GRAMMAR_DIR = ROOT / "src" / "fileseq" / "grammar"
OUTPUT_DIR = ROOT / "src" / "fileseq" / "parser"
ANTLR_JAR = ROOT / "tools" / "antlr-4.13.1-complete.jar"
GRAMMAR_FILE = "fileseq.g4"

# Candidate java binary locations, checked in order before falling back to PATH.
_JAVA_CANDIDATES = [
    # Homebrew (macOS)
    "/opt/homebrew/opt/openjdk/bin/java",
    "/opt/homebrew/opt/openjdk@21/bin/java",
    "/opt/homebrew/opt/openjdk@17/bin/java",
    "/opt/homebrew/opt/openjdk@11/bin/java",
    # Linux
    "/usr/lib/jvm/java-21-openjdk/bin/java",
    "/usr/lib/jvm/java-21-openjdk-amd64/bin/java",
    "/usr/lib/jvm/java-17-openjdk/bin/java",
    "/usr/lib/jvm/java-11-openjdk/bin/java",
]

# macOS JVMs installed via the official installer live here
_MACOS_JVM_DIR = Path("/Library/Java/JavaVirtualMachines")

GENERATED_FILES = [
    "fileseqLexer.py",
    "fileseqParser.py",
    "fileseqListener.py",
    "fileseqVisitor.py",
]
_ANTLR_IMPORT_RE = re.compile(r'^from antlr4 import \*', re.MULTILINE)
_VENDORED_IMPORT = 'from fileseq._vendor.antlr4 import *'


def _find_java() -> str:
    """Return a usable java binary, probing known locations before PATH."""
    candidates = list(_JAVA_CANDIDATES)
    if _MACOS_JVM_DIR.is_dir():
        for jvm in sorted(_MACOS_JVM_DIR.iterdir(), reverse=True):
            candidates.append(str(jvm / "Contents/Home/bin/java"))

    for candidate in candidates:
        p = Path(candidate)
        if p.is_file() and p.stat().st_mode & 0o111:
            return str(p)
    return "java"


def rewrite_generated_imports(output_dir: Path) -> None:
    """Rewrite ANTLR-generated imports to use the vendored antlr4 copy."""
    for filename in GENERATED_FILES:
        path = output_dir / filename
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        new_text = _ANTLR_IMPORT_RE.sub(_VENDORED_IMPORT, text)
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            print(f"  Rewrote imports in {filename}")


def main() -> int:
    """Generate parser from grammar file."""
    for label, path in [
        ("ANTLR JAR", ANTLR_JAR),
        ("Grammar directory", GRAMMAR_DIR),
        ("Grammar file", GRAMMAR_DIR / GRAMMAR_FILE),
    ]:
        if not path.exists():
            print(f"Error: {label} not found: {path}", file=sys.stderr)
            return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    java = _find_java()
    cmd = [java, "-jar", str(ANTLR_JAR), "-Dlanguage=Python3", "-visitor",
           "-o", str(OUTPUT_DIR), GRAMMAR_FILE]

    print(f"Generating Python parser from {GRAMMAR_FILE}...")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Using Java: {java}")

    try:
        result = subprocess.run(cmd, cwd=str(GRAMMAR_DIR))
    except FileNotFoundError:
        print("\n✗ Error: Java not found.", file=sys.stderr)
        print("Install Java 11+ and ensure it is on your PATH, or install via:", file=sys.stderr)
        print("  macOS:  brew install openjdk@21", file=sys.stderr)
        print("  Linux:  apt install openjdk-21-jdk  (or equivalent)", file=sys.stderr)
        return 1

    if result.returncode == 0:
        print(f"✓ Parser generated successfully in {OUTPUT_DIR}")
        rewrite_generated_imports(OUTPUT_DIR)
    else:
        print(f"✗ Parser generation failed with exit code {result.returncode}", file=sys.stderr)

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
