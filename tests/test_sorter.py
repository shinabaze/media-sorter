import errno
import hashlib
import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime
from unittest import mock

from media_sorter import apply, kind_of, plan, undo
from media_sorter import sorter

from .fixtures import make_mess, write


def snapshot(root):
    """Every file under root: relative path -> sha256 of its bytes."""
    out = {}
    for folder, _, names in os.walk(root):
        for n in names:
            p = os.path.join(folder, n)
            with open(p, "rb") as fh:
                out[os.path.relpath(p, root).replace(os.sep, "/")] = hashlib.sha256(fh.read()).hexdigest()
    return out


def contents(snap):
    """The multiset of file contents, ignoring where they are."""
    return sorted(h for p, h in snap.items() if "media-sorter-undo-" not in p)


class Sorter(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.src = os.path.join(self.tmp, "downloads")
        self.dest = os.path.join(self.src, "sorted")
        make_mess(self.src)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def rel(self, path):
        return os.path.relpath(path, self.dest).replace(os.sep, "/")

    def test_planning_changes_nothing(self):
        before = snapshot(self.tmp)
        plan(self.src, self.dest, recursive=True)
        self.assertEqual(snapshot(self.tmp), before)

    def test_files_go_to_kind_year_month(self):
        moves, skips = plan(self.src, self.dest, recursive=True)
        where = {os.path.basename(m.src): self.rel(m.dst) for m in moves}
        self.assertEqual(where["IMG_4021.jpg"], "images/2026/2026-03/IMG_4021.jpg")
        self.assertEqual(where["Screenshot 2026-05-02 at 09.41.12.png"], "images/2026/2026-05/Screenshot 2026-05-02 at 09.41.12.png")
        self.assertEqual(where["brief.pdf"], "documents/2026/2026-08/brief.pdf")
        self.assertEqual(where["scene.blend"], "projects/2026/2026-09/scene.blend")
        self.assertEqual(where["voiceover_take3.wav"], "audio/2026/2026-10/voiceover_take3.wav")
        self.assertEqual(sorted(os.path.basename(s) for s in skips), [".DS_Store", "big-render.mp4.crdownload"])

    def test_duplicates_are_found_by_content_and_the_oldest_keeps_its_place(self):
        moves, _ = plan(self.src, self.dest, recursive=True)
        dupes = {os.path.basename(m.src): os.path.basename(m.duplicate_of) for m in moves if m.duplicate_of}
        self.assertEqual(dupes, {"render_final (1).mp4": "render_final.mp4", "IMG_4021 copy.jpg": "IMG_4021.jpg"})
        self.assertTrue(all(self.rel(m.dst).startswith("duplicates/") for m in moves if m.duplicate_of))
        # same size and name but different bytes is not a duplicate
        self.assertFalse(any(os.path.basename(m.src) == "render_final_v2.mp4" and m.duplicate_of for m in moves))

    def test_same_name_different_content_gets_a_number(self):
        moves, _ = plan(self.src, self.dest, recursive=True)
        covers = sorted(self.rel(m.dst) for m in moves if os.path.basename(m.src) == "cover.png")
        self.assertEqual(covers, ["images/2026/2026-10/cover (2).png", "images/2026/2026-10/cover.png"])

    def test_without_recursive_subfolders_are_left_alone(self):
        moves, _ = plan(self.src, self.dest)
        self.assertFalse(any(os.sep + "old" + os.sep in m.src for m in moves))

    def test_apply_moves_everything_in_the_plan_and_loses_nothing(self):
        before = snapshot(self.src)
        moves, _ = plan(self.src, self.dest, recursive=True)
        log, done, problems = apply(moves, self.dest, "20261019-120000")
        after = snapshot(self.src)
        self.assertEqual(problems, [])
        self.assertEqual(len(done), len(moves))
        self.assertEqual(contents(after), contents(before), "every file's bytes still exist, once each")
        for m in moves:
            self.assertFalse(os.path.exists(m.src))
            self.assertTrue(os.path.isfile(m.dst))
        with open(log, encoding="utf-8") as fh:
            self.assertEqual([e["dst"] for e in json.load(fh)], [m.dst for m in moves])

    def test_running_again_finds_nothing_new(self):
        moves, _ = plan(self.src, self.dest, recursive=True)
        apply(moves, self.dest, "20261019-120000")
        again, skips = plan(self.src, self.dest, recursive=True)
        self.assertEqual(again, [])
        self.assertEqual(len(skips), 2)

    def test_a_file_already_sorted_is_a_duplicate_next_time(self):
        moves, _ = plan(self.src, self.dest)
        apply(moves, self.dest, "20261019-120000")
        write(os.path.join(self.src, "brief (copy).pdf"), b"%PDF-1.7 the brief", datetime(2026, 10, 9))
        again, _ = plan(self.src, self.dest)
        self.assertEqual(len(again), 1)
        self.assertEqual(self.rel(again[0].duplicate_of), "documents/2026/2026-08/brief.pdf")

    def test_apply_never_overwrites_a_file_that_appeared_after_the_plan(self):
        moves, _ = plan(self.src, self.dest)
        target = next(m for m in moves if os.path.basename(m.src) == "brief.pdf")
        write(target.dst, b"someone else's file")
        log, done, problems = apply(moves, self.dest, "20261019-120000")
        self.assertEqual(len(problems), 1)
        self.assertIn("left", problems[0])
        with open(target.dst, "rb") as fh:
            self.assertEqual(fh.read(), b"someone else's file")
        self.assertTrue(os.path.exists(target.src))

    def test_undo_puts_everything_back(self):
        before = snapshot(self.src)
        moves, _ = plan(self.src, self.dest, recursive=True)
        log, _, _ = apply(moves, self.dest, "20261019-120000")
        back, problems = undo(log)  # dry by default
        self.assertEqual((len(back), problems), (len(moves), []))
        self.assertTrue(all(os.path.exists(m.dst) for m in moves), "a dry undo moves nothing")
        undo(log, run=True)
        after = {p: h for p, h in snapshot(self.src).items() if not p.startswith("sorted/")}
        self.assertEqual(after, before)

    def test_undo_leaves_a_changed_or_blocked_file_alone(self):
        moves, _ = plan(self.src, self.dest)
        log, _, _ = apply(moves, self.dest, "20261019-120000")
        changed = next(m for m in moves if os.path.basename(m.src) == "brief.pdf")
        write(changed.dst, b"edited after sorting, now longer than before")
        blocked = next(m for m in moves if os.path.basename(m.src) == "scene.blend")
        write(blocked.src, b"a new file with the old name")
        back, problems = undo(log, run=True)
        self.assertEqual(len(problems), 2)
        self.assertTrue(os.path.exists(changed.dst) and os.path.exists(blocked.dst))
        self.assertEqual(len(back), len(moves) - 2)

    def test_a_move_across_drives_copies_checks_then_removes(self):
        moves, _ = plan(self.src, self.dest)
        before = contents(snapshot(self.src))
        real_rename = os.rename

        def cross_device(a, b):
            if os.path.dirname(a) == self.src:
                raise OSError(errno.EXDEV, "Invalid cross-device link")
            return real_rename(a, b)

        with mock.patch.object(sorter.os, "rename", side_effect=cross_device):
            _, done, problems = apply(moves, self.dest, "20261019-120000")
        self.assertEqual((len(done), problems), (len(moves), []))
        self.assertEqual(contents(snapshot(self.src)), before)

    def test_a_bad_copy_leaves_the_original_where_it_was(self):
        m = next(m for m in plan(self.src, self.dest)[0] if os.path.basename(m.src) == "brief.pdf")

        def bad_copy(a, b):
            with open(b, "wb") as fh:
                fh.write(b"truncated")

        with mock.patch.object(sorter.os, "rename", side_effect=OSError(errno.EXDEV, "cross-device")), \
                mock.patch.object(sorter.shutil, "copy2", side_effect=bad_copy):
            _, done, problems = apply([m], self.dest, "20261019-120000")
        self.assertEqual(done, [])
        self.assertIn("did not match", problems[0])
        self.assertTrue(os.path.isfile(m.src))
        self.assertFalse(os.path.exists(m.dst))

    def test_kinds_by_extension(self):
        for name, kind in {"A.JPG": "images", "clip.MOV": "video", "vo.flac": "audio", "deck.pptx": "documents",
                           "comp.aep": "projects", "x.7z": "archives", "mystery.xyz": "other", "Makefile": "other"}.items():
            self.assertEqual(kind_of(name), kind, name)


if __name__ == "__main__":
    unittest.main()
