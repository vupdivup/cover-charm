"""Release rendered GIFs to the reviewed prod asset channel.

Builds the same tree as the dev channel (`publish.py`) -- `manifest.json`
plus `gifs/`/`previews/` mirroring the MinIO object keys -- but instead
of force-pushing it, commits it on a `release/assets-vN` branch off the
prod `assets` branch and opens a PR. Merging that PR is the release; a
GitHub Action (`.github/workflows/tag-assets.yml`) then creates the
immutable `assets-vN` tag named in the manifest.

Two consequences of the PR requirement, both deliberate:

- Unlike `assets-dev`, this branch accumulates blob history: a PR needs
  a shared ancestor with its base, so it can't be a fresh orphan every
  time. Fine at this catalog size; re-orphan `assets` by hand if the
  repo ever gets heavy.
- The version is decided *here*, before review, and written into the
  manifest, so the site can point every media URL at an immutable tag
  while only `manifest.json` is read from the moving branch. The tag
  itself is only created once the PR merges -- tagging unreviewed
  content would defeat the point of the channel.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .config import Settings
from .db import albums_with_gif, connect
from .publish import PublishError, _purge_cdn, _repo_slug, _run_git, _write_tree

logger = logging.getLogger(__name__)

__all__ = ["DeployError", "DeployResult", "deploy_assets"]

_TAG_PREFIX = "assets-v"

# GitHub runs a `push` workflow from the pushed branch's own copy, so the
# tagging job has to live *on* the assets branch, not just on master.
# Every release tree therefore carries it along -- and since it's part of
# the release, a reviewer sees any change to it in the PR diff.
_TAG_WORKFLOW = Path(".github/workflows/tag-assets.yml")


class DeployError(PublishError):
    """Raised for a git/gh failure that leaves a release unable to proceed."""


@dataclass(frozen=True)
class DeployResult:
    version: str
    count: int
    base_url: str
    # The release branch pushed for review, or the prod branch itself on
    # a bootstrap release (no base to open a PR against yet).
    head_branch: str
    commit: str
    pr_url: str | None = None
    bootstrapped: bool = False
    # Set only for --dry-run, where nothing is pushed.
    tree_dir: Path | None = None


def _run_gh(args: list[str], *, cwd: str | Path | None = None) -> str:
    """Shell out to the GitHub CLI, mirroring publish._run_git's error contract."""
    try:
        result = subprocess.run(
            ["gh", *args], cwd=cwd, check=True, capture_output=True, text=True
        )
    except FileNotFoundError as exc:
        raise DeployError(
            "gh executable not found on PATH -- install the GitHub CLI, or pass no_pr=True "
            "to push the release branch and open the PR by hand"
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise DeployError(f"gh {' '.join(args)} failed: {exc.stderr.strip()}") from exc
    return result.stdout.strip()


def _branch_exists(remote: str, branch: str, *, repo_dir: str | Path | None) -> bool:
    return bool(_run_git(["ls-remote", "--heads", remote, branch], cwd=repo_dir))


def _next_version(remote: str, *, repo_dir: str | Path | None) -> str:
    """Pick the next assets-vN, one past the highest tag the remote already has.

    Read from the remote rather than local tags so a checkout that never
    fetched tags can't hand out a version that already exists (the tag
    ruleset makes tags immutable, so a collision fails the release
    workflow rather than silently moving a tag).
    """
    refs = _run_git(["ls-remote", "--tags", remote, f"{_TAG_PREFIX}*"], cwd=repo_dir)
    numbers = [
        int(match.group(1))
        for match in re.finditer(rf"refs/tags/{_TAG_PREFIX}(\d+)$", refs, flags=re.MULTILINE)
    ]
    return f"{_TAG_PREFIX}{max(numbers, default=0) + 1}"


def _release_branch(version: str, remote: str, *, repo_dir: str | Path | None) -> str:
    """Branch name to open the release PR from, unique on the remote.

    A version is only consumed when its tag is cut, i.e. on merge -- so
    an abandoned release PR leaves `release/<version>` behind and the
    next deploy computes that same version again. Pushing onto that
    stale branch would fail (deliberately no --force here), so a
    collision gets a timestamp suffix and the dead branch is left for
    whoever abandoned it to delete.
    """
    name = f"release/{version}"
    if not _run_git(["ls-remote", "--heads", remote, name], cwd=repo_dir):
        return name
    stamped = f"{name}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    logger.warning("%s already exists on %s (abandoned release?), using %s", name, remote, stamped)
    return stamped


def _copy_tag_workflow(tree_dir: Path, *, repo_dir: str | Path | None) -> None:
    """Carry the tagging workflow into the release tree (see _TAG_WORKFLOW)."""
    root = Path(repo_dir) if repo_dir else Path(_run_git(["rev-parse", "--show-toplevel"]))
    source = root / _TAG_WORKFLOW
    if not source.is_file():
        raise DeployError(
            f"{_TAG_WORKFLOW} is missing from {root} -- without it the merged release "
            "would never get its tag, and the site's media URLs point at that tag"
        )
    target = tree_dir / _TAG_WORKFLOW
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def _album_lines(manifest: dict) -> dict[tuple[str, str], str]:
    """Index a manifest's albums by (artist, title) for a released-vs-new diff."""
    lines = {}
    for album in manifest.get("albums", []):
        key = (album.get("artist", ""), album.get("title", ""))
        year = album.get("year")
        lines[key] = f"{key[0]} — {key[1]}{f' ({year})' if year else ''}"
    return lines


def _pr_body(version: str, previous: dict | None, current: dict) -> str:
    """Summarize what this release adds/removes versus what's live now."""
    new = _album_lines(current)
    old = _album_lines(previous) if previous else {}
    added = [line for key, line in new.items() if key not in old]
    removed = [line for key, line in old.items() if key not in new]

    parts = [f"Release `{version}` — {len(new)} album(s)."]
    for heading, items in (("Added", added), ("Removed", removed)):
        if items:
            parts.append(f"**{heading} ({len(items)})**\n" + "\n".join(f"- {i}" for i in items))
    if not added and not removed:
        parts.append("No album added or removed; assets and/or manifest metadata changed.")
    parts.append(
        f"Merging this PR publishes the release; `.github/workflows/tag-assets.yml` "
        f"then creates the `{version}` tag every media URL is pinned to."
    )
    return "\n\n".join(parts)


def _push_release(
    tree_dir: Path,
    *,
    remote: str,
    branch: str,
    head_branch: str,
    version: str,
    repo_dir: str | Path | None,
    bootstrap: bool,
) -> tuple[str, dict | None] | None:
    """Commit tree_dir onto the prod branch's tip and push it for review.

    Returns (commit sha, the manifest this release replaces) or None when
    the tree is byte-identical to what's already released. Runs in a
    throwaway worktree under a temp dir, like publish._push_tree, so a
    release can never disturb the caller's checkout.
    """
    local_branch = f"wubwub-release-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
    with tempfile.TemporaryDirectory(prefix="wubwub-release-") as tmp:
        worktree = Path(tmp) / "worktree"
        if bootstrap:
            _run_git(["worktree", "add", "--orphan", "-b", local_branch, str(worktree)], cwd=repo_dir)
        else:
            # FETCH_HEAD, not a local tracking branch: the checkout this
            # runs from may have no `assets` branch of its own, and we
            # want the remote's tip regardless of what it has cached.
            _run_git(["fetch", remote, branch], cwd=repo_dir)
            _run_git(
                ["worktree", "add", "-b", local_branch, str(worktree), "FETCH_HEAD"], cwd=repo_dir
            )
        try:
            previous = None
            manifest_path = worktree / "manifest.json"
            if manifest_path.exists():
                previous = json.loads(manifest_path.read_text())

            for child in worktree.iterdir():
                if child.name == ".git":
                    continue
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
            shutil.copytree(tree_dir, worktree, dirs_exist_ok=True)

            _run_git(["add", "--all"], cwd=worktree)
            changed = _run_git(["status", "--porcelain"], cwd=worktree).splitlines()
            if not changed:
                return None
            # A rebuild always rewrites manifest.json (`generated_at`
            # moves, and so does the version it's about to be released
            # as), so "only the manifest changed" isn't enough to call
            # this a real release -- compare it with those two fields
            # dropped before deciding there's nothing to review.
            if previous is not None and all(line.endswith("manifest.json") for line in changed):
                current = json.loads(manifest_path.read_text())
                volatile = ("generated_at", "version")
                if {k: v for k, v in previous.items() if k not in volatile} == {
                    k: v for k, v in current.items() if k not in volatile
                }:
                    return None

            _run_git(
                [
                    "-c",
                    "user.name=wubwub",
                    "-c",
                    "user.email=wubwub@localhost",
                    "commit",
                    "-m",
                    f"Release {version}",
                ],
                cwd=worktree,
            )
            commit = _run_git(["rev-parse", "HEAD"], cwd=worktree)
            # No --force: unlike the dev channel this branch is reviewed,
            # so a rejected push means someone else moved it and the
            # release should be re-cut rather than overwritten.
            _run_git(["push", remote, f"HEAD:refs/heads/{head_branch}"], cwd=worktree)
        finally:
            _run_git(["worktree", "remove", "--force", str(worktree)], cwd=repo_dir)
            _run_git(["branch", "-D", local_branch], cwd=repo_dir)
    return commit, previous


def deploy_assets(
    *,
    limit: int | None = None,
    remote: str = "origin",
    branch: str = "assets",
    dry_run: bool = False,
    out_dir: str | Path | None = None,
    no_pr: bool = False,
    repo_dir: str | Path | None = None,
    settings: Settings | None = None,
) -> DeployResult | None:
    """Cut a prod asset release: build the tree, push a release branch, open the PR.

    Returns None when the freshly built tree matches what's already
    released -- there is nothing to review, so no branch is pushed and no
    PR is opened. With dry_run=True the tree is written to out_dir (a
    temp dir if unset) and neither git nor gh is touched.
    """
    settings = settings or Settings.from_env()

    with connect(settings) as conn:
        albums = albums_with_gif(conn, limit=limit)
    if not albums:
        raise ValueError("no albums have a rendered GIF yet -- run `wubwub studio render` first")
    logger.info("%d album(s) to release", len(albums))

    remote_url = _run_git(["remote", "get-url", remote], cwd=repo_dir)
    repo_slug = _repo_slug(remote_url)
    version = _next_version(remote, repo_dir=repo_dir)
    logger.info("next release version is %s", version)

    tree_dir = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix="wubwub-release-tree-"))
    tree_dir.mkdir(parents=True, exist_ok=True)
    count = _write_tree(albums, out_dir=tree_dir, settings=settings, version=version)
    if count == 0:
        raise ValueError("every album's GIF/preview object was missing from MinIO, nothing to release")
    _copy_tag_workflow(tree_dir, repo_dir=repo_dir)

    base_url = f"https://cdn.jsdelivr.net/gh/{repo_slug}@{version}"

    if dry_run:
        logger.info("dry run: tree written to %s, nothing pushed", tree_dir)
        return DeployResult(
            version=version,
            count=count,
            base_url=base_url,
            head_branch="",
            commit="",
            tree_dir=tree_dir,
        )

    bootstrap = not _branch_exists(remote, branch, repo_dir=repo_dir)
    # Nothing to open a PR against on the very first release, so the
    # bootstrap goes straight onto the prod branch -- which is also the
    # only push that has to happen before the branch ruleset can apply.
    head_branch = branch if bootstrap else _release_branch(version, remote, repo_dir=repo_dir)
    if bootstrap:
        logger.warning(
            "%s doesn't exist on %s yet, pushing the first release straight to it (no PR)",
            branch,
            remote,
        )

    pushed = _push_release(
        tree_dir,
        remote=remote,
        branch=branch,
        head_branch=head_branch,
        version=version,
        repo_dir=repo_dir,
        bootstrap=bootstrap,
    )
    if pushed is None:
        logger.info("released assets already match this tree, nothing to do")
        return None
    commit, previous = pushed
    logger.info("pushed %s to %s@%s (%s)", version, remote, head_branch, commit)

    if bootstrap or no_pr:
        # The manifest on the prod branch moved, so bust its (branch-ref)
        # cache. Media URLs are tag-pinned and immutable -- never purged.
        if bootstrap:
            _purge_cdn(repo_slug, branch, ["manifest.json"])
        return DeployResult(
            version=version,
            count=count,
            base_url=base_url,
            head_branch=head_branch,
            commit=commit,
            bootstrapped=bootstrap,
        )

    current = json.loads((tree_dir / "manifest.json").read_text())
    pr_url = _run_gh(
        [
            "pr",
            "create",
            "--base",
            branch,
            "--head",
            head_branch,
            "--title",
            f"Release {version}: {count} album(s)",
            "--body",
            _pr_body(version, previous, current),
        ],
        cwd=repo_dir,
    ).splitlines()[-1]
    logger.info("opened release PR %s", pr_url)

    return DeployResult(
        version=version,
        count=count,
        base_url=base_url,
        head_branch=head_branch,
        commit=commit,
        pr_url=pr_url,
    )
