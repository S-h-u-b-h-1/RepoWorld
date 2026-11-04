"""Grounded repository navigation for saved public GitHub snapshots.

No code execution and no AI inference required. Find results are path/filename
candidates. Impact edges are bounded, sampled static imports—not runtime proof.
"""
from __future__ import annotations

from collections import deque
import re

TOKEN_RE = re.compile(r"[a-z0-9]+")
STOP = {"a", "an", "the", "i", "we", "my", "our", "to", "of", "in", "on", "for", "from", "at", "and", "or", "is", "are", "this", "that", "where", "which", "what", "how", "who", "can", "do", "does", "should", "would", "will", "make", "change", "edit", "implement", "find", "show", "located", "location", "handled", "handle", "code", "file", "files", "module", "repo", "repository", "feature", "part", "system", "logic", "responsible", "add", "new", "need", "want", "related", "place", "used", "uses"}
# Route ordinary language to filenames and directory conventions, not invented semantics.
CONCEPTS = {
    "auth": ("authentication", "authorize", "authorization", "login", "signin", "signup", "logout", "password", "jwt", "identity", "session", "token", "oauth", "sso", "user"),
    "payment": ("checkout", "payments", "billing", "charge", "stripe", "invoice", "transaction", "pay"),
    "order": ("orders", "cart", "basket", "purchase", "checkout", "fulfillment"),
    "ui": ("frontend", "interface", "component", "page", "screen", "view", "layout", "css", "styles", "design"),
    "api": ("endpoint", "endpoints", "routes", "router", "gateway", "http", "requests", "request", "controller", "rest"),
    "db": ("data", "storage", "database", "postgres", "sqlite", "migration", "schema", "models", "persistence", "sql"),
    "test": ("testing", "tests", "e2e", "spec", "specs", "pytest", "playwright", "unit", "qa"),
    "deploy": ("deployment", "hosting", "infra", "infrastructure", "docker", "kubernetes", "ci", "pipeline", "config", "workflow"),
    "search": ("lookup", "filter", "query", "find", "catalog", "index"),
    "cache": ("redis", "caching", "memory", "cache"),
    "notification": ("email", "mail", "sms", "push", "messaging", "message", "alert"),
    "security": ("permission", "permissions", "access", "encryption", "role", "roles", "csrf", "security"),
}


def tokens(text: str) -> set[str]:
    # Split camelCase and snake_case before tokenizing.
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(text or ""))
    return {t for t in TOKEN_RE.findall(text.lower().replace("_", " ").replace("-", " ")) if t not in STOP and len(t) > 1}


def expand_query(query: str) -> set[str]:
    found = tokens(query)
    for key, words in CONCEPTS.items():
        if key in found or found.intersection(words):
            found.add(key)
            # Limit expansion to relevant terms rather than all terms for all topics.
            found.update(words)
    return found


def _score_text(text: str, original: set[str], expanded: set[str], weight: int) -> tuple[int, list[str]]:
    text_tokens = tokens(text)
    exact = text_tokens & original
    extended = (text_tokens & expanded) - exact
    score = len(exact) * weight + len(extended) * max(1, weight // 3)
    return score, sorted(exact | extended)


def find_modules(graph: dict, query: str, *, limit: int = 6) -> dict:
    """Rank path-derived candidates. Returns no false assertion of source behavior."""
    if not isinstance(query, str) or not 2 <= len(query.strip()) <= 160:
        raise ValueError("Describe what you are looking for in 2–160 characters.")
    original = tokens(query)
    expanded = expand_query(query)
    if not original:
        return {"query": query, "results": [], "scope": "No meaningful search terms were provided."}
    ranked = []
    for node in graph.get("nodes", [])[:72]:
        if not isinstance(node, dict) or not isinstance(node.get("id"), str):
            continue
        main = " ".join(str(node.get(k) or "") for k in ("name", "path"))
        main_score, main_hits = _score_text(main, original, expanded, 10)
        kind_score, kind_hits = _score_text(str(node.get("kind", "")), original, expanded, 5)
        desc_score, desc_hits = _score_text(str(node.get("description", "")), original, expanded, 3)
        ranked_files = []
        for f in node.get("files", [])[:20]:
            if not isinstance(f, str):
                continue
            score, hits = _score_text(f, original, expanded, 8)
            if score > 0:
                ranked_files.append((score, f, hits))
        ranked_files.sort(key=lambda row: (-row[0], row[1]))
        file_score = sum(row[0] for row in ranked_files[:2])
        ranked_symbols=[]
        for sym in node.get('symbols', [])[:18]:
            if not isinstance(sym,dict) or not isinstance(sym.get('name'),str):
                continue
            sym_score, sym_hits = _score_text(sym['name'], original, expanded, 13)
            if sym_score:
                ranked_symbols.append((sym_score,sym['name'],sym.get('file',''),sym_hits))
        ranked_symbols.sort(key=lambda row:(-row[0],row[1]))
        total = main_score + kind_score + min(desc_score, 12) + file_score + sum(r[0] for r in ranked_symbols[:2])
        if total <= 0:
            continue
        evidence = [f for _score, f, _hits in ranked_files[:3]]
        if not evidence:
            evidence = [str(f) for f in node.get("files", [])[:2] if isinstance(f, str)]
        matches = sorted(set(main_hits + kind_hits + desc_hits + [hit for _, _, hits in ranked_files[:2] for hit in hits] + [hit for _,_,_,hits in ranked_symbols[:2] for hit in hits]))
        ranked.append((total, int(node.get("fileCount") or 0), node.get("id"), {
            "nodeId": node["id"], "name": str(node.get("name", "")),
            "path": str(node.get("path", "")), "kind": str(node.get("kind", "")),
            "score": total, "matchedTerms": matches[:8], "files": evidence,
            "symbols": [{"name":a[1],"file":a[2]} for a in ranked_symbols[:3]],
            "reason": "Matched sampled declaration names" if ranked_symbols else "Matched repository paths and filenames" if ranked_files else "Matched module path, type, or path-derived description",
        }))
    ranked.sort(key=lambda row: (-row[0], -row[1], row[2]))
    # We never turn a zero-match search into an AI hallucination.
    return {"query": query, "results": [row[3] for row in ranked[:limit]],
            "scope": "Candidates inferred from imported paths, filenames, and sampled declaration names. Check the linked source before editing.",
            "partial": bool(graph.get("stats", {}).get("partial"))}


def impact_trace(graph: dict, node_id: str, *, max_depth: int = 4, max_nodes: int = 50) -> dict:
    """Find reverse importer paths: changing B could affect A when A imports B."""
    nodes = {n["id"]: n for n in graph.get("nodes", [])[:72] if isinstance(n, dict) and isinstance(n.get("id"), str)}
    if node_id not in nodes:
        raise KeyError("Module not found in this repository snapshot.")
    reverse: dict[str, set[str]] = {nid: set() for nid in nodes}
    dependencies: set[str] = set()
    for edge in graph.get("edges", [])[:2500]:
        if not isinstance(edge, dict):
            continue
        src, dst = edge.get("source"), edge.get("target")
        if src in nodes and dst in nodes and src != dst:
            reverse[dst].add(src)
            if src == node_id:
                dependencies.add(dst)
    depths = {node_id: 0}
    parent: dict[str, str] = {}
    queue = deque([node_id])
    while queue and len(depths) <= max_nodes:
        current = queue.popleft()
        if depths[current] >= max_depth:
            continue
        for dependent in sorted(reverse.get(current, [])):
            if dependent not in depths and len(depths) < max_nodes:
                depths[dependent] = depths[current] + 1
                parent[dependent] = current
                queue.append(dependent)
    entries = []
    for item, depth in sorted(depths.items(), key=lambda pair: (pair[1], pair[0])):
        if item == node_id:
            continue
        chain = [item]
        while chain[-1] in parent:
            chain.append(parent[chain[-1]])
        # Report file->import direction: importer ... -> changed node.
        entries.append({"nodeId": item, "name": str(nodes[item].get("name", item)),
                        "path": str(nodes[item].get("path", item)), "hops": depth,
                        "importPath": chain})
    impacted_ids = set(depths)
    relevant_edges = [{"source": e.get("source"), "target": e.get("target")}
                      for e in graph.get("edges", [])[:2500] if isinstance(e, dict)
                      and e.get("source") in impacted_ids and e.get("target") in impacted_ids]
    return {
        "root": node_id, "direct": [e for e in entries if e["hops"] == 1],
        "indirect": [e for e in entries if e["hops"] > 1],
        "dependencies": sorted(dependencies), "affectedCount": len(entries),
        "edges": relevant_edges, "maxDepth": max_depth,
        "scope": "Potential exposure through sampled static imports only. This is not a complete call graph, runtime trace, or proof of a breaking change.",
        "partial": bool(graph.get("stats", {}).get("partial")),
    }


TOPIC_HINTS = (
    (("auth", "session", "login", "identity", "oauth"), "identity, login, or session-related code"),
    (("payment", "billing", "stripe", "invoice"), "payments or billing-related code"),
    (("checkout", "order", "cart", "fulfil"), "order or checkout-related code"),
    (("search", "catalog", "filter"), "search or catalog-related code"),
    (("api", "route", "gateway", "handler", "controller"), "API endpoints or routing-related code"),
    (("postgres", "redis", "database", "schema", "migration", "model"), "storage, schema, or data-related code"),
    (("frontend", "page", "component", "layout", "ui", "web", "view"), "frontend or interface-related code"),
    (("test", "spec", "e2e", "pytest"), "test or quality-related code"),
    (("infra", "docker", "terraform", "deploy", "config", "workflow"), "deployment or configuration-related code"),
)

def describe_module(path: str, filenames: list[str], file_count: int) -> str:
    """Helpful but qualified description; only path/filename evidence is available."""
    words = tokens(path + ' ' + ' '.join(filenames[:8]))
    for phrases, topic in TOPIC_HINTS:
        if any(term in words for term in phrases):
            return (f"{file_count} files appear related to {topic}, inferred from directory and filenames. "
                    "Open a source file to verify its actual responsibility.")
    return (f"{file_count} files grouped under {path}. Their purpose cannot be established "
            "from names alone; open a representative file to investigate.")
