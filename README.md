# MediaMaker

Schneidet TV-Aufnahmen (`.ts`): Werbung herausschneiden, schwarze Ränder und Senderlogo entfernen, als `.mp4` ausgeben.
Neuimplementierung des VB6-Programms in Python mit PySide6; gerendert wird mit `ffmpeg`, die Vorschau macht VLC.
Die Oberfläche wird weiterhin in der VB6-IDE entworfen und mit `ui/frm2qt.py` nach PySide6 übersetzt.

Der Stand der Arbeit steht in [CHANGELOG.md](CHANGELOG.md).

## Voraussetzungen

- Python 3.10 oder neuer
- Pakete: siehe `requirements.txt` (PySide6, python-vlc, numpy, Pillow)
- Programme: `ffmpeg` und `ffprobe` (im PATH), VLC mit libvlc

## Einrichten und Starten

```
cp MediaMaker.example.ini MediaMaker.ini      # danach an den eigenen Rechner anpassen (MediaMaker.ini wird nicht versioniert)
python3 mediamaker.py Film.ts                 # neuer Auftrag mit dieser Datei
python3 mediamaker.py                         # die zuletzt bearbeitete Schnittliste laden
python3 run_job.py JOB.sh --output Film.mp4   # Auftrag ohne Oberfläche ausführen
```

Nützliche Umgebungsvariablen: `MEDIAMAKER_DEBUG=1` (Protokoll in `mediamaker_debug.log`), `MEDIAMAKER_NO_FILTER=1` (Fehlerausgabe
ungefiltert). In der INI-Datei, Abschnitt `[settings]`: `player=memory|embed`, `vlc_args=...`, `hide_messages=Text1|Text2`.

## Tests

Die Tests brauchen keine Oberfläche (Qt wird durch `ui/tests/qtstub` ersetzt) und kleine Beispielvideos (`sample.ts`, `sample2.ts`,
`sample3.ts`), die nicht im Repository liegen:

```
python3 tests/test_app.py /pfad/zu/den/beispielvideos
python3 tests/test_border.py /pfad/zu/den/beispielvideos
python3 tests/test_logo.py /pfad/zu/sample.ts
python3 tests/test_build.py /pfad/zu/den/beispielvideos
python3 ui/tests/test_frm2qt.py "/pfad/zum/VB6-Ordner"
```

## Oberfläche aus VB6-Formularen erzeugen

```
python3 ui/frm2qt.py /pfad/zum/VB6-Ordner/*.frm --out ui/generated --stub
python3 ui/show_form.py frmMain --dir ui/generated        # Vorschau eines Formulars
```

## Versionen

Geänderte Stände werden mit Tags markiert (`v0.1`, `v0.2`, ...). Auf `main` wird die jeweils nächste Version entwickelt; die
Versionsnummer steht in `mediamaker.py` (`VERSION`).
