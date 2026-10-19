"""Test files built in code: a JPEG with a real EXIF block, and a messy downloads folder."""
import os
from datetime import datetime


def jpeg_with_exif(taken: str, order: str = "II") -> bytes:
    """A tiny JPEG whose EXIF says it was taken at `taken` ("2026:03:14 10:15:00").

    Layout of the TIFF block inside the APP1 segment (offsets from its start):
      0   "II" or "MM", 42, offset of IFD0 (8)
      8   IFD0: 1 entry, tag 0x8769 = offset of the EXIF IFD (26)
      26  EXIF IFD: 1 entry, tag 0x9003 DateTimeOriginal, ASCII, 20 bytes at offset 44
      44  "2026:03:14 10:15:00\\0"
    """
    e = "little" if order == "II" else "big"
    p16 = lambda v: v.to_bytes(2, e)  # noqa: E731
    p32 = lambda v: v.to_bytes(4, e)  # noqa: E731
    date = taken.encode("ascii") + b"\x00"
    tiff = order.encode() + p16(42) + p32(8)
    tiff += p16(1) + p16(0x8769) + p16(4) + p32(1) + p32(26) + p32(0)
    tiff += p16(1) + p16(0x9003) + p16(2) + p32(len(date)) + p32(44) + p32(0)
    tiff += date
    app1 = b"Exif\x00\x00" + tiff
    return b"\xff\xd8\xff\xe1" + (len(app1) + 2).to_bytes(2, "big") + app1 + b"\xff\xd9"


def write(path: str, data, when: datetime | None = None) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data if isinstance(data, bytes) else data.encode())
    if when:
        os.utime(path, (when.timestamp(), when.timestamp()))
    return path


def make_mess(root: str) -> None:
    """A made-up downloads folder after a few weeks of renders and exports."""
    render = b"\x00\x00\x00\x18ftypmp42" + b"frame" * 400
    j = os.path.join
    write(j(root, "IMG_4021.jpg"), jpeg_with_exif("2026:03:14 10:15:00"), datetime(2026, 10, 1, 9, 0))
    write(j(root, "Screenshot 2026-05-02 at 09.41.12.png"), b"\x89PNG screenshot", datetime(2026, 10, 1, 9, 5))
    write(j(root, "render_final.mp4"), render, datetime(2026, 9, 30, 18, 0))
    write(j(root, "render_final (1).mp4"), render, datetime(2026, 10, 1, 8, 0))
    write(j(root, "render_final_v2.mp4"), render + b"one more frame", datetime(2026, 10, 2, 11, 0))
    write(j(root, "voiceover_take3.wav"), b"RIFF....WAVEfmt take three", datetime(2026, 10, 3, 14, 30))
    write(j(root, "brief.pdf"), b"%PDF-1.7 the brief", datetime(2026, 8, 12, 10, 0))
    write(j(root, "scene.blend"), b"BLENDER scene", datetime(2026, 9, 28, 20, 0))
    write(j(root, "textures.zip"), b"PK textures", datetime(2026, 9, 28, 20, 5))
    write(j(root, "cover.png"), b"\x89PNG cover, final", datetime(2026, 10, 2, 16, 0))
    write(j(root, "old", "cover.png"), b"\x89PNG cover, first try", datetime(2026, 10, 2, 9, 0))
    write(j(root, "old", "IMG_4021 copy.jpg"), jpeg_with_exif("2026:03:14 10:15:00"), datetime(2026, 10, 5, 9, 0))
    write(j(root, "big-render.mp4.crdownload"), b"half a download", datetime(2026, 10, 3, 9, 0))
    write(j(root, ".DS_Store"), b"\x00\x00\x00\x01Bud1", datetime(2026, 10, 3, 9, 0))
