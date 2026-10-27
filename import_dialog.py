"""Choosing the job to import from a batch file (VB6: frmImport, "Select which job to import from batch file").

The jobs are shown as a list, one line each ("Job1:<output file>"); a double click on a job or OK chooses it (the same window as for choosing
a session)."""
from __future__ import annotations

from typing import Optional

import sessions_dialog


def choose_job(parent, jobs: list) -> Optional[object]:
    """The chosen job (batch.BatchJob), or None if cancelled."""
    chosen = sessions_dialog.choose_sessions(parent, "Import job", "Select which job to import from batch file:", jobs)
    return chosen[0][0] if chosen else None
