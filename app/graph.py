"""Static, bounded repository graph analysis. No code is executed."""

from __future__ import annotations

from collections import Counter, defaultdict
from .intelligence import describe_module
from pathlib import PurePosixPath
import posixpath
import re

MAX_NODES = 72
MAX_FILES = 12_000
MAX_ANALYZED_SOURCES = 22
MAX_SOURCE_BYTES = 85_000

SKIP_SEGMENTS = {
    ".git", ".github", ".next", ".nuxt", ".venv", "venv", "node_modules",
    "vendor", "dist", "build", "coverage", "target", "out", "__pycache__",
    ".turbo", ".cache", "fixtures", "snapshots", "__snapshots__", "public",
}
SOURCE_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py", ".go", ".rs", ".java", ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".rb", ".php", ".kt", ".swift", ".v", ".sv", ".svh", ".vhd", ".vhdl", ".s", ".asm", ".sh", ".sql"}
SOURCE_TEXT_PATTERN = re.compile(r"(?:\bfrom\s+|\brequire\s*\(|\bimport\s*\(\s*)['\"]([^'\"]+)['\"]")
JS_BARE_IMPORT = re.compile(r"\bimport\s*['\"]([^'\"]+)['\"]")
PY_FROM_IMPORT = re.compile(r"(?m)^\s*from\s+([\w.]+)\s+import\b")
PY_IMPORT = re.compile(r"(?m)^\s*import\s+([\w.]+)")
PY_DECL = re.compile(r"(?m)^\s*(?:async\s+)?(def|class)\s+([A-Za-z_][A-Za-z_0-9]*)\s*[(:]")
JS_DECL = re.compile(r"\b(?:export\s+(?:default\s+)?)?(?:async\s+)?(function|class)\s+([A-Za-z_$][\w$]*)\s*[({]")
JS_EXPORT = re.compile(r"\bexport\s+(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=")
JS_ARROW = re.compile(r"\b(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]{0,120}\)|[A-Za-z_$][\w$]*)\s*=>")


def extract_symbols(content: str, origin: str) -> list[dict]:
    """Approximate declaration-name extraction from the bounded source sample."""
    if not isinstance(content, str) or len(content) > MAX_SOURCE_BYTES:
        return []
    suffix=PurePosixPath(origin).suffix
    matches=[]
    if suffix == '.py':
        matches=[(m.group(2),m.group(1)) for m in PY_DECL.finditer(content)]
    elif suffix in {'.js','.jsx','.ts','.tsx','.mjs','.cjs'}:
        matches=[(m.group(2),m.group(1)) for m in JS_DECL.finditer(content)]
        matches += [(m.group(1),'export') for m in JS_EXPORT.finditer(content)]
        matches += [(m.group(1),'arrow') for m in JS_ARROW.finditer(content)]
    found=[];seen=set()
    for name,kind in matches:
        if name not in seen and len(name) <= 90:
            seen.add(name);found.append({'name':name,'file':origin,'kind':kind})
        if len(found)>=20:break
    return found


def clean_path(path: str) -> str | None:
    if not isinstance(path, str) or len(path) > 450 or "\\" in path or "\x00" in path:
        return None
    parts = path.split("/")
    if not parts or any(p in {"", ".", ".."} for p in parts):
        return None
    if any(p in SKIP_SEGMENTS or p.startswith(".env") for p in parts):
        return None
    return path


def group_for_file(path: str) -> str:
    parts = path.split("/")[:-1]
    if not parts:
        return "root"
    if len(parts) == 1:
        return parts[0]
    if parts[0] in {"apps", "packages", "services", "infra", "data", "tests", "docs", "tools"}:
        base = parts[:2]
        if len(parts) >= 3 and parts[2] in {"components", "hooks", "features", "routes", "api", "lib"}:
            base.append(parts[2])
        return "/".join(base)
    if parts[0] in {"src", "app", "lib", "server", "client", "frontend", "backend", "test", "internal", "cmd"}:
        return "/".join(parts[:2])
    return "/".join(parts[:2])


def classify(path: str, file_paths: list[str]) -> str:
    low = path.lower()
    last = low.split("/")[-1]
    if any(x in low for x in ("test", "spec", "e2e")):
        return "test"
    if any(x in low for x in ("auth", "identity", "security", "session")):
        return "security"
    if any(x in low for x in ("database", "postgres", "redis", "prisma", "migrat", "sqlite", "model")):
        return "database"
    if any(x in low for x in ("infra", "docker", "terraform", "k8s", "deploy", "ci", "helm")):
        return "infra"
    if any(x in low for x in ("docs", "document", "guide", "readme")):
        return "docs"
    if any(x in low for x in ("components", "pages", "views", "frontend", "client", "widget", "web", "ui", "layout")):
        return "frontend"
    if any(x in low for x in ("api", "routes", "router", "gateway", "endpoint", "controller", "handlers")):
        return "api"
    if any(x in low for x in ("service", "worker", "jobs", "queue", "payment", "order", "notification")):
        return "service"
    if any(x in low for x in ("utils", "helpers", "shared", "lib", "pkg", "packages", "sdk", "types")):
        return "library"
    if last in {"config", "settings"}:
        return "infra"
    if len(file_paths) and all(PurePosixPath(p).suffix in {".md", ".mdx", ".rst"} for p in file_paths):
        return "docs"
    return "core"


def title_for(path: str) -> str:
    if path == "root":
        return "Root files"
    name = path.split("/")[-1]
    if name.lower() in {"ui", "api", "sdk", "cli", "db"}:
        return name.upper()
    label = re.sub(r"[-_]", " ", name).strip()
    return (label[:1].upper() + label[1:]) if label else name


def source_priority(path: str) -> tuple[int, int, str]:
    pieces = path.split("/")
    suffix = PurePosixPath(path).suffix
    if suffix not in SOURCE_SUFFIXES:
        return (99, 99, path)
    category = 0 if pieces[0] in {"src", "app", "apps", "packages", "services", "server", "internal"} else 2
    if any(w in path.lower() for w in ("index.", "route", "main.", "app.", "server.", "service", "api/", "components/")):
        category -= 1
    return (category, len(pieces), path)


def _resolve_import(ref: str, origin: str) -> str | None:
    if not ref or len(ref) > 190:
        return None
    if ref.startswith("./") or ref.startswith("../"):
        normalized = posixpath.normpath(posixpath.join(posixpath.dirname(origin), ref))
        if normalized == ".." or normalized.startswith("../"):
            return None
        return normalized
    if ref.startswith("@/") or ref.startswith("~/"):
        return "src/" + ref[2:]
    if ref.startswith("#/"):
        return "src/" + ref[2:]
    return None


def parse_imports(content: str, origin: str) -> set[str]:
    if not content or len(content) > MAX_SOURCE_BYTES:
        return set()
    suffix = PurePosixPath(origin).suffix
    found: set[str] = set()
    if suffix in {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}:
        for match in SOURCE_TEXT_PATTERN.findall(content) + JS_BARE_IMPORT.findall(content):
            resolved = _resolve_import(match, origin)
            if resolved:
                found.add(resolved)
    elif suffix == ".py":
        for item in PY_FROM_IMPORT.findall(content) + PY_IMPORT.findall(content):
            # Absolute Python package paths only; relative imports need package context.
            found.add(item.replace(".", "/"))
    return found


def _module_for_path(path: str, candidates: set[str]) -> str | None:
    # Longest prefix is necessary for nested modules (e.g. src/components vs src).
    possible = [m for m in candidates if m != "root" and (path == m or path.startswith(m + "/"))]
    if possible:
        return max(possible, key=len)
    return "root" if "root" in candidates and "/" not in path else None


def build_graph(
    files: list[dict], source_texts: dict[str, str] | None = None, *,
    name: str = "Repository", owner: str = "GitHub", description: str = "",
    url: str = "", branch: str = "main", stars: int = 0, language: str = "",
    truncated: bool = False,
) -> dict:
    """Group visible files into bounded modules and link observed local imports.

    Files are supplied as {path, type, size} Git tree entries. Source texts are an
    explicitly bounded sample, not a full semantic/runtime program analysis.
    """
    source_texts = source_texts or {}
    selected_files = []
    for item in files[:MAX_FILES]:
        if item.get("type") != "blob":
            continue
        path = clean_path(item.get("path", ""))
        if path:
            selected_files.append(path)
    dirs: dict[str, list[str]] = defaultdict(list)
    for path in selected_files:
        dirs[group_for_file(path)].append(path)

    ordered = sorted(dirs, key=lambda d: (-len(dirs[d]), d))
    limited = len(ordered) > MAX_NODES
    retained = ordered[:MAX_NODES]
    candidate_set = set(retained)
    symbols_by_module: dict[str, list[dict]] = defaultdict(list)
    for origin, content in source_texts.items():
        module = _module_for_path(origin, candidate_set)
        if module is None:
            continue
        existing = symbols_by_module[module]
        remaining = max(0, 18-len(existing))
        if remaining:
            existing.extend(extract_symbols(content, origin)[:remaining])
    nodes = []
    for path in retained:
        paths = dirs[path]
        kind = classify(path, paths)
        nodes.append({
            "id": path, "name": title_for(path), "path": path,
            "kind": kind, "fileCount": len(paths),
            "description": describe_module(path, sorted(paths, key=source_priority), len(paths)),
            "files": sorted(paths, key=source_priority)[:14],
            # More complete, bounded path index for issue placement and targeted
            # source retrieval. The visual inspector still shows the 14-file sample.
            "fileIndex": sorted(paths, key=source_priority)[:240],
            "sampled": path in {group_for_file(p) for p in source_texts},
            "symbols": symbols_by_module.get(path, []),
        })

    import_evidence: dict[tuple[str, str], list[str]] = defaultdict(list)
    for origin, content in source_texts.items():
        from_module = _module_for_path(origin, candidate_set)
        if not from_module:
            continue
        for imported in parse_imports(content, origin):
            to_module = _module_for_path(imported, candidate_set)
            if to_module and to_module != from_module:
                key = (from_module, to_module)
                if len(import_evidence[key]) < 5:
                    import_evidence[key].append(origin)
    edges = [
        {"source": source, "target": target, "type": "import", "count": len(samples), "evidence": sorted(samples)}
        for (source, target), samples in sorted(import_evidence.items())
    ]
    warnings = []
    if truncated or len(files) > MAX_FILES:
        warnings.append("Git tree truncated or over the file budget: analysis covers a partial repository snapshot.")
    if limited:
        warnings.append(f"Showing {MAX_NODES} largest modules out of {len(ordered)} groups.")
    if source_texts:
        warnings.append(f"Dependencies are derived from {len(source_texts)} sampled source files; unobserved dependencies are not shown.")
    else:
        warnings.append("Source imports were not available; this map shows directory structure only.")
    return {
        "name": name, "owner": owner, "description": description or "Explore this repository's modules and their visible import relationships.",
        "url": url, "branch": branch, "stars": stars, "language": language or "Multi-language",
        "source": "github", "nodes": nodes, "edges": edges,
        "stats": {
            "modules": len(nodes), "files": len(selected_files), "dependencies": len(edges),
            "inspectedSources": len(source_texts), "partial": bool(limited or truncated or len(files) > MAX_FILES),
        },
        "warnings": warnings,
    }
