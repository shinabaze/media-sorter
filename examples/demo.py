"""Make a messy downloads folder in a temp directory, sort it, then undo the sort.

    python examples/demo.py

Nothing outside the temp directory is touched.
"""
import os
import shutil
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from media_sorter import apply, plan, undo  # noqa: E402
from tests.fixtures import make_mess  # noqa: E402


def tree(root):
    for folder, dirs, names in os.walk(root):
        dirs.sort()
        for n in sorted(names):
            yield os.path.relpath(os.path.join(folder, n), root).replace(os.sep, "/")


def main():
    tmp = tempfile.mkdtemp()
    src = os.path.join(tmp, "downloads")
    dest = os.path.join(src, "sorted")
    try:
        make_mess(src)
        print(f"A downloads folder with {len(list(tree(src)))} files.\n\nThe plan (nothing has moved yet):")
        moves, skips = plan(src, dest, recursive=True)
        for m in moves:
            why = f"same bytes as {os.path.basename(m.duplicate_of)}" if m.duplicate_of else f"date from {m.date_from}"
            print(f"  {os.path.relpath(m.src, src).replace(os.sep, '/'):<40} -> {os.path.relpath(m.dst, dest).replace(os.sep, '/'):<58} {why}")
        for s in skips:
            print(f"  {os.path.basename(s):<40}    left alone")

        log, done, problems = apply(moves, dest, "20261019-120000")
        print(f"\nApplied: {len(done)} moved, {len(problems)} problems. Now in sorted/:")
        for p in tree(dest):
            print(f"  {p}")

        back, problems = undo(log, run=True)
        print(f"\nUndo: {len(back)} put back, {len(problems)} problems. downloads/ again, outside sorted/:")
        for p in tree(src):
            if not p.startswith("sorted/"):
                print(f"  {p}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
