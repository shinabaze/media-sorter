"""
python -m media_sorter SRC [--to DEST] [--recursive] [--apply] [--json]
python -m media_sorter --undo DEST/media-sorter-undo-<time>.json [--apply]

Without --apply nothing moves: you see the plan. DEST defaults to SRC/sorted.
"""
import argparse
import json
import os
import sys
from collections import Counter
from dataclasses import asdict
from datetime import datetime

from .sorter import apply, plan, undo


def _rel(path, base):
    return os.path.relpath(path, base).replace(os.sep, "/")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m media_sorter", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", nargs="?", help="the folder to tidy")
    ap.add_argument("--to", dest="dest", help="where sorted files go (default: SRC/sorted)")
    ap.add_argument("--recursive", action="store_true", help="also sort files in subfolders")
    ap.add_argument("--apply", action="store_true", help="really move the files")
    ap.add_argument("--undo", metavar="LOG", help="put back what an earlier run moved")
    ap.add_argument("--json", action="store_true", help="print the plan as JSON")
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if a.undo:
        back, problems = undo(a.undo, run=a.apply)
        for frm, to in back:
            print(f"  back  {frm}  ->  {to}")
        for p in problems:
            print(f"  skip  {p}")
        print(f"\n{'put back' if a.apply else 'would put back'} {len(back)} file(s), {len(problems)} left alone"
              + ("" if a.apply else ". Add --apply to do it."))
        return 1 if problems else 0

    if not a.src or not os.path.isdir(a.src):
        ap.error("give a folder to tidy")
    src = os.path.abspath(a.src)
    dest = os.path.abspath(a.dest or os.path.join(src, "sorted"))
    moves, skips = plan(src, dest, a.recursive)
    if a.json:
        print(json.dumps({"moves": [asdict(m) for m in moves], "skipped": skips}, indent=1))
    else:
        for m in moves:
            why = f"same as {_rel(m.duplicate_of, src if m.duplicate_of.startswith(src) else dest)}" if m.duplicate_of else f"date from {m.date_from}"
            print(f"  {'dupe' if m.duplicate_of else 'move'}  {_rel(m.src, src)}  ->  {_rel(m.dst, dest)}   ({why})")
        for s in skips:
            print(f"  skip  {_rel(s, src)}")
        kinds = Counter(m.kind for m in moves)
        print(f"\n{len(moves)} to move ({', '.join(f'{n} {k}' for k, n in sorted(kinds.items()))}), {len(skips)} skipped")
    if not a.apply:
        print("Dry run: nothing moved. Add --apply to move these files.")
        return 0

    log, done, problems = apply(moves, dest, datetime.now().strftime("%Y%m%d-%H%M%S"))
    for p in problems:
        print(f"  {p}")
    print(f"moved {len(done)} file(s). To undo: python -m media_sorter --undo \"{log}\" --apply")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
