"""When was a file made? From its EXIF data, then its name, then its modified time."""
from __future__ import annotations

import os
import re
from datetime import datetime

# 2026-03-14, 2026_03_14, 20260314: as in IMG_20260314_101500.jpg or "Screenshot 2026-03-14 at 10.15.00.png"
NAME_DATE = re.compile(r"(?<!\d)((?:19|20)\d\d)[-_.]?(0[1-9]|1[0-2])[-_.]?(0[1-9]|[12]\d|3[01])(?!\d)")


def file_date(path: str) -> tuple[datetime, str]:
    """(date, where it came from): "exif", "name" or "modified"."""
    if path.lower().endswith((".jpg", ".jpeg")):
        taken = exif_date(path)
        if taken:
            return taken, "exif"
    named = name_date(os.path.basename(path))
    if named:
        return named, "name"
    return datetime.fromtimestamp(os.path.getmtime(path)), "modified"


def name_date(name: str) -> datetime | None:
    for m in NAME_DATE.finditer(name):
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:  # 2026-02-31 looks like a date and isn't one
            continue
    return None


def exif_date(path: str) -> datetime | None:
    """DateTimeOriginal from a JPEG's EXIF block (or DateTime if that is all there is)."""
    try:
        with open(path, "rb") as fh:
            data = fh.read(256 * 1024)  # EXIF sits in the first segments; no need to read the picture
        if data[:2] != b"\xff\xd8":
            return None
        i = 2
        while i + 4 <= len(data) and data[i] == 0xFF:
            marker = data[i + 1]
            if marker in (0xD9, 0xDA):  # end of image, start of the picture data
                return None
            size = int.from_bytes(data[i + 2:i + 4], "big")
            if marker == 0xE1 and data[i + 4:i + 10] == b"Exif\x00\x00":
                return _tiff_date(data[i + 10:i + 2 + size])
            i += 2 + size
    except (OSError, IndexError, ValueError):
        pass
    return None


def _tiff_date(t: bytes) -> datetime | None:
    order = {b"II": "little", b"MM": "big"}.get(t[:2])
    if not order:
        return None
    u16 = lambda o: int.from_bytes(t[o:o + 2], order)  # noqa: E731
    u32 = lambda o: int.from_bytes(t[o:o + 4], order)  # noqa: E731

    def entries(offset):
        for k in range(u16(offset)):
            p = offset + 2 + 12 * k
            yield u16(p), u32(p + 4), p + 8  # tag, count, where the value (or its offset) is

    def text(count, at):
        start = u32(at) if count > 4 else at
        return t[start:start + count].split(b"\x00")[0].decode("ascii")

    found = {}
    exif_ifd = None
    for tag, count, at in entries(u32(4)):
        if tag == 0x8769:
            exif_ifd = u32(at)
        elif tag == 0x0132:
            found["DateTime"] = text(count, at)
    if exif_ifd:
        for tag, count, at in entries(exif_ifd):
            if tag == 0x9003:
                found["DateTimeOriginal"] = text(count, at)
    for key in ("DateTimeOriginal", "DateTime"):
        try:
            return datetime.strptime(found[key], "%Y:%m:%d %H:%M:%S")
        except (KeyError, ValueError):
            continue
    return None
