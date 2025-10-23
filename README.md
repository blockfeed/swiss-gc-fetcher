# Swiss GC Fetcher

A utility to streamline updates of [Swiss](https://github.com/emukidid/swiss-gc) on GameCube SD cards.  
It downloads the latest (or a tagged/previous) release asset, extracts the correct payloads, and installs them onto an SD card.

## Features

- Downloads the latest Swiss release asset from GitHub (prefers `.tar.xz`, falls back to `.7z`).
- Devices supported:
  - **picoboot**: installs `ipl.dol` and merges the Apploader payload.
  - **gcloader**: installs `boot.iso` from the GCLoader payload and merges the Apploader payload.
  - **picoloader**: extracts **GEKKOBOOT** from the Swiss release (`Picoloader/` folder) and installs **`/ipl.dol`** and the **`/swiss/`** folder (contains `apploader.img`).
- **Optional `--cubeboot` (picoboot only)**:
  - Fetches the latest [`cubeboot.dol`](https://github.com/OffBroadway/cubeboot) from OffBroadway/cubeboot.
  - Installs `cubeboot.dol` as `/ipl.dol` and Swiss as `/boot.dol`.
  - If `/cubeboot.ini` is missing at SD root, fetches it from the latest [cubeboot release](https://github.com/OffBroadway/cubeboot/releases) and installs it.
- **Safety (GCLoader)**: releases **v0.6r1695 through v0.6r1867 are blacklisted** due to a bricking risk (especially on **GCLoader HW1**). These will never be installed when using `--device gcloader`.
- **Hiding files**: `--hide-files` applies FAT hidden attributes to **`*.dol`, `*.ini`, `*.cli`, `GBI`, `MCBACKUP`, `swiss`** using [`fatattr`](https://tracker.debian.org/pkg/fatattr).  
  - `fatattr` is available via Debian/Ubuntu and also in the [AUR](https://aur.archlinux.org/packages/fatattr).
- Safe by default: `--dry-run` for simulation, `--force` required to overwrite.

## Requirements

- Python 3.8+
- Network access to GitHub
- [`fatattr`](https://tracker.debian.org/pkg/fatattr) installed if using `--hide-files` (Debian/Ubuntu package or AUR)
- Optional: `7z`/`7za` if only `.7z` release assets are available

## Installation

```bash
git clone https://github.com/blockfeed/swiss-gc-fetcher.git
cd swiss-gc-fetcher
```

## Usage

Replace `/media/SDCARD` with the mount point of your SD card.

```bash
# Dry-run (no writes) with extra diagnostics
python3 swiss_gc_fetcher.py --sd-root /media/SDCARD --device picoboot --dry-run --verbose

# Picoboot (Swiss -> /ipl.dol, merge Apploader)
python3 swiss_gc_fetcher.py --sd-root /media/SDCARD --device picoboot

# Picoboot + Cubeboot (cubeboot -> /ipl.dol, Swiss -> /boot.dol; ensure /cubeboot.ini exists)
python3 swiss_gc_fetcher.py --sd-root /media/SDCARD --device picoboot --cubeboot

# GCLoader (Swiss GCLoader payload -> /boot.iso; merge Apploader; blocks risky revisions)
python3 swiss_gc_fetcher.py --sd-root /media/SDCARD --device gcloader

# Picoloader (GEKKOBOOT: installs /ipl.dol and /swiss/ from the Picoloader package)
python3 swiss_gc_fetcher.py --sd-root /media/SDCARD --device picoloader

# Picoloader overwrite case (remove any existing boot.dol/ipl.dol)
python3 swiss_gc_fetcher.py --sd-root /media/SDCARD --device picoloader --force

# Use the previous official release instead of latest
python3 swiss_gc_fetcher.py --sd-root /media/SDCARD --device gcloader --previous-release

# Pin a specific Swiss tag
python3 swiss_gc_fetcher.py --sd-root /media/SDCARD --device picoboot --tag v0.6r1913

# Force overwrite existing files
python3 swiss_gc_fetcher.py --sd-root /media/SDCARD --device picoboot --force

# Hide files/folders (requires fatattr; hides *.dol, *.ini, *.cli, GBI, MCBACKUP, swiss)
python3 swiss_gc_fetcher.py --sd-root /media/SDCARD --device picoboot --hide-files
```

## Options

- `--sd-root PATH` : SD card root mount point
- `--device NAME` : Target device (`picoboot` or `gcloader`)
- `--cubeboot` : (picoboot only) install `cubeboot.dol` as `ipl.dol`, Swiss as `boot.dol`, fetch `cubeboot.ini` if missing
- `--dry-run` : Show actions without making changes
- `--force` : Allow overwriting existing files
- `--hide-files` : Apply FAT hidden attribute (**`*.dol`, `*.ini`, `*.cli`, `GBI`, `MCBACKUP`, `swiss`**) via `fatattr`
- `--tag TAG` : Use a specific Swiss release tag instead of latest (e.g. `v0.6r1913`)
- `--previous-release` : Use the previous official Swiss release (skips drafts, prereleases, and blacklisted GCLoader versions)
- `--verbose` : Print extra diagnostic details

## Notes

- **Picoloader specifics**:
  - `--device picoloader` will **not** accept `--cubeboot`; they are incompatible.
  - Picoloader expects `ipl.dol` at SD root and a `/swiss/` folder containing `apploader.img`.
    If `boot.dol` or `ipl.dol` already exist at SD root, pass `--force` (the tool will remove/replace them) or delete them manually before running.

- The tool blocks Swiss releases **v0.6r1695..v0.6r1867** when `--device gcloader` is selected, due to a **bricking risk** (reported particularly for **GCLoader HW1**). If you specify a blocked tag explicitly, the tool will exit with an error.
- When `--hide-files` is used, this tool requires `fatattr` in `PATH`. If it’s not found, the tool will log a notice and skip the hiding step.

## License

GPLv3 (see LICENSE).
