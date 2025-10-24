#!/usr/bin/env python3
"""
Swiss GC Fetcher (clean, tested build)

Devices:
  - picoboot: install IPL (ipl.dol) + Apploader; supports --cubeboot (OffBroadway) and --cubiboot (makeo).
  - picoloader: extract GEKKOBOOT to provide ipl.dol + swiss/, then refresh Apploader; supports --cubiboot.
  - gcloader: install boot.iso from GCLoader zip + Apploader; ignores --cubeboot/--cubiboot.

Always refreshes Apploader: removes /swiss/patches/apploader.img then merges the new payload (overwrite).
Hide step supports: *.dol, *.ini, *.cli, GBI, MCBACKUP, swiss.

Notes:
- --cubeboot: picoboot only → cubeboot.dol -> /ipl.dol, Swiss -> /boot.dol, cubeboot.ini if missing.
- --cubiboot: picoboot & picoloader → cubiboot.dol -> /ipl.dol, Swiss -> /swiss-gc.dol.
  If --cubiboot is NOT used on these devices, /swiss-gc.dol is removed before proceeding.
"""

import argparse
from pathlib import Path
import os, sys, shutil, json, zipfile, tarfile, urllib.request, urllib.error, tempfile, subprocess, warnings
import re as _re

# Suppress non-critical noise (user requested)
warnings.filterwarnings("ignore", category=DeprecationWarning)

GITHUB_API = "https://api.github.com"
SWISS_REPO = "emukidid/swiss-gc"
CUBEBOOT_REPO = "OffBroadway/cubeboot"
CUBIBOOT_REPO = "makeo/cubiboot"

def log(msg: str):
    print(msg, flush=True)

def http_get_json(url: str):
    req = urllib.request.Request(url, headers={"Accept":"application/vnd.github+json","User-Agent":"swiss-gc-fetcher"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode("utf-8"))

def download(url: str, dest: Path):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent":"swiss-gc-fetcher"})
    with urllib.request.urlopen(req) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)
    return dest

def choose_release_asset(tag: str|None, previous: bool):
    if tag:
        rel = http_get_json(f"{GITHUB_API}/repos/{SWISS_REPO}/releases/tags/{tag}")
    else:
        rels = http_get_json(f"{GITHUB_API}/repos/{SWISS_REPO}/releases")
        rels = [r for r in rels if not r.get("draft") and not r.get("prerelease")]
        rels.sort(key=lambda r: r.get("created_at",""), reverse=True)
        rel = rels[1] if previous and len(rels) > 1 else rels[0]
    assets = rel.get("assets") or []
    tarxz = next((a for a in assets if str(a.get("name","")).endswith(".tar.xz")), None)
    sevenz = next((a for a in assets if str(a.get("name","")).endswith(".7z")), None)
    chosen = tarxz or sevenz
    if not chosen:
        raise RuntimeError("No supported Swiss assets (.tar.xz or .7z) found in the selected release.")
    return rel, chosen

def extract_archive(archive_path: Path, dest: Path):
    dest.mkdir(parents=True, exist_ok=True)
    name = archive_path.name.lower()
    if name.endswith(".tar.xz") or name.endswith(".txz") or name.endswith(".tar"):
        # Use filter="data" when available (Python 3.12+) to silence the 3.14 warning and be safe by default
        with tarfile.open(archive_path, "r:*") as tf:
            try:
                tf.extractall(dest, filter="data")
            except TypeError:
                # Older Python without filter= support
                tf.extractall(dest)
        return
    if name.endswith(".7z"):
        try:
            import py7zr
        except ImportError:
            raise RuntimeError("This asset is .7z; please 'pip install py7zr' or fetch a .tar.xz release.")
        with py7zr.SevenZipFile(archive_path, mode='r') as z:
            z.extractall(path=dest)
        return
    raise RuntimeError(f"Unsupported archive format: {archive_path.name}")

def find_member(root: Path, rel: str) -> Path|None:
    # First try exact/case-sensitive
    p = (root / rel)
    if p.exists():
        return p
    # Fallback: case-insensitive suffix match
    rel_norm = rel.replace("\\","/").lower()
    for cand in root.rglob("*"):
        if cand.as_posix().lower().endswith(rel_norm):
            return cand
    return None

def merge_directories(src: Path, dst: Path, overwrite: bool):
    for root, dirs, files in os.walk(src):
        rel = Path(root).relative_to(src)
        outdir = dst / rel
        outdir.mkdir(parents=True, exist_ok=True)
        for fn in files:
            s = Path(root) / fn
            d = outdir / fn
            if d.exists() and not overwrite:
                continue
            shutil.copy2(s, d)

def fatattr_available() -> bool:
    from shutil import which
    return which("fatattr") is not None

def hide_matching(sd_root: Path):
    patterns = ["*.dol", "*.ini", "*.cli", "GBI", "MCBACKUP", "swiss"]
    for pattern in patterns:
        for p in sd_root.rglob(pattern):
            try:
                subprocess.run(["fatattr","+h",str(p)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                # Non-critical: skip failures silently as requested
                pass

def fetch_cubeboot_asset(temp_dir: Path, name_exact: str, ext: str=".dol") -> Path:
    rel = http_get_json(f"{GITHUB_API}/repos/{CUBEBOOT_REPO}/releases/latest")
    assets = rel.get("assets") or []
    asset = next((a for a in assets if str(a.get("name","")).lower() == name_exact.lower()), None)
    if not asset:
        asset = next((a for a in assets if str(a.get("name","")).lower().endswith(ext)), None)
    if not asset:
        raise RuntimeError(f"Could not find {name_exact} in {CUBEBOOT_REPO} latest release.")
    url = asset.get("browser_download_url")
    dest = Path(temp_dir) / name_exact
    download(url, dest)
    return dest

def fetch_cubiboot_asset(temp_dir: Path, name_exact: str="cubiboot.dol") -> Path:
    rel = http_get_json(f"{GITHUB_API}/repos/{CUBIBOOT_REPO}/releases/latest")
    assets = rel.get("assets") or []
    asset = next((a for a in assets if str(a.get("name","")).lower() == name_exact.lower()), None)
    if not asset:
        asset = next((a for a in assets if str(a.get("name","")).lower().endswith(".dol")), None)
    if not asset:
        raise RuntimeError(f"Could not find {name_exact} in {CUBIBOOT_REPO} latest release.")
    url = asset.get("browser_download_url")
    dest = Path(temp_dir) / name_exact
    download(url, dest)
    return dest

def main():
    ap = argparse.ArgumentParser(
        description=("Fetch Swiss release asset and install payload(s) to an SD card. "
                     "Devices: picoboot (ipl.dol + Apploader), picoloader (GEKKOBOOT + Apploader), "
                     "gcloader (boot.iso + Apploader)."),
    )
    ap.add_argument("--sd-root", required=True, help="SD card root path (e.g. /media/SDCARD)")
    ap.add_argument("--device", required=True, choices=["picoboot","picoloader","gcloader"],
                    help="Target device. gcloader ignores --cubeboot/--cubiboot.")
    ap.add_argument("--dry-run", action="store_true", help="Print actions without writing")
    ap.add_argument("--tag", help="Release tag to use (e.g. v0.6r1957). Overrides --previous-release")
    ap.add_argument("--previous-release", action="store_true", help="Use the previous official release")
    ap.add_argument("--force", action="store_true", help="Overwrite existing files")
    ap.add_argument("--hide-files", action="store_true", help="Set FAT hidden attribute on *.dol, *.ini, *.cli, GBI, MCBACKUP, swiss using 'fatattr'")
    ap.add_argument("--verbose", action="store_true", help="More logging")
    ap.add_argument("--cubeboot", action="store_true",
                    help="Also install OffBroadway/cubeboot (picoboot only): cubeboot.dol->/ipl.dol, Swiss->/boot.dol (+cubeboot.ini). Ignored for picoloader/gcloader.")
    ap.add_argument("--cubiboot", action="store_true",
                    help="Use makeo/cubiboot (picoboot & picoloader): cubiboot.dol->/ipl.dol, Swiss->/swiss-gc.dol. "
                         "If not set on these devices, /swiss-gc.dol is removed before proceeding.")
    args = ap.parse_args()

    sd_root = Path(args.sd_root)
    if not sd_root.exists():
        if args.dry_run:
            log(f"(dry-run) would create SD root {sd_root}")
        else:
            sd_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        # Fetch Swiss asset
        rel, asset = choose_release_asset(args.tag, args.previous_release)
        tag = (rel.get("tag_name") or "").strip()

        asset_url = asset.get("browser_download_url")
        asset_path = tmp / asset.get("name")
        log(f"Downloading Swiss asset: {asset_url}")
        if not args.dry_run:
            download(asset_url, asset_path)

        extract_root = tmp / "extract"
        if args.dry_run:
            log(f"(dry-run) would extract to {extract_root}")
        else:
            extract_archive(asset_path, extract_root)

        # Detect top-level swiss_r<rev> directory and numeric rev
        rev_dir_name = None
        if extract_root.exists():
            for child in extract_root.iterdir():
                name = child.name
                if child.is_dir() and name.lower().startswith('swiss_r'):
                    rev_dir_name = name  # e.g., 'swiss_r1957'
                    break
        rev = None
        if not rev_dir_name:
            m = _re.search(r'r(\d+)', tag)
            if m:
                rev = m.group(1)
                rev_dir_name = f"swiss_r{rev}"
        else:
            m = _re.search(r'swiss_r(\d+)', rev_dir_name, _re.IGNORECASE)
            if m:
                rev = m.group(1)
        if not rev or not rev_dir_name:
            raise SystemExit("ERROR: could not determine Swiss revision from extracted asset or tag")

        # Common: always refresh Apploader (remove destination img first)
        apploader_zip_rel = f"{rev_dir_name}/Apploader/EXTRACT_TO_ROOT.zip"
        if args.dry_run:
            log(f"(dry-run) would extract {apploader_zip_rel} and merge into {sd_root / 'swiss'}")
        else:
            ap_zip = find_member(extract_root, apploader_zip_rel)
            if not ap_zip:
                raise SystemExit(f"ERROR: could not find {apploader_zip_rel} inside extracted asset")
            log(f"Extracting Apploader payload: {ap_zip}")
            ap_out = tmp / "apploader"
            ap_out.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(ap_zip, "r") as z:
                z.extractall(ap_out)
            src_swiss = ap_out / "swiss"
            dst_swiss = sd_root / "swiss"
            dst_apploader = dst_swiss / "patches" / "apploader.img"
            if dst_apploader.exists():
                try:
                    log(f"Removing existing apploader: {dst_apploader}")
                    dst_apploader.unlink()
                except Exception as e:
                    log(f"WARNING: failed to remove {dst_apploader}: {e}")
            log(f"Merging {src_swiss} -> {dst_swiss} (overwrite apploader)")
            merge_directories(src_swiss, dst_swiss, overwrite=True)

        # Swiss DOL path
        dol_rel = f"{rev_dir_name}/DOL/swiss_r{rev}.dol"
        dol_file = find_member(extract_root, dol_rel)
        if not dol_file:
            raise SystemExit(f"ERROR: could not find {dol_rel} inside extracted asset")

        # Per-device flow
        if args.device == "picoboot":
            if args.cubeboot and args.cubiboot:
                raise SystemExit("ERROR: --cubeboot and --cubiboot are mutually exclusive.")

            if args.cubeboot:
                if args.dry_run:
                    log("(dry-run) would fetch OffBroadway/cubeboot cubeboot.dol (+ini)")
                else:
                    cb_path = fetch_cubeboot_asset(tmp, "cubeboot.dol", ".dol")
                    ipl_dest = sd_root / "ipl.dol"
                    if ipl_dest.exists() and not args.force:
                        raise SystemExit(f"ERROR: {ipl_dest} exists. Use --force to overwrite.")
                    boot_dol_dest = sd_root / "boot.dol"
                    if boot_dol_dest.exists() and not args.force:
                        raise SystemExit(f"ERROR: {boot_dol_dest} exists. Use --force to overwrite.")
                    log(f"Installing cubeboot -> {ipl_dest}")
                    shutil.copy2(cb_path, ipl_dest)
                    log(f"Installing Swiss DOL -> {boot_dol_dest}")
                    shutil.copy2(dol_file, boot_dol_dest)
                    ini_dest = sd_root / "cubeboot.ini"
                    if not ini_dest.exists():
                        try:
                            ini_path = fetch_cubeboot_asset(tmp, "cubeboot.ini", ".ini")
                            log(f"Installing cubeboot.ini -> {ini_dest}")
                            shutil.copy2(ini_path, ini_dest)
                        except Exception as e:
                            log(f"WARNING: could not fetch cubeboot.ini: {e}")
            elif args.cubiboot:
                if args.dry_run:
                    log("(dry-run) would fetch makeo/cubiboot cubiboot.dol")
                else:
                    cbi_path = fetch_cubiboot_asset(tmp)
                    ipl_dest = sd_root / "ipl.dol"
                    if ipl_dest.exists() and not args.force:
                        raise SystemExit(f"ERROR: {ipl_dest} exists. Use --force to overwrite.")
                    sgc_dest = sd_root / "swiss-gc.dol"
                    if sgc_dest.exists() and not args.force:
                        raise SystemExit(f"ERROR: {sgc_dest} exists. Use --force to overwrite.")
                    log(f"Installing cubiboot -> {ipl_dest}")
                    shutil.copy2(cbi_path, ipl_dest)
                    log(f"Installing Swiss DOL -> {sgc_dest}")
                    shutil.copy2(dol_file, sgc_dest)
            else:
                # ensure swiss-gc.dol is removed when not using cubiboot
                sgc = sd_root / "swiss-gc.dol"
                if not args.dry_run and sgc.exists():
                    try:
                        log(f"Removing stale swiss-gc.dol: {sgc}")
                        sgc.unlink()
                    except Exception as e:
                        log(f"WARNING: failed to remove {sgc}: {e}")
                ipl_dest = sd_root / "ipl.dol"
                if ipl_dest.exists() and not args.force:
                    raise SystemExit(f"ERROR: {ipl_dest} exists. Use --force to overwrite.")
                if args.dry_run:
                    log(f"(dry-run) would install IPL DOL -> {ipl_dest}")
                else:
                    shutil.copy2(dol_file, ipl_dest)

        elif args.device == "picoloader":
            if args.cubeboot:
                log("NOTICE: --cubeboot is ignored for --device picoloader (use --cubiboot instead).")
            # Find the GEKKOBOOT EXTRACT_TO_ROOT.zip under */PicoLoader/*/gekkoboot/
            gkb_zip = None
            for cand in extract_root.rglob("*"):
                if cand.is_dir() and "pico" in cand.name.lower() and "loader" in cand.name.lower():
                    for zc in cand.rglob("gekkoboot"):
                        if zc.is_dir():
                            for zf in zc.glob("*.zip"):
                                if "extract_to_root" in zf.name.lower():
                                    gkb_zip = zf
                                    break
                        if gkb_zip:
                            break
                if gkb_zip:
                    break
            if args.dry_run:
                log(f"(dry-run) would extract GEKKOBOOT zip: {gkb_zip or 'NOT FOUND'}")
            else:
                if not gkb_zip or not gkb_zip.exists():
                    raise SystemExit("ERROR: Could not locate GEKKOBOOT EXTRACT_TO_ROOT.zip under PicoLoader.")
                log(f"Extracting Picoloader GEKKOBOOT payload: {gkb_zip}")
                out = tmp / "picoloader"
                out.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(gkb_zip, "r") as z:
                    z.extractall(out)
                ipl_src = next((p for p in out.rglob("ipl.dol") if p.is_file()), None)
                swiss_src = next((p for p in out.rglob("swiss") if p.is_dir()), None)
                if not ipl_src or not swiss_src:
                    raise SystemExit("ERROR: GEKKOBOOT payload missing ipl.dol or swiss/ directory.")
                # delete any existing boot.dol or ipl.dol as per convention when overwriting
                for f in (sd_root / "boot.dol", sd_root / "ipl.dol"):
                    if f.exists():
                        if not args.force:
                            raise SystemExit(f"ERROR: {f} exists. Use --force to overwrite/remove.")
                        log(f"Removing existing file: {f}")
                        f.unlink()
                log(f"Installing Picoloader IPL: {ipl_src} -> {sd_root / 'ipl.dol'}")
                shutil.copy2(ipl_src, sd_root / "ipl.dol")
                log(f"Merging {swiss_src} -> {sd_root / 'swiss'}")
                merge_directories(swiss_src, sd_root / "swiss", overwrite=True)

            # cubiboot handling (after GEKKOBOOT merge)
            if args.cubiboot and not args.dry_run:
                cbi_path = fetch_cubiboot_asset(tmp)
                ipl_dest = sd_root / "ipl.dol"
                if ipl_dest.exists() and not args.force:
                    raise SystemExit(f"ERROR: {ipl_dest} exists. Use --force to overwrite.")
                sgc_dest = sd_root / "swiss-gc.dol"
                if sgc_dest.exists() and not args.force:
                    raise SystemExit(f"ERROR: {sgc_dest} exists. Use --force to overwrite.")
                log(f"Installing cubiboot -> {ipl_dest}")
                shutil.copy2(cbi_path, ipl_dest)
                log(f"Installing Swiss DOL -> {sgc_dest}")
                shutil.copy2(dol_file, sgc_dest)
            elif not args.cubiboot and not args.dry_run:
                # ensure swiss-gc.dol is removed when not using cubiboot
                sgc = sd_root / "swiss-gc.dol"
                if sgc.exists():
                    try:
                        log(f"Removing stale swiss-gc.dol: {sgc}")
                        sgc.unlink()
                    except Exception as e:
                        log(f"WARNING: failed to remove {sgc}: {e}")

        elif args.device == "gcloader":
            if args.cubeboot:
                log("NOTICE: --cubeboot is ignored for --device gcloader (no DOL boot at SD root).")
            if args.cubiboot:
                log("NOTICE: --cubiboot is ignored for --device gcloader (no DOL boot at SD root).")
            gcl_zip_rel = f"{rev_dir_name}/GCLoader/EXTRACT_TO_ROOT.zip"
            if args.dry_run:
                log(f"(dry-run) would extract {gcl_zip_rel} and install /boot.iso")
            else:
                gcl_zip = find_member(extract_root, gcl_zip_rel)
                if not gcl_zip:
                    raise SystemExit(f"ERROR: could not find {gcl_zip_rel} inside extracted asset")
                out = tmp / "gcloader"
                out.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(gcl_zip, "r") as z:
                    z.extractall(out)
                boot_iso = next((p for p in out.rglob("boot.iso")), None)
                if not boot_iso:
                    raise SystemExit("ERROR: GCLoader EXTRACT_TO_ROOT.zip did not contain boot.iso")
                dest = sd_root / "boot.iso"
                if dest.exists() and not args.force:
                    raise SystemExit(f"ERROR: {dest} exists. Use --force to overwrite.")
                log(f"Installing GCLoader boot.iso: {boot_iso} -> {dest}")
                shutil.copy2(boot_iso, dest)

        # Hide files/folders if requested
        if args.hide_files:
            if fatattr_available():
                log("NOTICE: --hide-files requested: 'fatattr' detected in PATH.")
                if not args.dry_run:
                    hide_matching(sd_root)
            else:
                log("NOTICE: --hide-files requested but 'fatattr' not found in PATH; skipping hide step.")

    log("Done.")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        # Quiet exit per user's preference
        sys.exit(130)
