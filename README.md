# media-sorter

Tidy a folder of renders and downloads without losing anything.

It sorts files into `type/year/month`, finds duplicates by their bytes rather than their names,
and always shows you the plan first. Nothing moves until you add `--apply`. Every run writes an
undo log, nothing is ever deleted, and it never writes over a file that is already there.

Python 3.10+, standard library only, about 350 lines.

**Run it:**

```bash
python examples/demo.py                                 # sorts a made-up folder in a temp directory, then undoes it
python -m unittest discover -s tests -t .

python -m media_sorter ~/Downloads                      # the plan; nothing moves
python -m media_sorter ~/Downloads --apply              # do it (into ~/Downloads/sorted)
python -m media_sorter ~/Downloads --to ~/Media --recursive --apply
python -m media_sorter --undo ~/Downloads/sorted/media-sorter-undo-20261019-142325.json --apply
```

## How it works

```
every file in the folder (and subfolders with --recursive)
  │
  ├─ partial download, hidden or system file? ──────────────► left alone
  │
  ├─ date:  EXIF DateTimeOriginal (JPEG)  ─► else a date in the name  ─► else the modified time
  ├─ type:  by extension: images, video, audio, documents, projects, archives, other
  │
  ├─ oldest first. Same size as another file? hash both.
  │     same bytes as a file already placed ─► duplicates/<month>/
  │     otherwise                           ─► <type>/<year>/<year-month>/
  │     name taken by different bytes        ─► "name (2).ext"
  │
  └─ the plan is printed. With --apply: move, and rewrite the undo log after every move
```

The date rules and the EXIF reading, worked through by hand: [docs/explained.md](docs/explained.md).

## A worked example

`python examples/demo.py` builds a downloads folder of 14 files: renders, a voiceover, a brief, a
photo with EXIF data, two copies of one render under different names, two different files both
called `cover.png`, a half-finished download and a `.DS_Store`. The plan, shortened:

```
  IMG_4021.jpg                     -> images/2026/2026-03/IMG_4021.jpg           date from exif
  old/IMG_4021 copy.jpg            -> duplicates/2026-03/IMG_4021 copy.jpg       same bytes as IMG_4021.jpg
  Screenshot 2026-05-02 at ...png  -> images/2026/2026-05/Screenshot 2026-...    date from name
  brief.pdf                        -> documents/2026/2026-08/brief.pdf           date from modified
  render_final.mp4                 -> video/2026/2026-09/render_final.mp4        date from modified
  render_final (1).mp4             -> duplicates/2026-10/render_final (1).mp4    same bytes as render_final.mp4
  old/cover.png                    -> images/2026/2026-10/cover.png              date from modified
  cover.png                        -> images/2026/2026-10/cover (2).png          date from modified
  ...
  .DS_Store                           left alone
  big-render.mp4.crdownload           left alone
```

Twelve files move and two are left alone. The photo goes to March 2026, when it was taken, though
it was downloaded in October. The two renders with the same bytes are caught even though their
names differ, while `render_final_v2.mp4`, a different file, is not touched. The older `cover.png`
keeps the name. Then the demo runs the undo, and all twelve go back to where they were.

## What I learned

- **Plan, then apply.** A tidy-up that runs in one step will sooner or later put something where
  you didn't expect it. Printing the whole plan first costs nothing, and it is the one moment you
  can still say no.
- **A move across drives is a copy and a delete.** `os.rename` can't cross drives, and
  `shutil.move` falls back to copying and then removing the original without checking the copy.
  Here the copy is compared byte for byte before the original goes. A test fakes a bad copy and
  checks that the original is still there.
- **`os.rename` behaves differently on Windows and Linux.** On Windows it refuses to replace an
  existing file; on Linux it replaces it silently. So the "never overwrite" rule is an explicit
  check, and the test for it was proved red with `os.replace`, which overwrites everywhere.
- **Write the undo log as you go.** If the run stops halfway, a log written at the end is missing
  or wrong. This one is rewritten after every move, so it always matches what actually moved.

## Limits

- Dates come from EXIF only for JPEG. HEIC, RAW and video files use their name or modified time,
  and a modified time can be the day you downloaded the file, not the day it was made.
- Duplicates are exact byte copies. The same photo saved twice at different quality is two files.
- Undo puts files back but leaves the folders it made, empty. Delete those yourself if you want.
- It reads every file whose size matches another file's in full to hash it. For a folder of large
  videos with equal sizes that takes a while.

## Files

```
media_sorter/  sorter.py (plan, apply, undo)  dates.py (EXIF, names)  __main__.py
tests/         unittest in temp folders, fixtures.py builds the files including a real EXIF block
examples/      demo.py
docs/          explained.md, decisions.md
```

MIT licence. Copyright 2026 Shinabaze Ajiya.
