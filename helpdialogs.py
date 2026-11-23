"""The windows of the menu Help: the Readme (README.md, formatted) and About (name, version, the COMMIT, the versions of the tools)."""
from __future__ import annotations

import html
import os

from PySide6 import QtCore, QtGui, QtWidgets

import dialogs

REPO_URL = "https://github.com/THN1/mediamaker"


def readme_dialog(parent, markdown: str, folder: str) -> QtWidgets.QDialog:
    """README.md as formatted text (headings, lists, tables, code, links; Qt reads Markdown itself). Links open in the browser; pictures are looked for next to the file."""
    factor = dialogs.ui_factor(parent)
    dialog = QtWidgets.QDialog(parent)
    dialogs.scale_font(dialog, factor, parent)
    dialog.setWindowTitle("MediaMaker - Readme")
    dialog.resize(round(900 * factor), round(720 * factor))
    layout = QtWidgets.QVBoxLayout(dialog)
    browser = QtWidgets.QTextBrowser(dialog)
    browser.setOpenExternalLinks(True)
    browser.setSearchPaths([folder])
    browser.setMarkdown(markdown)
    layout.addWidget(browser)
    buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    dialog.exec()
    return dialog


def about_text(version: str, commit_line: str, details: str) -> str:
    """The same information as plain text (for the button 'Copy information': for a bug report)."""
    return f"MediaMaker {version}\nCommit {commit_line}\n\n{details.rstrip()}\n"


def about_dialog(parent, version: str, info: dict, details: str, commit_line: str) -> QtWidgets.QDialog:
    """A window with the name, the version and, framed and large, the COMMIT that the program was started from (so that one sees what a test ran with), then the versions of
    Python, Qt, ffmpeg, ffprobe and VLC. 'Copy information' puts it all into the clipboard."""
    factor = dialogs.ui_factor(parent)
    dialog = QtWidgets.QDialog(parent)
    dialogs.scale_font(dialog, factor, parent)
    dialog.setWindowTitle("About MediaMaker")
    dialog.setMinimumWidth(round(560 * factor))
    outer = QtWidgets.QVBoxLayout(dialog)
    outer.setSpacing(14)

    top = QtWidgets.QHBoxLayout()
    top.setSpacing(16)
    icon = QtWidgets.QLabel(dialog)
    if parent is not None and hasattr(parent, "windowIcon"):
        icon.setPixmap(parent.windowIcon().pixmap(round(64 * factor), round(64 * factor)))
    icon.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
    top.addWidget(icon)
    title = QtWidgets.QLabel(dialog)
    title.setTextFormat(QtCore.Qt.TextFormat.RichText)
    title.setText(dialogs.scale_html_pt('<span style="font-size:22pt; font-weight:600;">MediaMaker</span><br>'
                  '<span style="font-size:11pt; color:gray;">Cuts, unifies and joins videos</span><br>'
                  f'<span style="font-size:11pt;">Version {html.escape(version)}</span>', factor))
    top.addWidget(title, 1)
    outer.addLayout(top)

    box = QtWidgets.QFrame(dialog)
    box.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
    box.setStyleSheet("QFrame { background: palette(alternate-base); border: 1px solid palette(mid); border-radius: 6px; }")
    inner = QtWidgets.QVBoxLayout(box)
    inner.setContentsMargins(16, 12, 16, 12)
    commit = QtWidgets.QLabel(box)
    commit.setTextFormat(QtCore.Qt.TextFormat.RichText)
    commit.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
    if info.get("hash"):
        lines = [f'<span style="font-size:10pt; color:gray;">Commit</span><br>'
                 f'<span style="font-family:monospace; font-size:20pt; font-weight:600;">{html.escape(info["short"])}</span>'
                 + (f'&nbsp;&nbsp;<span style="font-family:monospace; font-size:10pt; color:gray;">{html.escape(info["describe"])}</span>' if info.get("describe") != info["short"] else "")]
        if info.get("date") or info.get("subject"):
            lines.append(f'<span style="font-size:10pt;">{html.escape(info.get("date", "")[:16].replace("T", " "))}&nbsp;&nbsp;{html.escape(info.get("subject", ""))}</span>')
        if info.get("branch"):
            lines.append(f'<span style="font-size:10pt; color:gray;">Branch {html.escape(info["branch"])}</span>')
        if info.get("dirty"):
            shown = ", ".join(info["dirty"][:6]) + (" ..." if len(info["dirty"]) > 6 else "")
            lines.append(f'<span style="font-size:10pt; color:#d2691e;">&#9888; Local changes in {len(info["dirty"])} file(s): {html.escape(shown)}</span>')
        elif info.get("source") == "git":
            lines.append('<span style="font-size:10pt; color:#2e8b57;">&#10004; No local changes</span>')
        commit.setText(dialogs.scale_html_pt("<br>".join(lines), factor))
    else:
        commit.setText(dialogs.scale_html_pt('<span style="font-size:12pt;">Commit unknown</span><br><span style="font-size:10pt; color:gray;">'
                                             'The program is not run from a git clone, and there is no file COMMIT next to it.</span>', factor))
    inner.addWidget(commit)
    outer.addWidget(box)

    versions = QtWidgets.QLabel(dialog)
    versions.setTextFormat(QtCore.Qt.TextFormat.RichText)
    versions.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
    versions.setText(dialogs.scale_html_pt('<pre style="font-size:9pt; margin:0;">' + html.escape(details.rstrip()) + "</pre>", factor))
    outer.addWidget(versions)

    link = QtWidgets.QLabel(dialog)
    link.setTextFormat(QtCore.Qt.TextFormat.RichText)
    link.setOpenExternalLinks(True)
    link.setText(f'<a href="{REPO_URL}">{REPO_URL}</a>')
    outer.addWidget(link)

    row = QtWidgets.QHBoxLayout()
    copy = QtWidgets.QPushButton("Copy information", dialog)
    copy.clicked.connect(lambda: QtWidgets.QApplication.clipboard().setText(about_text(version, commit_line, details)))
    close = QtWidgets.QPushButton("Close", dialog)
    close.setDefault(True)
    close.clicked.connect(dialog.accept)
    row.addWidget(copy)
    row.addStretch(1)
    row.addWidget(close)
    outer.addLayout(row)
    dialog.exec()
    return dialog
