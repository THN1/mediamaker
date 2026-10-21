# Änderungen

## 0.2 (in Arbeit)

- Versionsnummer auf 0.2-dev gesetzt; noch keine funktionalen Änderungen gegenüber 0.1.

## 0.1

Erster eingefrorener Stand der Neuimplementierung in Python/PySide6 (noch nicht alle Funktionen des VB6-Programms).

Enthalten:

- **Hauptfenster** mit Schnittliste (JSON-Datei `MediaMaker.json`, alte CSV-Listen importierbar), Öffnen und Analyse von Videos
  (ffprobe), Drag & Drop, Tonspurwahl, Beenden mit sauberem Herunterfahren von VLC.
- **Vorschau** mit VLC: Wiedergabe in den Arbeitsspeicher, von Qt gezeichnet (läuft unter Wayland und X11); Schieber, Bildnummer und
  Zeit; Sprung zu einer Bildnummer; Anfahren der Startposition wird abgesichert.
- **Marker A/B** und **Zeitleiste** mit 20 Vorschaubildern, roten Kreuzen für fehlende Bilder, Klick zum Verschieben der Marker.
- **Bildnummern** zählen ab dem ersten dekodierbaren Videobild (intern ab Containerbeginn).
- **Segmente** löschen, verschieben, duplizieren; beim Duplizieren Suche nach dem Filmbeginn.
- **Suche** nach dem Ende bzw. dem nächsten Werbeblock mit Randerkennung oder Senderlogo (Hintergrund, abbrechbar, mit Fortschritt);
  **Auto crop**.
- **Profil und Optionen** (Dialoge mit Prüfung, benannte Profile, Schätzung der Bitraten); `pad` gehört zum Profil.
- **Media info** (Strg+K) und **Information** (Segmentübersicht mit Lage im fertigen Film, Gesamtlänge und geschätzter Größe).
- **ffmpeg-Aufruf** gegen das VB6-Programm geprüft (Beispiel Elysium: Befehl identisch, Bilder stimmen überein), Kommandozeile
  `run_job.py`, Fortschritt und Restzeit.
- **Oberfläche** aus den VB6-Formularen (`ui/frm2qt.py`), Qt-Ersatz für Tests ohne Oberfläche.

Noch nicht enthalten:

- Dialoge für Beschnitt und Logo (frmCrop, frmRemoveLogo) und die Knöpfe dafür
- Speichern als MP4/AVI aus der Oberfläche mit Fortschrittsanzeige (die Bausteine `ffmpeg_cmd.py`, `runner.py`, `run_job.py` gibt es)
- Batch-Menü, Import/Wiederherstellen einer Sitzung, Untertitel, Mehrsprachigkeit, DVD-Modus, Copy-Modus
- Überlappung von Segmenten, Kapitel (chapter()), Vorschau am Schnittpunkt
