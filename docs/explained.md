# How it decides, worked by hand

## Which date

A file has three possible dates, tried in this order:

1. **EXIF `DateTimeOriginal`**, for JPEG photos: when the camera or phone took the picture. It
   survives copying, downloading and emailing, which is why it comes first.
2. **A date in the name**, like `IMG_20260314_101500.jpg` or `Screenshot 2026-05-02 at
   09.41.12.png`. Many apps put the creation date there. A name date must be a real date:
   `20261340` (month 13) and `20260231` (31 February) are ignored, and digits that run on into
   other digits (`1202603141`) don't count.
3. **The modified time** from the file system. It is always there, and often it is just the moment
   the file was downloaded or copied.

So a photo taken on 14 March and downloaded on 1 October is filed under March: its EXIF wins over
its modified time.

## Reading EXIF without a library

A JPEG is a list of segments. Each one starts with `FF`, a marker byte and a two-byte length:

```
FF D8                      start of image
FF E1  00 48  "Exif\0\0"   APP1: the EXIF block, 0x48 bytes long (this length counts its own two bytes)
   ... TIFF data ...
FF DB  ...                 other segments
FF DA  ...                 the picture itself; EXIF is always before this
```

Inside APP1 is a small TIFF file:

```
offset  bytes            meaning
0       49 49            "II": numbers are little-endian ("MM" would mean big-endian)
2       2A 00            42, the TIFF magic number
4       08 00 00 00      the first directory (IFD0) starts at offset 8
8       01 00            IFD0 has 1 entry
10      69 87 04 00      tag 0x8769 "EXIF IFD", type 4 (a 32-bit number)
14      01 00 00 00      count 1
18      1A 00 00 00      value: the EXIF directory is at offset 26
...
26      01 00            the EXIF directory has 1 entry
28      03 90 02 00      tag 0x9003 "DateTimeOriginal", type 2 (text)
32      14 00 00 00      20 bytes long, too long to fit in the entry...
36      2C 00 00 00      ...so it is at offset 44
44      "2026:03:14 10:15:00\0"
```

That is exactly the file `tests/fixtures.py` builds. `dates.py` walks it in the same order: find
APP1, read the byte order, follow the pointer from IFD0 to the EXIF directory, find tag 0x9003,
follow its offset, read 20 bytes. Any read that runs off the end returns "no date" rather than an
error.

## Which files are duplicates

Hashing every file would mean reading every byte of every video. Two files can only be identical
if they are the same size, so sizes come first:

| File | Size | Hashed? |
|---|---|---|
| render_final.mp4 | 2,012 | yes, another file is 2,012 bytes |
| render_final (1).mp4 | 2,012 | yes |
| render_final_v2.mp4 | 2,026 | no, nothing else is 2,026 bytes |

Only the two 2,012-byte files get a SHA-256, and their hashes match. Files are taken oldest first,
so `render_final.mp4` (30 September) keeps the normal place and `render_final (1).mp4`
(1 October) goes to `duplicates/2026-10/`. Files already in the destination count too, so running
it again on new downloads catches a copy of something sorted last week.

## Never overwrite, never lose

Before each move: if anything already has the target name, the file stays where it was and the
run reports it. Within one plan, names already given out are tracked, so two different
`cover.png` files become `cover.png` and `cover (2).png`.

A move on the same drive is a rename: instant, and the bytes never move. A move to another drive
is a copy, a byte-for-byte comparison, and only then the removal of the original. If the copy
doesn't match, the copy is removed and the original stays.

## Undo

The log is a JSON list of every move: where from, where to, and the size. Undo walks it backwards
and moves each file back, unless:

- the file is no longer where the log says,
- its size has changed (someone edited it after sorting), or
- something new now has its old name.

Those are reported and left alone. Like the sort, undo prints its plan and only acts with
`--apply`.
