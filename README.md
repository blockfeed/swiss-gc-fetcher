# Swiss GC Fetcher

A small utility to streamline updates of [Swiss](https://github.com/emukidid/swiss-gc) on GameCube SD cards.  
It automatically downloads the latest (or a tagged) release asset, extracts the Picoboot payload, and installs it onto an SD card.

## Motivation

Keeping Swiss up to date manually requires downloading release archives, extracting the correct files, and merging folders.  
This script automates that process with a single command.

## Features

- Downloads the latest Swiss release asset from GitHub (prefers `.tar.xz`, falls back to `.7z`).
- Extracts and installs the Picoboot payload:
  - Places `ipl.dol` at the root of the SD card.
  - Merges the `swiss/` folder from the Apploader payload.
- Optional `--hide-files` flag: applies FAT hidden attributes with `fatattr`.
- Safe by default: `--dry-run` for simulation, `--force` required to overwrite.

## Requirements

- Python 3.8+
- Network access to GitHub
- `fatattr` installed if using `--hide-files`
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

# Force overwrite existing files
python3 swiss_gc_fetcher.py --sd-root /media/SDCARD --device picoboot --force

# Hide sensitive files/folders (requires fatattr)
python3 swiss_gc_fetcher.py --sd-root /media/SDCARD --device picoboot --hide-files
```

## Options

- `--sd-root PATH` : SD card root mount point
- `--device NAME` : Target device (currently only `picoboot` supported)
- `--dry-run` : Show actions without making changes
- `--force` : Allow overwriting existing files
- `--hide-files` : Apply FAT hidden attribute via `fatattr`
- `--tag TAG` : Use a specific release tag instead of latest (e.g. `v0.6r1913`)

## License

GPLv3 (see LICENSE).
