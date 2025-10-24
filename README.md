# Swiss GC Fetcher

Installs the latest (or a specific) Swiss release to an SD card for GameCube homebrew setups.

## Features
- Fetches latest (or `--tag`/`--previous-release`) Swiss from `emukidid/swiss-gc`.
- Devices:
  - **picoboot**: installs `ipl.dol` and merges Apploader payload.
  - **picoloader**: extracts GEKKOBOOT (Picoloader) to install `ipl.dol` and `swiss/`, then merges Apploader payload.
  - **gcloader**: installs `boot.iso` from the GCLoader package and merges Apploader payload.
- **Apploader is always refreshed**: removes `/swiss/patches/apploader.img` first, then merges new one.
- `--hide-files` uses `fatattr` to hide: **`*.dol`**, **`*.ini`**, **`*.cli`**, **`GBI`**, **`MCBACKUP`**, **`swiss`** (recursive).
- **Cubeboot** (OffBroadway) support for **picoboot** via `--cubeboot`.
- **Cubiboot** (makeo) support for **picoboot & picoloader** via `--cubiboot`:
  - Installs `cubiboot.dol` as `/ipl.dol` and places Swiss DOL as `/swiss-gc.dol`.
  - When `--cubiboot` is **not** passed on these devices, `/swiss-gc.dol` is removed before proceeding.

## Requirements
- Python 3.8+
- Internet access
- Optional: `py7zr` if you want to install from a `.7z` Swiss release asset (`pip install py7zr`)
- (optional) `fatattr` in PATH for `--hide-files`

## Install
No install required—run the script directly:
```bash
python3 swiss_gc_fetcher.py --help
```

## Usage
**Picoboot (standard):**
```bash
python3 swiss_gc_fetcher.py --sd-root /media/SDCARD --device picoboot
```

**Picoboot + CUBEBOOT (OffBroadway -> `/ipl.dol`, Swiss -> `/boot.dol`):**
```bash
python3 swiss_gc_fetcher.py --sd-root /media/SDCARD --device picoboot --cubeboot --force
```

**Picoboot + CUBIBOOT (makeo -> `/ipl.dol`, Swiss -> `/swiss-gc.dol`):**
```bash
python3 swiss_gc_fetcher.py --sd-root /media/SDCARD --device picoboot --cubiboot --force
```

**Picoloader (GEKKOBOOT -> `/ipl.dol` + `/swiss/`):**
```bash
python3 swiss_gc_fetcher.py --sd-root /media/SDCARD --device picoloader --force
```

**Picoloader + CUBIBOOT (makeo -> `/ipl.dol` + `/swiss-gc.dol`):**
```bash
python3 swiss_gc_fetcher.py --sd-root /media/SDCARD --device picoloader --cubiboot --force
```

**GCLoader (`/boot.iso`):**
```bash
python3 swiss_gc_fetcher.py --sd-root /media/SDCARD --device gcloader --force
```

**Hide files/folders (requires `fatattr`):**
```bash
python3 swiss_gc_fetcher.py --sd-root /media/SDCARD --device picoboot --hide-files
```

**Pinned release:**
```bash
python3 swiss_gc_fetcher.py --sd-root /media/SDCARD --device picoboot --tag v0.6r1913
# or previous official: --previous-release
```

## Behavior details
- **Mutual exclusivity**: `--cubeboot` and `--cubiboot` cannot be used together.
- **gcloader**: both `--cubeboot` and `--cubiboot` are ignored with a notice.
- **Overwrite**: pass `--force` to replace existing `/ipl.dol`, `/boot.dol`, `/boot.iso`, `/swiss-gc.dol`.
- **Apploader**: The script deletes `/swiss/patches/apploader.img` and merges the new Apploader payload every run.
- **Overwrite errors**: re-run with `--force` or remove the files manually.

## License
GPLv3 (same as upstream tooling).
