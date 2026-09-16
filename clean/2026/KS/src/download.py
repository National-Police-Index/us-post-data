"""Download the KS 2026 raw data from a Dropbox shared-folder link.

Dropbox serves a shared folder as a single zip when the link's ``dl``
parameter is ``1``. This script streams that zip to ``data/input/`` and
extracts it in place so ``clean.py`` can read the raw files.

Usage (from clean/2026/KS/):
    python src/download.py                  # download + extract
    python src/download.py --keep-zip       # leave the zip in data/input/
"""

import argparse
import logging
import os
import zipfile
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

import requests


DROPBOX_URL = (
    "https://www.dropbox.com/scl/fo/tlhr9flp2mdojuxua1kvc/"
    "AI9H07kQZswGZx6I0NC00Tc"
    "?rlkey=861uxkb0q2o57z5r1tai05lw8&st=a0djg6em&dl=0"
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def force_direct_download(url: str) -> str:
    """Rewrite the share link so Dropbox serves the folder as a zip."""
    parts = urlsplit(url)
    query = parse_qs(parts.query)
    query["dl"] = ["1"]
    return urlunsplit(parts._replace(query=urlencode(query, doseq=True)))


def download(url: str, dest: str, chunk_size: int = 1 << 20) -> str:
    logger.info("GET %s", url)
    with requests.get(url, stream=True, timeout=(30, 600)) as resp:
        resp.raise_for_status()
        ctype = resp.headers.get("Content-Type", "")
        if "zip" not in ctype and "octet-stream" not in ctype:
            raise RuntimeError(
                f"expected a zip, got Content-Type={ctype!r} — "
                "link may be expired, private, or not a folder link"
            )
        total = 0
        with open(dest, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=chunk_size):
                fh.write(chunk)
                total += len(chunk)
                if total % (50 << 20) < chunk_size:
                    logger.info("  %.1f MB", total / (1 << 20))
    logger.info("downloaded %.1f MB → %s", total / (1 << 20), dest)
    return dest


def extract(zip_path: str, input_dir: str) -> list[str]:
    os.makedirs(input_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist() if not n.endswith("/")]
        zf.extractall(input_dir)
    logger.info("extracted %d file(s) → %s", len(names), input_dir)
    for n in names:
        logger.info("  %s", n)
    return names


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DROPBOX_URL)
    parser.add_argument("--input-dir", default="data/input")
    parser.add_argument("--keep-zip", action="store_true")
    args = parser.parse_args()

    zip_path = os.path.join(args.input_dir, "ks-2026.zip")
    os.makedirs(os.path.dirname(zip_path), exist_ok=True)

    download(force_direct_download(args.url), zip_path)
    extract(zip_path, args.input_dir)
    if not args.keep_zip:
        os.remove(zip_path)


if __name__ == "__main__":
    main()
