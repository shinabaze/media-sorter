# Decisions

**A dry run is the default, not a flag.** `--apply` has to be typed to move anything, and so does
`--apply` on an undo. The safe command is the one you get by accident.

**Duplicates are moved aside, never deleted.** Deciding which copy to throw away is a judgement
about your files, and this tool doesn't make it. It puts every copy it is sure about in
`duplicates/`, where you can look and empty it yourself.

**Exact bytes only.** Two files are duplicates when their SHA-256 matches. Perceptual hashing
would also catch a re-saved JPEG, and it would sometimes call two different photos the same,
which is the wrong mistake for a tool that moves files.

**Oldest first.** When there are two copies, the one with the earliest date keeps the normal
place. The first copy is usually the one other things refer to; the later ones are "(1)" and
"copy" downloads.

**EXIF without Pillow.** Reading one date from a JPEG needs about 50 lines of byte handling, and
Pillow would make a small tool something to install. Other formats (HEIC, RAW, video) would need
real parsers, so they fall back to the name and the modified time, and the README says so.

**A cross-drive move is verified.** `shutil.move` copies and removes without comparing. For a tool
whose whole promise is not losing anything, the copy is compared byte for byte first.

**The undo log is rewritten after every move.** It costs a small write per file and means the log
is correct if the run is stopped, crashes or loses power halfway. It is written to a temporary
file and renamed into place, so it is never half written.

**Undo checks before it moves.** A file edited after sorting, or a new file with the old name, is
left alone and reported. Undo must never be the thing that loses work.

**Folders stay.** Neither the sort nor the undo removes a folder, even an empty one.
