"""Chapter editor (VB6: frmChapters): shows one chapter per segment; a style gives them names, the names can be edited, and every change writes the
chapters file for ffmpeg at once (savetxt). The check box switches the chapters on and off (off deletes the file). See chapters.py."""
from __future__ import annotations

from typing import Optional

import chapters
from ui_frmChapters import frmChaptersBase

F2 = 113
SHIFT = 26                 # pixels: the frame and the button move down, so that the check box is above the frame and not on its edge


class frmChapters(frmChaptersBase):
    def __init__(self, parent=None):
        """parent: the main window (segments, place of the chapters file, messages)."""
        super().__init__(parent)
        self.main = parent
        self.Label2.hide()                    # "input files MUST NOT HAVE CHAPTERS": no longer true, the command takes the chapters from this file
        self.arrange()
        self.lvwChapters.itemDoubleClicked.connect(lambda *args: self.edit_current())
        self.Form_Load()

    def arrange(self) -> None:
        """In the VB6 form the check box sits ON the upper edge of the frame (over its caption "Frame1"); here the frame would show through it. So the frame
        (with everything in it) and the Close button move down, the frame gets a caption, and the check box stands alone above it."""
        self.Frame1.setTitle("Chapter names")
        for widget in (self.Frame1, self.cmdOK):
            g = widget.geometry()
            widget.setGeometry(g.x(), g.y() + SHIFT, g.width(), g.height())
        self.resize(self.width(), self.height() + SHIFT)

    # ------------------------------------------------------------------ the list
    def titles(self) -> list:
        return [self.lvwChapters.topLevelItem(i).text(0) for i in range(self.lvwChapters.row_count())]

    def show_titles(self, titles: list) -> None:
        self.lvwChapters.set_rows([[t] for t in titles])

    def savetxt(self) -> None:
        """Writes the chapters file for the segments of the main window."""
        chapters.write(self.main.chapters_path(), self.titles(), self.main.segments)

    # ------------------------------------------------------------------ VB6 procedures
    def Form_Load(self):
        text = chapters.read(self.main.chapters_path())
        if text is not None and chapters.is_valid(text, self.main.segments):
            self.show_titles(chapters.fit_titles(chapters.parse_titles(text), self.main.segments))
            self.chkActivate.setChecked(True)
        else:
            self.chkActivate.setChecked(False)
        self.chkActivate_Click()

    def chkActivate_Click(self):
        on = self.chkActivate.isChecked()
        self.Frame1.setEnabled(on)
        path = self.main.chapters_path()
        if on:
            if self.lvwChapters.row_count() == 0:                    # first style: enumerated
                self.cboStyle.setCurrentIndex(0)
                self.apply_style(0)
            else:
                self.savetxt()
        else:
            self.lvwChapters.set_rows([])
            if chapters.read(path) is not None:
                self.main.remove_chapters_file()

    def cboStyle_Click(self):
        self.apply_style(self.cboStyle.currentIndex())

    def apply_style(self, style: int) -> None:
        """Names for the chapters: 0-2 generated from the segments, 3 the names of the previous file, 4 the names in the batch file."""
        segments = self.main.segments
        if style <= 2:
            titles: Optional[list] = chapters.style_titles(style, segments)
        elif style == 3:
            text = chapters.read(self.main.chapters_path())
            if text is None:
                self.main.msg("No previous chapter file found.")
                return
            titles = chapters.parse_titles(text)
        else:
            titles = self.main.batch_chapter_titles()                # (says itself why there are none)
        if titles is None:
            return
        if style >= 3 and len(titles) != len(segments):
            self.main.msg(f"The chapters have {len(titles)} name{'s' if len(titles) != 1 else ''}, the list has {len(segments)} segment{'s' if len(segments) != 1 else ''}: "
                          + ("the surplus names are dropped." if len(titles) > len(segments) else "the missing ones are named \"Scene n\"."))
        self.show_titles(chapters.fit_titles(titles, segments))
        self.savetxt()

    def edit_current(self) -> None:
        row = self.lvwChapters.current_row()
        if row < 0:
            return
        item = self.lvwChapters.topLevelItem(row)
        new = self.main.ask_text("Chapter Editor", "Enter new value:", item.text(0))
        if new:                                                      # (empty: nothing changes, as in VB6)
            item.setText(0, new)
            self.savetxt()

    def lvwChapters_KeyUp(self, keycode=0, shift=0):
        if keycode == F2:
            self.edit_current()

    def cmdOK_Click(self):
        self.accept()
