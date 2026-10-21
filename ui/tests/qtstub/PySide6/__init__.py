"""Streng modellierter Ersatz für PySide6, nur für den Test von frm2qt.py ohne installiertes Qt.

Jede Klasse kennt nur die Methoden und Signale, die der erzeugte Code verwenden darf (aus der Qt-Dokumentation
übernommen). Ein unbekannter Name löst einen Fehler aus; so fallen Tippfehler und erfundene Methoden auf.
Er ersetzt keinen Lauf mit dem echten Qt.
"""
