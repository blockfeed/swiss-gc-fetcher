#!/usr/bin/env python3
"""
swiss_gc_fetcher.py (v0.3.1)

- Robust asset detection: case-insensitive, accepts names that *contain* "swiss_r####.(tar.xz|7z)".
- Adds --verbose for optional diagnostics (prints asset names if no match).
- Keeps: --device picoboot, --hide-files via fatattr, safe tar extraction (filter="data").
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import urllib.error
import zipfile
from pathlib import Path

API_BASE = "https://api.github.com/repos/emukidid/swiss-gc/releases"
# Accept names like "swiss_r1913.tar.xz", "SWISS_R1913.TAR.XZ", or prefixed variants (e.g., "release-swiss_r1913.tar.xz")
RE_DISTRIB_LOOSE = re.compile(r"swiss_r(?P<rev>\d+)\.(?P<ext>tar\.xz|7z)$", re.IGNORECASE)

def log(msg): print(msg, flush=True)

def http_get_json(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "swiss-gc-fetcher/0.3.1",
        "Accept": "application/vnd.github+json",
    })
    with urllib.request.urlopen(req) as f:
        return json.load(f)

def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "swiss-gc-fetcher/0.3.1"})
    with urllib.request.urlopen(req) as resp, open(dest, "wb") as out:
        shutil.copyfileobj(resp, out)

def pick_asset(assets, verbose=False):
    """
    Pick best asset: prefer .tar.xz then .7z; highest rev.
    More tolerant name matching (case-insensitive, not anchored).
    Returns dict with keys: name, url, ext, rev
    """
    candidates = []
    names = []
    for a in assets or []:
        name = a.get("name", "")
        names.append(name)
        m = RE_DISTRIB_LOOSE.search(name)
        if m:
            ext = m.group("ext").lower()
            rev = int(m.group("rev"))
            candidates.append((ext, rev, a))
    if not candidates:
        if verbose:
            log("DEBUG: available asset names: " + ", ".join(names) if names else "DEBUG: no assets in release")
        return None
    order = {"tar.xz": 0, "7z": 1}
    candidates.sort(key=lambda t: (order.get(t[0], 99), -t[1]))
    ext, rev, a = candidates[0]
    return {"name": a["name"], "url": a["browser_download_url"], "ext": ext, "rev": rev}

def ensure_7z():
    for cmd in ("7z", "7za"):
        if shutil.which(cmd):
            return cmd
    return None

def extract_tar_xz(tar_path, dest_dir):
    with tarfile.open(tar_path, mode="r:xz") as tf:
        tf.extractall(path=dest_dir, filter="data")

def extract_7z(archive_path, dest_dir):
    cmd = ensure_7z()
    if not cmd:
        raise RuntimeError("7z/7za not found in PATH; cannot extract .7z asset. Install p7zip or choose .tar.xz release.")
    subprocess.check_call([cmd, "x", "-y", f"-o{dest_dir}", archive_path], stdout=subprocess.DEVNULL)

def find_member(root_dir: Path, relpath: str) -> Path:
    norm_rel = relpath.replace("\\", "/")
    base = root_dir.as_posix()
    for p in root_dir.rglob("*"):
        if p.is_file():
            rp = p.as_posix()
            rp_rel = rp[len(base)+1:] if rp.startswith(base + "/") else rp
            if rp_rel.endswith(norm_rel):
                return p
    return None

def merge_directories(src_dir: Path, dst_dir: Path, dry_run=False, overwrite=False):
    if not src_dir.exists():
        raise FileNotFoundError(f"Source directory does not exist: {src_dir}")
    for root, dirs, files in os.walk(src_dir):
        rel = os.path.relpath(root, src_dir)
        target_root = dst_dir / rel if rel != "." else dst_dir
        if dry_run: log(f"mkdir -p {target_root}")
        else: os.makedirs(target_root, exist_ok=True)
        for f in files:
            s = Path(root) / f
            d = target_root / f
            if d.exists() and not overwrite:
                log(f"SKIP existing: {d}")
                continue
            if dry_run: log(f"copy {s} -> {d}")
            else:
                os.makedirs(d.parent, exist_ok=True)
                shutil.copy2(s, d)

def fatattr_available():
    return shutil.which("fatattr") is not None

def set_hidden_attributes(sd_root: Path, dry_run: bool):
    patterns = ["*.dol", "GBI", "MCBACKUP", "swiss"]
    fa = shutil.which("fatattr")
    if not fa:
        log("NOTICE: --hide-files requested but 'fatattr' was not found in PATH. Skipping hide step.")
        return
    log(f"fatattr found at: {fa}")
    for pattern in patterns:
        matches = list(sd_root.glob(pattern))
        if not matches:
            continue
        for m in matches:
            cmd = [fa, "+h", str(m)]
            log("Running: " + " ".join(cmd))
            if not dry_run:
                try:
                    subprocess.check_call(cmd)
                except subprocess.CalledProcessError as e:
                    log(f"WARNING: fatattr failed on {m}: {e}")
                except Exception as e:
                    log(f"WARNING: could not run fatattr on {m}: {e}")

def main():
    ap = argparse.ArgumentParser(
        description="Fetch Swiss release and install Picoboot payload to SD card."
    )
    ap.add_argument("--sd-root", required=True, help="SD card root path (e.g. /media/SDCARD)")
    ap.add_argument("--device", required=True, help="Target device (currently only 'picoboot' is supported)")
    ap.add_argument("--dry-run", action="store_true", help="Print actions without writing")
    ap.add_argument("--tag", help="Release tag to use (e.g. v0.6r1913). Default: latest")
    ap.add_argument("--force", action="store_true", help="Overwrite existing files")
    ap.add_argument("--hide-files", action="store_true",
                    help="Set FAT hidden attribute on *.dol, GBI, MCBACKUP, swiss using 'fatattr' (requires 'fatattr' in PATH)")
    ap.add_argument("--verbose", action="store_true", help="Print diagnostic details (e.g., asset names if no match)")
    args = ap.parse_args()

    sd_root = Path(args.sd_root)
    if not sd_root.is_dir():
        log(f"ERROR: SD root missing or not a directory: {sd_root}")
        sys.exit(2)

    device = args.device.lower().strip()
    if device != "picoboot":
        log(f"ERROR: unsupported device '{args.device}'. Only 'picoboot' is supported right now.")
        sys.exit(1)

    # Get release
    try:
        url = f"{API_BASE}/latest" if not args.tag else f"{API_BASE}/tags/{args.tag}"
        log(f"Querying GitHub API: {url}")
        rel = http_get_json(url)
    except Exception as e:
        log(f"ERROR: fetching release info failed: {e}")
        sys.exit(3)

    asset = pick_asset(rel.get("assets"), verbose=args.verbose)
    if not asset:
        log("ERROR: no suitable asset found (.tar.xz or .7z).")
        if args.verbose:
            log("TIP: Try specifying an explicit tag with --tag (e.g., --tag v0.6r1913)")
        sys.exit(4)
    log(f"Selected asset: {asset['name']} (rev {asset['rev']}, ext {asset['ext']})")

    with tempfile.TemporaryDirectory(prefix="swiss_fetch_") as tmp:
        tmp = Path(tmp)
        archive_path = tmp / asset["name"]
        if args.dry_run:
            log(f"(dry-run) would download: {asset['url']} -> {archive_path}")
        else:
            log(f"Downloading: {asset['url']}")
            download(asset["url"], str(archive_path))

        extract_root = tmp / "extracted"
        if not args.dry_run:
            os.makedirs(extract_root, exist_ok=True)
            if asset["ext"] == "tar.xz":
                extract_tar_xz(archive_path, extract_root)
            else:
                extract_7z(archive_path, extract_root)
        else:
            log(f"(dry-run) would extract {archive_path} into {extract_root}")

        rev = asset["rev"]
        dol_rel = f"swiss_r{rev}/DOL/swiss_r{rev}.dol"
        apploader_zip_rel = f"swiss_r{rev}/Apploader/EXTRACT_TO_ROOT.zip"

        if args.dry_run:
            log(f"(dry-run) would search for {dol_rel} and {apploader_zip_rel}")
        else:
            dol_file = find_member(extract_root, dol_rel)
            if not dol_file:
                log(f"ERROR: could not find {dol_rel} inside extracted asset")
                sys.exit(5)
            ipl_dest = sd_root / "ipl.dol"
            if ipl_dest.exists() and not args.force:
                log(f"ERROR: {ipl_dest} exists. Use --force to overwrite.")
                sys.exit(6)
            log(f"Installing IPL DOL: {dol_file} -> {ipl_dest}")
            os.makedirs(ipl_dest.parent, exist_ok=True)
            shutil.copy2(dol_file, ipl_dest)

            ap_zip = find_member(extract_root, apploader_zip_rel)
            if not ap_zip:
                log(f"ERROR: could not find {apploader_zip_rel} inside extracted asset")
                sys.exit(7)
            log(f"Extracting apploader payload: {ap_zip}")
            ap_out = tmp / "apploader"
            os.makedirs(ap_out, exist_ok=True)
            with zipfile.ZipFile(ap_zip, "r") as z:
                z.extractall(ap_out)

            src_swiss = ap_out / "swiss"
            dst_swiss = sd_root / "swiss"
            log(f"Merging {src_swiss} -> {dst_swiss}")
            merge_directories(src_swiss, dst_swiss, dry_run=False, overwrite=args.force)
            log(f"Expect: {dst_swiss / 'patches' / 'apploader.img'}")

        if args.hide_files:
            if fatattr_available():
                log("NOTICE: --hide-files requested: 'fatattr' detected in PATH.")
            else:
                log("NOTICE: --hide-files requested but 'fatattr' not found in PATH; skipping hide step.")
            set_hidden_attributes(sd_root, dry_run=args.dry_run)

    log("Done.")

if __name__ == "__main__":
    main()
