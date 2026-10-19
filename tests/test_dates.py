import os
import shutil
import tempfile
import unittest
from datetime import datetime

from media_sorter import exif_date, file_date, name_date

from .fixtures import jpeg_with_exif, write


class Dates(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def path(self, name):
        return os.path.join(self.tmp, name)

    def test_exif_in_both_byte_orders(self):
        for order in ("II", "MM"):
            p = write(self.path(f"{order}.jpg"), jpeg_with_exif("2025:12:31 23:59:58", order))
            self.assertEqual(exif_date(p), datetime(2025, 12, 31, 23, 59, 58), order)

    def test_not_a_jpeg_or_broken_exif_gives_none(self):
        self.assertIsNone(exif_date(write(self.path("a.jpg"), b"not a jpeg at all")))
        broken = jpeg_with_exif("2025:12:31 23:59:58")[:30]
        self.assertIsNone(exif_date(write(self.path("b.jpg"), broken)))
        self.assertIsNone(exif_date(write(self.path("c.jpg"), jpeg_with_exif("not a date at all!!"))))

    def test_dates_in_names(self):
        cases = {
            "IMG_20260314_101500.jpg": datetime(2026, 3, 14),
            "Screenshot 2026-05-02 at 09.41.12.png": datetime(2026, 5, 2),
            "export_2026.07.09_final.mov": datetime(2026, 7, 9),
            "render_v2.mp4": None,
            "invoice-20261340.pdf": None,      # month 13
            "take_20260231.wav": None,          # 31 February
            "id 1202603141.txt": None,          # digits on both sides: not a date
        }
        for name, expect in cases.items():
            self.assertEqual(name_date(name), expect, name)

    def test_exif_beats_the_name_and_the_name_beats_the_modified_time(self):
        when = datetime(2026, 1, 2, 3, 4)
        a = write(self.path("IMG_20260601.jpg"), jpeg_with_exif("2024:05:06 07:08:09"), when)
        b = write(self.path("IMG_20260601.png"), b"png", when)
        c = write(self.path("notes.txt"), b"txt", when)
        self.assertEqual(file_date(a), (datetime(2024, 5, 6, 7, 8, 9), "exif"))
        self.assertEqual(file_date(b), (datetime(2026, 6, 1), "name"))
        self.assertEqual(file_date(c), (when, "modified"))


if __name__ == "__main__":
    unittest.main()
