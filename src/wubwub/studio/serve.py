"""Serve the `site/` showcase locally against either asset channel.

The page is static and channel-aware at runtime (`?channel=dev` in
`site/app.js`), so serving is just a stdlib file server -- no build, no
dependency, no generated config file. What the two modes differ in is
what they do *before* serving:

- prod (default): nothing. The page reads the manifest from the `assets`
  branch and the media from the immutable tag that manifest names, i.e.
  exactly what a visitor to the hosted site gets.
- dev: force-push the current MinIO contents to `assets-dev` first (the
  `publish.py` channel), then serve with `?channel=dev` so the page
  reads that branch instead.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .config import Settings
from .publish import publish_assets

logger = logging.getLogger(__name__)

__all__ = ["serve_site", "site_dir"]

DEFAULT_PORT = 8000


class _Handler(SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler that logs through `logging`, not straight to stderr.

    The stdlib default writes request lines to sys.stderr itself, which
    would ignore the CLI's -v/-q entirely.
    """

    def log_message(self, format: str, *args) -> None:  # noqa: A002 -- stdlib signature
        logger.debug("%s - %s", self.address_string(), format % args)


def site_dir(repo_dir: str | Path | None = None) -> Path:
    """Locate the repo's `site/` directory relative to this package."""
    if repo_dir:
        return Path(repo_dir) / "site"
    # src/wubwub/studio/serve.py -> repo root
    return Path(__file__).resolve().parents[3] / "site"


def serve_site(
    *,
    dev: bool = False,
    port: int = DEFAULT_PORT,
    publish: bool = True,
    site: str | Path | None = None,
    remote: str = "origin",
    branch: str = "assets-dev",
    repo_dir: str | Path | None = None,
    settings: Settings | None = None,
    on_start: Callable[[str], None] | None = None,
) -> str:
    """Serve the showcase until interrupted; returns the URL it served.

    In dev mode, `publish=False` skips the assets-dev push and serves
    against whatever is already on that branch. `on_start` is handed the
    URL once the socket is bound but before the blocking serve loop --
    that's how the CLI gets the URL onto stdout without this module
    printing anything itself.
    """
    root = Path(site) if site else site_dir(repo_dir)
    if not (root / "index.html").is_file():
        raise ValueError(f"no site/index.html under {root} -- pass site= to point at the page")

    if dev and publish:
        result = publish_assets(
            remote=remote, branch=branch, repo_dir=repo_dir, settings=settings
        )
        logger.info("published %d album(s) to %s", result.count, result.base_url)

    url = f"http://localhost:{port}/{'?channel=dev' if dev else ''}"
    handler = partial(_Handler, directory=str(root))
    with ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        logger.info("serving %s on %s (%s channel)", root, url, "dev" if dev else "prod")
        if on_start:
            on_start(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            logger.info("stopped")
    return url
