"""Bounded public GitHub source-archive import, without REST API calls.

For free previews only: GitHub documents source ZIP archives for public repos.
Use codeload.github.com/owner/repo/zip/HEAD (the default-branch snapshot).
Never execute archive content or extract files to disk. Archive imports cannot
prove a commit SHA, stars, default branch name, or issue list.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import PurePosixPath
import stat
import zipfile
from urllib.parse import quote

import httpx

from .graph import MAX_SOURCE_BYTES, MAX_FILES, build_graph, source_priority

# Deliberately small for a single-worker 512 MB free hosted demonstration.
MAX_ARCHIVE_BYTES = 12_000_000
MAX_ARCHIVE_ENTRIES = 13_000
MAX_ARCHIVE_EXPANDED_BYTES = 65_000_000
SAMPLE_FILES = 3


def _valid_path(item: zipfile.ZipInfo, root: str) -> str | None:
    """Remove the one archive wrapper directory; reject unsafe paths and links."""
    name = item.filename
    if item.is_dir() or not name.startswith(root + "/"):
        return None
    relative = name[len(root) + 1:]
    if (not relative or len(relative) > 450 or relative.startswith("/")
            or "\\" in relative or "\x00" in relative):
        return None
    parts = relative.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return None
    unix_mode = item.external_attr >> 16
    if stat.S_IFMT(unix_mode) == stat.S_IFLNK:
        return None
    return relative


async def get_public_archive_graph(owner: str, repo: str,
                                   client: httpx.AsyncClient | None = None) -> dict:
    """Download a small, public default-branch source archive with firm caps.

    Not used for token-backed imports. Codeload is a public source-distribution
    endpoint and still has its own service protections; never repeatedly retry
    after a 403/429, follow arbitrary redirects, or use it for large repositories.
    """
    from .github import RepoError, _source_sample

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=httpx.Timeout(24, connect=6),
                                   follow_redirects=False)
    assert client is not None
    archive_url = ("https://codeload.github.com/" + quote(owner, safe="") + "/"
                   + quote(repo, safe="") + "/zip/HEAD")
    try:
        try:
            async with client.stream("GET", archive_url,
                                     headers={"Accept": "application/zip",
                                              "User-Agent": "RepoWorld/0.9.7"},
                                     timeout=httpx.Timeout(25, connect=6),
                                     follow_redirects=False) as response:
                if response.status_code == 404:
                    raise RepoError("This public repository archive was not found. Check the owner/name and visibility.", 404)
                if response.status_code in (403, 429):
                    # Respect archive service throttling: no automatic retry.
                    raise RepoError("GitHub source archives are temporarily restricted. A server-side GITHUB_TOKEN enables standard GitHub API importing.",429,retry_after=300)
                if response.status_code != 200:
                    raise RepoError("GitHub could not provide the public source archive (HTTP " + str(response.status_code) + "). Try a different public repo.",502)
                length = response.headers.get("content-length", "")
                if length.isdigit() and int(length) > MAX_ARCHIVE_BYTES:
                    raise RepoError("This repository archive is too large for the free demo. Try a smaller public repository.", 413)
                payload = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(payload) + len(chunk) > MAX_ARCHIVE_BYTES:
                        raise RepoError("This repository archive is too large for the free demo. Try a smaller public repository.", 413)
                    payload.extend(chunk)
        except httpx.TimeoutException as exc:
            raise RepoError("The public source archive timed out. Try a smaller repository.", 504) from exc
        except httpx.RequestError as exc:
            raise RepoError("GitHub's source archive server could not be reached from the host.", 502) from exc
        if len(payload) < 4 or payload[:4] != b"PK\x03\x04":
            raise RepoError("GitHub returned an unexpected archive response.", 502)
        try:
            with zipfile.ZipFile(BytesIO(payload)) as z:
                infos = z.infolist()
                if len(infos) > MAX_ARCHIVE_ENTRIES:
                    raise RepoError("This repository has too many archive entries for the free demo.", 413)
                roots = {item.filename.split("/", 1)[0] for item in infos if "/" in item.filename}
                if len(roots) != 1:
                    raise RepoError("Unexpected public repository archive layout.", 502)
                root = next(iter(roots))
                if not root.lower().startswith(repo.lower() + "-"):
                    raise RepoError("GitHub archive does not match the requested public repository.",502)
                selected = []
                catalog = {}
                expanded = 0
                for item in infos:
                    if item.is_dir():
                        continue
                    expanded += item.file_size
                    if expanded > MAX_ARCHIVE_EXPANDED_BYTES:
                        raise RepoError("The repository's expanded archive exceeds the free demo memory budget.",413)
                    relative = _valid_path(item,root)
                    if not relative:
                        continue
                    catalog[relative] = item
                    selected.append({"path": relative, "type": "blob", "size": item.file_size})
                if not selected:
                    raise RepoError("This public archive contains no supported source files.",422)
                chosen = _source_sample(selected,SAMPLE_FILES)
                sources = {}
                for entry in chosen:
                    item = catalog[entry["path"]]
                    # Limit expansion ratios and individual reads. GitHub source
                    # code often compresses well; skip extreme entries instead
                    # of decompressing any suspicious member.
                    if (item.file_size > MAX_SOURCE_BYTES or item.file_size < 1 or
                        item.compress_size < 1 or item.file_size > 500 * item.compress_size):
                        continue
                    try:
                        data = z.read(item)
                        if len(data) <= MAX_SOURCE_BYTES:
                            sources[entry["path"]] = data.decode("utf-8",errors="replace")
                    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile):
                        continue
        except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError) as exc:
            raise RepoError("The public repository archive was damaged or unsupported.",502) from exc
        graph = build_graph(selected, sources, name=repo, owner=owner,
                            url=f"https://github.com/{owner}/{repo}",
                            description="Public GitHub default-branch source archive.",
                            branch="HEAD", stars=0, language="Multi-language",
                            truncated=len(selected) > MAX_FILES)
        if not graph.get("nodes"):
            raise RepoError("No supported files were found for the 3D city.", 422)
        graph.setdefault("warnings", []).append(
            "Source archive imported directly from GitHub without the REST API. "
            "The commit SHA, default branch name, stars and issue list were not independently verified. "
            "Source links reference movable HEAD; GitHub Issue Radar still needs GitHub API access."
        )
        graph["stars"] = None  # Archive data cannot verify star count.
        return graph
    finally:
        if owns_client:
            await client.aclose()
