"""Strictly modelled replacement for PySide6, only for testing frm2qt.py without an installed Qt.

Every class knows only the methods and signals the generated code may use (taken from the Qt documentation). An unknown name
raises an error, so typos and invented methods are noticed.
It does not replace a run with the real Qt.
"""
