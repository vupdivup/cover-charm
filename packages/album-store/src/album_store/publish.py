"""Publish rendered GIFs to a git branch for jsDelivr CDN serving.

Pulls every album's GIF (and preview) out of MinIO, materializes them
under `gifs/<slug>/<slug>.gif` / `previews/<slug>/<slug>.gif` -- the
same relative paths as their object keys, so the manifest needs no
translation layer -- alongside a `manifest.json`, and force-pushes the
result as a single commit on an orphan branch (default `assets-dev`).
jsDelivr then serves it at
`https://cdn.jsdelivr.net/gh/<owner>/<repo>@<branch>/...`.

There is deliberately only one channel today: this force-pushes over
whatever was there, with no PR and no review. A reviewed, tagged
"prod" channel (PR into a separate `assets` branch, immutable
`assets-vN` tags so a site can pin an exact release) is a natural
later addition, but isn't needed until there's a production site to
protect.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .config import Settings
from .db import StoredAlbum, albums_with_gif, connect
from .objects import client as s3_client
from .objects import get_object

logger = logging.getLogger(__name__)

__all__ = ["PublishError", "PublishResult", "publish_assets"]

_PURGE_URL = "https://purge.jsdelivr.net/"


class PublishError(RuntimeError):
    """Raised for a git/gh failure that leaves publish unable to proceed."""


@dataclass(frozen=True)
class PublishResult:
    branch: str
    commit: str
    count: int
    base_url: str
    # Set only for --dry-run, where nothing is pushed and the caller
    # needs somewhere to look at the materialized tree.
    tree_dir: Path | None = None


def _run_git(args: list[str], *, cwd: str | Path | None = None) -> str:
    try:
        result = subprocess.run(
            ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
        )
    except FileNotFoundError as exc:
        raise PublishError("git executable not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise PublishError(f"git {' '.join(args)} failed: {exc.stderr.strip()}") from exc
    return result.stdout.strip()


def _repo_slug(remote_url: str) -> str:
    """Turn a git remote URL into an '<owner>/<repo>' slug for CDN/purge URLs.

    Handles both the https:// and git@ forms; jsDelivr's gh backend
    only needs the owner/repo pair, not the protocol or a trailing .git.
    """
    match = re.search(r"[:/]([^/:]+)/([^/]+?)(?:\.git)?/?$", remote_url)
    if not match:
        raise PublishError(f"couldn't parse owner/repo from remote url: {remote_url!r}")
    return f"{match.group(1)}/{match.group(2)}"


def _write_tree(albums: list[StoredAlbum], *, out_dir: Path, settings: Settings) -> int:
    """Download each album's GIF + preview into out_dir and write manifest.json.

    An album missing an object (e.g. deleted from MinIO after being
    rendered) is logged and skipped rather than aborting the whole
    publish -- same posture as render.py's per-album error handling.
    """
    s3 = s3_client(settings)
    manifest_albums = []
    for album in albums:
        try:
            gif_bytes = get_object(s3, settings.minio_gif_bucket, album.gif_key)
            preview_bytes = get_object(s3, settings.minio_gif_bucket, album.preview_key)
        except Exception as exc:  # noqa: BLE001 -- boto3 raises ClientError subtypes we don't need to enumerate
            logger.warning(
                "skipping album id=%s %r by %r, couldn't fetch object: %s",
                album.id,
                album.title,
                album.artist,
                exc,
            )
            continue

        gif_path = out_dir / album.gif_key
        preview_path = out_dir / album.preview_key
        gif_path.parent.mkdir(parents=True, exist_ok=True)
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        gif_path.write_bytes(gif_bytes)
        preview_path.write_bytes(preview_bytes)

        manifest_albums.append(
            {
                "artist": album.artist,
                "title": album.title,
                "year": album.year,
                "gif": album.gif_key,
                "preview": album.preview_key,
            }
        )
        logger.debug("wrote %s + %s", album.gif_key, album.preview_key)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(manifest_albums),
        "albums": manifest_albums,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return len(manifest_albums)


def _push_tree(tree_dir: Path, *, remote: str, branch: str, repo_dir: str | Path | None) -> str:
    """Commit tree_dir as a single commit on a fresh orphan branch and force-push it.

    Runs in a throwaway worktree under a temp dir rather than the
    caller's checkout, so publishing can never disturb whatever the
    user has checked out or staged. A fresh orphan every call (instead
    of updating an existing checkout of the branch) means assets-dev
    never accumulates blob history across publishes -- it's always
    exactly one commit.
    """
    # The orphan needs its own *local* branch name distinct from the
    # target remote branch: after the first publish a local branch
    # named `branch` would already exist (worktree removal doesn't
    # delete it), and `worktree add --orphan` refuses to reuse a name.
    # Pushing `HEAD:refs/heads/<branch>` below lets the local and
    # remote names differ, so this scratch branch is deleted at the end
    # and never collides with itself on the next publish.
    local_branch = f"album-store-publish-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
    with tempfile.TemporaryDirectory(prefix="album-store-publish-") as tmp:
        worktree = Path(tmp) / "worktree"
        _run_git(["worktree", "add", "--orphan", "-b", local_branch, str(worktree)], cwd=repo_dir)
        try:
            for child in worktree.iterdir():
                if child.name == ".git":
                    continue
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
            shutil.copytree(tree_dir, worktree, dirs_exist_ok=True)

            _run_git(["add", "--all"], cwd=worktree)
            _run_git(
                [
                    "-c",
                    "user.name=album-store",
                    "-c",
                    "user.email=album-store@localhost",
                    "commit",
                    "-m",
                    f"Publish {branch}",
                ],
                cwd=worktree,
            )
            commit = _run_git(["rev-parse", "HEAD"], cwd=worktree)
            # Plain --force, not --force-with-lease: this branch is
            # entirely machine-generated and disposable, and a lease
            # would require fetching+basing on a prior SHA we
            # deliberately never read (every publish starts from a
            # fresh orphan, not the branch's current tip).
            _run_git(["push", "--force", remote, f"HEAD:refs/heads/{branch}"], cwd=worktree)
        finally:
            _run_git(["worktree", "remove", "--force", str(worktree)], cwd=repo_dir)
            _run_git(["branch", "-D", local_branch], cwd=repo_dir)
    return commit


def _purge_cdn(repo_slug: str, branch: str, paths: list[str]) -> None:
    """Best-effort jsDelivr cache purge for what was just pushed.

    A branch ref is cached up to 12h; without this the site would keep
    seeing stale GIFs until the cache expires on its own. Failure here
    doesn't fail the publish -- the assets are already live at origin,
    the CDN just catches up on its own schedule.
    """
    cdn_paths = [f"/gh/{repo_slug}@{branch}/{p}" for p in paths]
    body = json.dumps({"path": cdn_paths}).encode()
    req = urllib.request.Request(
        _PURGE_URL, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            logger.debug("jsDelivr purge responded %s", resp.status)
    except (urllib.error.URLError, TimeoutError) as exc:
        logger.warning("jsDelivr cache purge failed (assets are pushed regardless): %s", exc)


def publish_assets(
    *,
    limit: int | None = None,
    remote: str = "origin",
    branch: str = "assets-dev",
    dry_run: bool = False,
    out_dir: str | Path | None = None,
    repo_dir: str | Path | None = None,
    settings: Settings | None = None,
) -> PublishResult:
    """Export every album's GIF + preview to a manifest'd tree and publish it.

    With dry_run=True, the tree is written to out_dir (a temp dir if
    unset) and nothing is pushed -- lets you inspect what would be
    published, or feed a local dev server, without touching git.
    """
    settings = settings or Settings.from_env()

    with connect(settings) as conn:
        albums = albums_with_gif(conn, limit=limit)
    if not albums:
        raise ValueError("no albums have a rendered GIF yet -- run `album-store render` first")
    logger.info("%d album(s) to publish", len(albums))

    tree_dir = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix="album-store-publish-tree-"))
    tree_dir.mkdir(parents=True, exist_ok=True)
    count = _write_tree(albums, out_dir=tree_dir, settings=settings)
    if count == 0:
        raise ValueError("every album's GIF/preview object was missing from MinIO, nothing to publish")

    remote_url = _run_git(["remote", "get-url", remote], cwd=repo_dir)
    repo_slug = _repo_slug(remote_url)
    base_url = f"https://cdn.jsdelivr.net/gh/{repo_slug}@{branch}"

    if dry_run:
        logger.info("dry run: tree written to %s, nothing pushed", tree_dir)
        return PublishResult(branch=branch, commit="", count=count, base_url=base_url, tree_dir=tree_dir)

    commit = _push_tree(tree_dir, remote=remote, branch=branch, repo_dir=repo_dir)
    logger.info("pushed %d album(s) to %s@%s (%s)", count, remote, branch, commit)

    paths = ["manifest.json"] + [f"{a.gif_key}" for a in albums] + [f"{a.preview_key}" for a in albums]
    _purge_cdn(repo_slug, branch, paths)

    return PublishResult(branch=branch, commit=commit, count=count, base_url=base_url)
