"""Plan a tidy-up, carry it out, and undo it.

Nothing is deleted or overwritten. A move to another drive copies the file, checks the copy byte
for byte, and only then removes the original."""
from __future__ import annotations

import errno
import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass

from .dates import file_date

KINDS = {
    "images": "jpg jpeg png gif webp heic heif avif tif tiff bmp svg dng cr2 cr3 nef arw raf",
    "video": "mp4 mov m4v mkv webm avi mts wmv",
    "audio": "wav mp3 m4a aac flac ogg opus aif aiff",
    "documents": "pdf doc docx odt rtf txt md csv xls xlsx ods ppt pptx key pages",
    "projects": "psd ai fig sketch xd blend aep prproj drp kdenlive afphoto afdesign",
    "archives": "zip 7z rar tar gz tgz",
}
KIND_OF = {ext: kind for kind, exts in KINDS.items() for ext in exts.split()}
# Downloads still in progress, and files the system writes for itself
PARTIAL = (".crdownload", ".part", ".partial", ".download", ".tmp")
SYSTEM = {"desktop.ini", "thumbs.db"}
LOG_PREFIX = "media-sorter-undo-"


@dataclass
class Move:
    src: str
    dst: str
    kind: str
    date: str
    date_from: str
    size: int
    duplicate_of: str = ""


def kind_of(name: str) -> str:
    return KIND_OF.get(os.path.splitext(name)[1].lower().lstrip("."), "other")


def skipped(name: str) -> bool:
    low = name.lower()
    return low.startswith(".") or low.endswith(PARTIAL) or low in SYSTEM or low.startswith(LOG_PREFIX)


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _files(root: str, recursive: bool, exclude: str | None):
    for folder, dirs, names in os.walk(root):
        if exclude:
            dirs[:] = [d for d in dirs if os.path.abspath(os.path.join(folder, d)) != exclude]
        if not recursive:
            dirs[:] = []
        dirs.sort()
        for n in sorted(names):
            yield os.path.join(folder, n)


def plan(src: str, dest: str, recursive: bool = False) -> tuple[list[Move], list[str]]:
    """What would move where. Reads the disk, changes nothing. Returns (moves, skipped files)."""
    src, dest = os.path.abspath(src), os.path.abspath(dest)
    found, skips = [], []
    for path in _files(src, recursive, dest):
        if skipped(os.path.basename(path)) or not os.path.isfile(path):
            skips.append(path)
        else:
            when, how = file_date(path)
            found.append((when, path, how))
    found.sort()  # oldest first, so the oldest copy of a file is the one kept as the original

    # Hash only files whose size matches another one: a different size can't be the same content.
    by_size: dict[int, list[str]] = {}
    existing = [p for p in _files(dest, True, None) if os.path.isfile(p)] if os.path.isdir(dest) else []
    for p in existing + [p for _, p, _ in found]:
        by_size.setdefault(os.path.getsize(p), []).append(p)
    hashes = {p: sha256(p) for group in by_size.values() if len(group) > 1 for p in group}
    owner = {}  # content hash -> the file that keeps its normal place
    for p in existing:
        if p in hashes:
            owner.setdefault(hashes[p], p)

    moves, taken = [], {os.path.normcase(p) for p in existing}
    for when, path, how in found:
        name, size = os.path.basename(path), os.path.getsize(path)
        original = owner.get(hashes.get(path, ""), "")
        if original:
            folder = os.path.join(dest, "duplicates", f"{when:%Y-%m}")
        else:
            folder = os.path.join(dest, kind_of(name), f"{when:%Y}", f"{when:%Y-%m}")
            if path in hashes:
                owner[hashes[path]] = path
        dst = _free_name(folder, name, taken)
        taken.add(os.path.normcase(dst))
        moves.append(Move(path, dst, "duplicates" if original else kind_of(name), f"{when:%Y-%m-%d}", how, size, original))
    return moves, skips


def _free_name(folder: str, name: str, taken: set) -> str:
    stem, ext = os.path.splitext(name)
    candidate, n = os.path.join(folder, name), 2
    while os.path.normcase(candidate) in taken or os.path.exists(candidate):
        candidate = os.path.join(folder, f"{stem} ({n}){ext}")
        n += 1
    return candidate


def move_file(src: str, dst: str) -> None:
    """Rename, or copy-verify-remove across drives. Refuses to replace anything."""
    if os.path.exists(dst):
        raise FileExistsError(dst)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        os.rename(src, dst)
    except OSError as e:
        if e.errno != errno.EXDEV:
            raise
        shutil.copy2(src, dst)
        if os.path.getsize(dst) != os.path.getsize(src) or sha256(dst) != sha256(src):
            os.remove(dst)  # our own bad copy; the original is untouched
            raise OSError(f"copy of {src} did not match, left it where it was")
        os.remove(src)  # only after the copy is proven identical


def _write_log(path: str, entries: list[dict]) -> None:
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(entries, fh, indent=1)
    os.replace(tmp, path)


def apply(moves: list[Move], dest: str, stamp: str) -> tuple[str, list[dict], list[str]]:
    """Carry out a plan. The undo log is rewritten after every move, so it is right even if this
    stops halfway. Returns (log path, done, problems)."""
    os.makedirs(dest, exist_ok=True)
    log = os.path.join(dest, f"{LOG_PREFIX}{stamp}.json")
    done, problems = [], []
    for m in moves:
        try:
            move_file(m.src, m.dst)
        except (OSError, FileExistsError) as e:
            problems.append(f"left {m.src} where it was: {e}")
            continue
        done.append(asdict(m))
        _write_log(log, done)
    if not done:
        _write_log(log, done)
    return log, done, problems


def undo(log: str, run: bool = False) -> tuple[list[tuple[str, str]], list[str]]:
    """Put files back where the log says they came from. Dry unless run=True."""
    with open(log, encoding="utf-8") as fh:
        entries = json.load(fh)
    back, problems = [], []
    for e in reversed(entries):
        if not os.path.isfile(e["dst"]):
            problems.append(f"{e['dst']} is gone, nothing to put back")
        elif os.path.getsize(e["dst"]) != e["size"]:
            problems.append(f"{e['dst']} changed since it was moved, left it")
        elif os.path.exists(e["src"]):
            problems.append(f"something is already at {e['src']}, left {e['dst']}")
        else:
            back.append((e["dst"], e["src"]))
    if run:
        for frm, to in back:
            move_file(frm, to)
    return back, problems
