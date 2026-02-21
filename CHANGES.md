# FileSeq Changelog

## v3.0.0 (TBD)

### Major Changes - ANTLR4 Grammar-Based Parsing

This is a **major version** with breaking changes. FileSeq v3 migrates from regex-based parsing to ANTLR4 grammar-based
parsing, aligning the Python implementation with the Go and C++ implementations for consistency and maintainability.

#### Breaking Changes

**Removed API:**
- `FileSequence.SPLIT_RE` class variable (custom regex pattern override)
- `FileSequence.DISK_RE` class variable (custom disk scanning override)
- `constants.SPLIT_PATTERN`, `constants.SPLIT_RE` (use grammar-based parsing API)
- `constants.SPLIT_SUB_PATTERN`, `constants.SPLIT_SUB_RE` (use grammar-based parsing API)

**Removed Files:**
- `setup.py` (replaced with modern `pyproject.toml`)
- `src/fileseq/__version__.py` (version now managed by `setuptools-scm` from git tags)

**Behavioral Changes:**
- **Auto-padding:** Now only applies to single-frame files without explicit padding
  - `foo.100.exr` → gets auto-padding based on frame width (backward compatible)
  - `foo.1@@@@.exr` → preserves explicit padding (previously would auto-pad)
- **Pattern parsing:** Uses shared ANTLR4 grammar instead of regex
  - More consistent behavior across languages
  - Better error messages for invalid patterns

#### New Features

- **Decimal frame ranges:** Support for decimal step values
  - `foo.1-5x0.25#.exr` → frames 1, 1.25, 1.5, 1.75, 2, 2.25...
  - Single token parsing for better performance

- **Subframe sequences (Python-specific):**
  - Dual range: `foo.1-5#.10-20@@.exr` (main frames + subframes)
  - Composite padding: `foo.1-5@.#.exr` (frame padding + subframe padding)
  - Pattern-only: `foo.#.#.exr` (wildcard for both components)

- **Better hidden file support:**
  - `.bar1000.exr` now correctly parses as basename=`.bar`, frame=`1000`, ext=`.exr`
  - Previously treated `.bar1000` as single extension

- **Cross-platform path handling:**
  - Correctly handles both Unix (`/`) and Windows (`\`) path separators
  - Mixed separators normalized properly

#### Implementation Details

- **Grammar-based parsing:** Shared ANTLR4 grammar (`grammar/fileseq.g4`) with Go and C++ implementations
- **Parser generator:** `src/fileseq/grammar/generate.py` tool for regenerating parser from grammar
- **Build system:** Modern `pyproject.toml` with PEP 517/518 support
- **Version management:** Automatic versioning via `setuptools-scm` from git tags
- **CI/CD:** Grammar validation in CI to ensure consistency across languages
- **Documentation:** Comprehensive migration guide and benchmarks included

#### Performance

Grammar-based parsing provides comparable performance to v2.x regex parsing:
- Simple patterns: ~240 μs per parse
- Complex patterns: ~445 μs per parse
- FrameSet operations: ~13 μs for simple ranges
- Disk scanning: <1 ms for typical directories

#### Migration Guide

**If you were using custom regex patterns:**
```python
# v2.x - REMOVED in v3
class MySequence(FileSequence):
    SPLIT_RE = my_custom_regex  # ❌ No longer supported

# v3 - Use grammar-based API
seq = FileSequence(pattern)  # Grammar handles parsing
```

**If you relied on auto-padding for explicit padding patterns:**
```python
# v2.x behavior
seq = FileSequence("foo.1@@@@.exr")
# Would apply auto-padding, possibly changing @@@@ to # or @@

# v3 behavior
seq = FileSequence("foo.1@@@@.exr")
# Preserves @@@@ as specified (4 chars)
```

---

## v2.3.1 (2025-02-21)

### Bug Fixes
- Strip whitespace from frame range in `FrameSet` constructor (#137)

---

## v2.3.0 (2024-12-24)

### Bug Fixes
- Preserve files with negative zero frames using hyphen format (#144)

### Improvements
- Detect and preserve path separators for cross-platform support (#146)

---

## v2.2.1 (2024-10-27)

### Bug Fixes
- Fix `Decimal` handling in `FrameSet` broken by previous changes (#142)

---

## v2.2.0 (2024-09-21)

### Features
- Add support for `pathlib.Path` via a new `FilePathSequence` class (#140)

### Bug Fixes
- Fix mypy errors and improve annotation accuracy (#141)

---

## v2.1.2 (2024-10-31)

### Bug Fixes
- Fix `yield_sequences_in_list` to use unique keys for single files (#135)

---

## v2.1.1 (2024-04-20)

### Improvements
- Add note to `FileSequence.__str__` regarding format caveat
- Update type annotations for `mypy --strict` compliance
- Remove `typing_extensions` dependency

---

## v2.1.0 (2024-03-26)

### Improvements
- Enhance `FileSequence` equality testing using `FrameSet` (#132)

---

## v2.0.0 (2024-02-20)

### Breaking Changes
- Drop Python 2 support (#119)
- Change default padding behavior when setting ranges (#127)

### Features
- Add Python 3 type annotations and `py.typed` marker (#118)
- Enable `FileSequence.setExtension()` with empty strings (#126)

---

## v1.15.3 (2023-11-04)

### Bug Fixes
- Fix `yield_sequences_in_list` name collision handling (#135)

---

## v1.15.2 (2023-07-25)

### Bug Fixes
- Fix decimal subframes being incorrectly rounded with negative signs (#123)
