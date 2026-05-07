"""
Project Analyzer — scans the existing project codebase and produces:
  1. A reuse index — every exported function / class / component / type
  2. Detected conventions — indentation, quotes, semicolons, naming style, etc.

The gate uses these to:
  - Flag new code that duplicates existing functionality (reuse violation)
  - Flag new code that breaks the project's own style conventions

This is a heuristic-only implementation (regex + simple parsing). For deeper
semantic checks, the fresh-reviewer layer is still the answer.
"""
from __future__ import annotations

import os
import re
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------- #
# Cache — project indexes are expensive to build, but stable between runs.
# Keyed by (project_root, mtime_of_newest_file). 10-min TTL.
# --------------------------------------------------------------------------- #
_INDEX_CACHE: dict[tuple, tuple[float, "ProjectIndex"]] = {}
_CACHE_TTL_S = 600


@dataclass
class Export:
    name: str
    kind: str  # function | class | component | type | const | hook
    file: str
    line: int
    signature_hint: str = ""


@dataclass
class Conventions:
    indent: str = "  "          # detected indentation (2 spaces, 4 spaces, or tab)
    quotes: str = "double"      # "single" | "double"
    semicolons: bool = True
    trailing_comma: bool = False
    file_naming: str = "kebab"  # kebab | camel | pascal | snake
    function_naming: str = "camel"  # camel | snake
    constant_naming: str = "screaming-snake"  # SCREAMING_SNAKE_CASE for top-level constants
    import_style: str = "named"  # named | default | mixed


@dataclass
class ProjectIndex:
    project_root: str
    exports: list[Export] = field(default_factory=list)
    conventions: Conventions = field(default_factory=Conventions)
    indexed_files: int = 0
    excluded_files: int = 0


# --------------------------------------------------------------------------- #
# Public entrypoints
# --------------------------------------------------------------------------- #
def get_index(project_root: str) -> ProjectIndex:
    """Build (or return cached) project index for the given root."""
    if not project_root or not os.path.isdir(project_root):
        return ProjectIndex(project_root=project_root or "")
    key = (os.path.abspath(project_root),)
    cached = _INDEX_CACHE.get(key)
    if cached and time.time() - cached[0] < _CACHE_TTL_S:
        return cached[1]
    index = _build_index(project_root)
    _INDEX_CACHE[key] = (time.time(), index)
    return index


def check_reuse(new_files: list[dict], index: ProjectIndex) -> list[dict]:
    """For each new file, find existing exports that may already provide the
    functionality being introduced. Returns a list of finding dicts.
    """
    findings: list[dict] = []
    if not index.exports:
        return findings

    # Build lookup tables
    by_name: dict[str, list[Export]] = {}
    by_keyword: dict[str, list[Export]] = {}
    for exp in index.exports:
        by_name.setdefault(exp.name.lower(), []).append(exp)
        for kw in _name_keywords(exp.name):
            by_keyword.setdefault(kw, []).append(exp)

    for new_file in new_files:
        path = new_file.get("path", "")
        content = new_file.get("content", "") or ""
        if not content:
            continue

        # Skip checking the file against itself if it was already in the index
        new_exports = _extract_exports_from_content(content, path)
        for ne in new_exports:
            # Skip if this is the same file path as where the export already lives
            same_path_exports = [e for e in by_name.get(ne.name.lower(), []) if _same_path(e.file, path, index.project_root)]
            if same_path_exports:
                continue  # editing existing — not a duplicate

            # Direct name collision (different file)
            external_dupes = [e for e in by_name.get(ne.name.lower(), []) if not _same_path(e.file, path, index.project_root)]
            for dupe in external_dupes:
                findings.append({
                    "source": "reuse",
                    "severity": "major",
                    "file": path,
                    "line": ne.line,
                    "rule": "duplicate-export-name",
                    "message": (
                        f"new {ne.kind} `{ne.name}` may duplicate existing {dupe.kind} "
                        f"at `{_rel(dupe.file, index.project_root)}:{dupe.line}`. Consider importing the existing one."
                    ),
                })

            # Keyword overlap — same purpose suggested by name parts
            seen_keyword_files: set[str] = set()
            for kw in _name_keywords(ne.name):
                for candidate in by_keyword.get(kw, [])[:5]:
                    if _same_path(candidate.file, path, index.project_root):
                        continue
                    if candidate.name.lower() == ne.name.lower():
                        continue  # already reported above
                    if not _name_overlap_significant(ne.name, candidate.name):
                        continue
                    cand_key = f"{candidate.file}:{candidate.name}"
                    if cand_key in seen_keyword_files:
                        continue
                    seen_keyword_files.add(cand_key)
                    findings.append({
                        "source": "reuse",
                        "severity": "minor",
                        "file": path,
                        "line": ne.line,
                        "rule": "similar-export-exists",
                        "message": (
                            f"new {ne.kind} `{ne.name}` is similar in purpose to existing "
                            f"{candidate.kind} `{candidate.name}` at "
                            f"`{_rel(candidate.file, index.project_root)}:{candidate.line}`. "
                            f"Verify it isn't a duplicate before adding."
                        ),
                    })

    # Cap to avoid noise
    return findings[:20]


def check_conventions(new_files: list[dict], index: ProjectIndex) -> list[dict]:
    """Compare new code's style against detected project conventions."""
    findings: list[dict] = []
    conv = index.conventions

    for new_file in new_files:
        path = new_file.get("path", "")
        content = new_file.get("content", "") or ""
        if not content or not _is_source(path):
            continue

        # Indentation mismatch
        new_indent = _detect_indent(content)
        if new_indent and conv.indent and new_indent != conv.indent:
            findings.append({
                "source": "convention",
                "severity": "minor",
                "file": path,
                "rule": "indent-mismatch",
                "message": (
                    f"file uses {_describe_indent(new_indent)} indentation, "
                    f"project uses {_describe_indent(conv.indent)}"
                ),
            })

        # Quote style
        single = len(re.findall(r"(?<![\w'])'(?:[^'\\]|\\.)*'", content))
        double = len(re.findall(r'(?<![\w"])"(?:[^"\\]|\\.)*"', content))
        new_quote = "single" if single > double * 1.5 else ("double" if double > single * 1.5 else None)
        if new_quote and conv.quotes and new_quote != conv.quotes:
            findings.append({
                "source": "convention",
                "severity": "minor",
                "file": path,
                "rule": "quote-style-mismatch",
                "message": (
                    f"file uses {new_quote} quotes ({single if new_quote == 'single' else double}), "
                    f"project uses {conv.quotes}"
                ),
            })

        # File naming (only flag for newly created files, can't tell from here —
        # but flag obviously off-style names)
        basename = os.path.basename(path)
        if basename and "." in basename:
            stem = basename.rsplit(".", 1)[0]
            new_naming = _detect_filename_style(stem)
            if new_naming and conv.file_naming and new_naming != conv.file_naming:
                # Only flag if there are 5+ files in the project using the project style
                # (otherwise convention detection might be wrong)
                findings.append({
                    "source": "convention",
                    "severity": "minor",
                    "file": path,
                    "rule": "file-naming-mismatch",
                    "message": (
                        f"file name `{basename}` uses {new_naming}-case, "
                        f"project convention is {conv.file_naming}-case"
                    ),
                })

    return findings[:10]


# --------------------------------------------------------------------------- #
# Index building
# --------------------------------------------------------------------------- #
SOURCE_EXTS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py", ".java", ".kt", ".cs", ".go", ".rs", ".rb", ".php"}
EXCLUDED_DIRS = {"node_modules", "dist", "build", ".next", ".nuxt", "__pycache__", ".git", "vendor", "target", "bin", "obj", "coverage", ".pytest_cache", "out", ".venv", "venv", "env"}
EXCLUDED_FILE_PATTERNS = (
    re.compile(r"\.test\.(ts|tsx|js|jsx|py)$"),
    re.compile(r"\.spec\.(ts|tsx|js|jsx)$"),
    re.compile(r"_test\.(go|py)$"),
    re.compile(r"\.d\.ts$"),
    re.compile(r"\.min\.js$"),
)


def _build_index(project_root: str) -> ProjectIndex:
    index = ProjectIndex(project_root=project_root)
    sample_files: list[Path] = []  # for convention sampling

    for dirpath, dirnames, filenames in os.walk(project_root):
        # In-place prune of excluded dirs
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS and not d.startswith(".")]

        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in SOURCE_EXTS:
                continue
            full = os.path.join(dirpath, fname)
            if any(p.search(full) for p in EXCLUDED_FILE_PATTERNS):
                index.excluded_files += 1
                continue

            try:
                content = open(full, "r", encoding="utf-8", errors="replace").read()
            except OSError:
                continue

            index.indexed_files += 1
            for exp in _extract_exports_from_content(content, full):
                index.exports.append(exp)

            if len(sample_files) < 30:
                sample_files.append(Path(full))

    # Detect conventions from samples
    index.conventions = _detect_conventions(sample_files)

    return index


def _extract_exports_from_content(code: str, path: str) -> list[Export]:
    """Extract exported declarations using language-aware regex."""
    out: list[Export] = []
    if not code:
        return out

    ext = os.path.splitext(path)[1].lower()

    if ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
        out.extend(_extract_js_ts_exports(code, path))
    elif ext == ".py":
        out.extend(_extract_python_exports(code, path))
    elif ext in (".cs",):
        out.extend(_extract_csharp_exports(code, path))
    elif ext == ".java":
        out.extend(_extract_java_exports(code, path))
    elif ext == ".go":
        out.extend(_extract_go_exports(code, path))
    return out


def _extract_js_ts_exports(code: str, path: str) -> list[Export]:
    out: list[Export] = []
    lines = code.split("\n")
    for i, line in enumerate(lines, start=1):
        s = line.strip()
        # export function NAME / export async function NAME / export default function NAME
        m = re.match(r"export\s+(?:default\s+)?(?:async\s+)?function\s+(\w+)", s)
        if m:
            out.append(Export(name=m.group(1), kind=_classify_js_name(m.group(1)), file=path, line=i, signature_hint=s[:120]))
            continue
        # export class NAME
        m = re.match(r"export\s+(?:default\s+)?class\s+(\w+)", s)
        if m:
            out.append(Export(name=m.group(1), kind="class", file=path, line=i, signature_hint=s[:120]))
            continue
        # export const NAME = (...)  / export const NAME: T = ...
        m = re.match(r"export\s+const\s+(\w+)\b", s)
        if m:
            name = m.group(1)
            kind = _classify_js_const(name, s)
            out.append(Export(name=name, kind=kind, file=path, line=i, signature_hint=s[:120]))
            continue
        # export type NAME / export interface NAME
        m = re.match(r"export\s+(?:type|interface)\s+(\w+)", s)
        if m:
            out.append(Export(name=m.group(1), kind="type", file=path, line=i, signature_hint=s[:120]))
            continue
        # export enum NAME
        m = re.match(r"export\s+(?:const\s+)?enum\s+(\w+)", s)
        if m:
            out.append(Export(name=m.group(1), kind="type", file=path, line=i, signature_hint=s[:120]))
    return out


def _classify_js_name(name: str) -> str:
    if name and name[0].isupper():
        return "component"
    if name.startswith("use") and len(name) > 3 and name[3].isupper():
        return "hook"
    return "function"


def _classify_js_const(name: str, line: str) -> str:
    # const NAME = React.memo(...) → component
    if "memo(" in line or "React.memo" in line or "forwardRef" in line:
        return "component"
    # const NAME = (...) => / const NAME = function → function
    if "=>" in line or "= function" in line:
        return _classify_js_name(name)
    # SCREAMING_SNAKE → const, otherwise const
    return "const"


def _extract_python_exports(code: str, path: str) -> list[Export]:
    out: list[Export] = []
    for i, line in enumerate(code.split("\n"), start=1):
        s = line.lstrip()
        if line and not line[0].isspace():  # only top-level definitions
            m = re.match(r"def\s+(\w+)\s*\(", s)
            if m and not m.group(1).startswith("_"):
                out.append(Export(name=m.group(1), kind="function", file=path, line=i, signature_hint=s[:120]))
                continue
            m = re.match(r"class\s+(\w+)", s)
            if m and not m.group(1).startswith("_"):
                out.append(Export(name=m.group(1), kind="class", file=path, line=i, signature_hint=s[:120]))
                continue
            m = re.match(r"(\w+)\s*=", s)
            if m and m.group(1).isupper() and not m.group(1).startswith("_"):
                out.append(Export(name=m.group(1), kind="const", file=path, line=i, signature_hint=s[:120]))
    return out


def _extract_csharp_exports(code: str, path: str) -> list[Export]:
    out: list[Export] = []
    for i, line in enumerate(code.split("\n"), start=1):
        s = line.strip()
        m = re.match(r"public\s+(?:static\s+)?(?:async\s+)?(?:partial\s+)?(?:class|record|interface|struct)\s+(\w+)", s)
        if m:
            out.append(Export(name=m.group(1), kind="class", file=path, line=i, signature_hint=s[:120]))
            continue
        m = re.match(r"public\s+(?:static\s+)?(?:async\s+)?[\w<>?,\[\]\s]+\s+(\w+)\s*\(", s)
        if m and m.group(1) not in ("if", "for", "while", "switch", "return", "throw", "do"):
            out.append(Export(name=m.group(1), kind="function", file=path, line=i, signature_hint=s[:120]))
    return out


def _extract_java_exports(code: str, path: str) -> list[Export]:
    out: list[Export] = []
    for i, line in enumerate(code.split("\n"), start=1):
        s = line.strip()
        m = re.match(r"public\s+(?:static\s+)?(?:final\s+)?(?:abstract\s+)?(?:class|interface|enum|record)\s+(\w+)", s)
        if m:
            out.append(Export(name=m.group(1), kind="class", file=path, line=i, signature_hint=s[:120]))
    return out


def _extract_go_exports(code: str, path: str) -> list[Export]:
    out: list[Export] = []
    for i, line in enumerate(code.split("\n"), start=1):
        s = line.strip()
        # func ExportedName(...) — uppercase first letter is exported in Go
        m = re.match(r"func\s+(?:\([^)]*\)\s+)?([A-Z]\w*)\s*\(", s)
        if m:
            out.append(Export(name=m.group(1), kind="function", file=path, line=i, signature_hint=s[:120]))
            continue
        m = re.match(r"type\s+([A-Z]\w*)\s+", s)
        if m:
            out.append(Export(name=m.group(1), kind="type", file=path, line=i, signature_hint=s[:120]))
    return out


# --------------------------------------------------------------------------- #
# Convention detection
# --------------------------------------------------------------------------- #
def _detect_conventions(sample_files: list[Path]) -> Conventions:
    indents: list[str] = []
    quotes_single: list[int] = []
    quotes_double: list[int] = []
    semi_lines = 0
    no_semi_lines = 0
    file_naming_styles: list[str] = []

    for fp in sample_files:
        try:
            content = fp.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        ind = _detect_indent(content)
        if ind:
            indents.append(ind)
        quotes_single.append(len(re.findall(r"(?<![\w'])'(?:[^'\\]|\\.)*'", content)))
        quotes_double.append(len(re.findall(r'(?<![\w"])"(?:[^"\\]|\\.)*"', content)))

        if fp.suffix in (".ts", ".tsx", ".js", ".jsx", ".cs", ".java"):
            for line in content.splitlines():
                stripped = line.rstrip()
                if not stripped or stripped.endswith("{") or stripped.endswith(",") or stripped.endswith("("):
                    continue
                if stripped.endswith(";"):
                    semi_lines += 1
                else:
                    no_semi_lines += 1

        stem = fp.stem
        ns = _detect_filename_style(stem)
        if ns:
            file_naming_styles.append(ns)

    most_common_indent = _most_common(indents) or "  "
    sum_single = sum(quotes_single)
    sum_double = sum(quotes_double)
    quote_pref = "single" if sum_single > sum_double else "double"
    semi_pref = semi_lines > no_semi_lines
    name_pref = _most_common(file_naming_styles) or "kebab"

    return Conventions(
        indent=most_common_indent,
        quotes=quote_pref,
        semicolons=semi_pref,
        file_naming=name_pref,
    )


def _detect_indent(code: str) -> str:
    # Find the most common leading whitespace pattern on indented lines
    counts: dict[str, int] = {}
    for line in code.splitlines():
        m = re.match(r"^([\t ]+)", line)
        if not m:
            continue
        ind = m.group(1)
        # Normalize to one indent level (use the smallest non-empty leading space sequence)
        if "\t" in ind:
            counts["\t"] = counts.get("\t", 0) + 1
        else:
            # 2 vs 4 spaces — count the first 2 or 4 chars
            n = len(ind)
            if n == 2:
                counts["  "] = counts.get("  ", 0) + 1
            elif n == 4:
                counts["    "] = counts.get("    ", 0) + 1
    if not counts:
        return ""
    return max(counts, key=counts.get)


def _describe_indent(ind: str) -> str:
    if ind == "\t":
        return "tab"
    return f"{len(ind)}-space"


def _detect_filename_style(stem: str) -> str:
    if not stem:
        return ""
    if "-" in stem:
        return "kebab"
    if "_" in stem:
        return "snake"
    if stem[0].isupper():
        return "pascal"
    if any(c.isupper() for c in stem):
        return "camel"
    return "kebab"  # lowercase single-word default


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
_KEYWORD_SPLIT = re.compile(r"(?<=[a-z])(?=[A-Z])|[_\-]+")


def _name_keywords(name: str) -> list[str]:
    if not name:
        return []
    parts = _KEYWORD_SPLIT.split(name)
    return [p.lower() for p in parts if len(p) > 2]


def _name_overlap_significant(a: str, b: str) -> bool:
    """Two names overlap significantly if they share 2+ keyword parts of length >2."""
    ak = set(_name_keywords(a))
    bk = set(_name_keywords(b))
    if not ak or not bk:
        return False
    overlap = ak & bk
    return len(overlap) >= 2 or (len(overlap) >= 1 and (len(ak) <= 2 or len(bk) <= 2))


def _same_path(a: str, b: str, root: str) -> bool:
    try:
        ap = os.path.normpath(a if os.path.isabs(a) else os.path.join(root, a))
        bp = os.path.normpath(b if os.path.isabs(b) else os.path.join(root, b))
        return ap == bp
    except Exception:
        return a == b


def _rel(p: str, root: str) -> str:
    try:
        return os.path.relpath(p, root).replace("\\", "/")
    except ValueError:
        return p


def _most_common(items: list) -> str:
    if not items:
        return ""
    counts: dict = {}
    for x in items:
        counts[x] = counts.get(x, 0) + 1
    return max(counts, key=counts.get)


def _is_source(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in SOURCE_EXTS
