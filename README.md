# Swiss GC Fetcher

A utility to streamline updates of [Swiss](https://github.com/emukidid/swiss-gc) on GameCube SD cards.  
It automatically downloads the latest (or a tagged) release asset, extracts the correct payloads, and installs them onto an SD card.

## Motivation

Updating Swiss manually requires downloading release archives, extracting the correct files, and merging folders.  
This script automates that process with a single command.

## Features

- Downloads the latest Swiss release asset from GitHub (prefers `.tar.xz`, falls back to `.7z`).
- Devices supported:
  - **picoboot**: installs `ipl.dol` and merges the Apploader payload.
  - **gcloader**: installs `boot.iso` from the GCLoader payload and merges the Apploader payload.
- Safe handling: for GCLoader, releases **v0.6r1695 through v0.6r1867 are blacklisted** due to a bricking risk (especially on GCLoader HW1). These will never be installed by this tool.
- Optional `--hide-files` flag: applies FAT hidden attributes with [`fatattr`](https://tracker.debian.org/pkg/fatattr).  
  - `fatattr` is packaged for Debian/Ubuntu and is also available in the [AUR](https://aur.archlinux.org/packages/fatattr).
- Safe by default: `--dry-run` for simulation, `--force` required to overwrite.

## Requirements

- Python 3.8+
- Network access to GitHub
- [`fatattr`](https://tracker.debian.org/pkg/fatattr) installed if using `--hide-files` (Debian/Ubuntu package or AUR)
- Optional: `7z`/`7za` if only `.7z` release assets are available

## Installation

```bash
git clone https://github.com/<your-username>/swiss-gc-fetcher.git
cd swiss-gc-fetcher
```

## Usage

Replace `/media/SDCARD` with the mount point of your SD card.

```bash
# Dry-run (no changes made)
python3 swiss_gc_fetcher.py --sd-root /media/SDCARD --device picoboot --dry-run

# Install latest Swiss Picoboot payload
python3 swiss_gc_fetcher.py --sd-root /media/SDCARD --device picoboot

# Install latest Swiss GCLoader payload (safe versions only)
python3 swiss_gc_fetcher.py --sd-root /media/SDCARD --device gcloader

# Use the previous official release (safe for your device)
python3 swiss_gc_fetcher.py --sd-root /media/SDCARD --device gcloader --previous-release

# Pin a specific tag
python3 swiss_gc_fetcher.py --sd-root /media/SDCARD --device picoboot --tag v0.6r1913

# Force overwrite existing files
python3 swiss_gc_fetcher.py --sd-root /media/SDCARD --device picoboot --force

# Hide sensitive files/folders (requires fatattr)
python3 swiss_gc_fetcher.py --sd-root /media/SDCARD --device picoboot --hide-files
```

## Options

- `--sd-root PATH` : SD card root mount point
- `--device NAME` : Target device (`picoboot` or `gcloader`)
- `--dry-run` : Show actions without making changes
- `--force` : Allow overwriting existing files
- `--hide-files` : Apply FAT hidden attribute via `fatattr`
- `--tag TAG` : Use a specific release tag instead of latest (e.g. `v0.6r1913`)
- `--previous-release` : Use the previous official release (skips drafts, prereleases, and blacklisted gcloader versions)
- `--verbose` : Print extra diagnostic details

## License

GPLv3 (see LICENSE).
