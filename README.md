# SKATE 4 // MATRIX MOD MENU

Ein Trainer / Mod-Menü für **Skate 4** im Matrix-Look (grün auf schwarz), geschrieben in Python mit tkinter. Enthalten ist ein eingebauter Speicher-Scanner, mit dem du die benötigten Adressen selbst finden kannst.

---

## ⚠️ WARNHINWEISE – bitte zuerst lesen

- **Nur offline bzw. im Einzelspieler benutzen.** Skate 4 ist ein Online-Spiel mit Anti-Cheat. Das Verändern des Spielspeichers verstößt voraussichtlich gegen die Nutzungsbedingungen des Spiels und kann zu einer **Sperre deines Accounts** führen. Nutze das Tool nicht in Mehrspieler-Sitzungen und nicht, wenn der Anti-Cheat aktiv ist.
- **Benutzung auf eigene Gefahr.** Speicher-Manipulation kann zu Abstürzen, Fehlverhalten des Spiels oder beschädigten Spielständen führen. Mache vorher ein Backup deiner Spielstände.
- **Keine Garantie.** Das Programm ist ungetestet gegen das echte Spiel und wird ohne Gewähr bereitgestellt. Die Speicheradressen von Skate 4 sind **nicht** enthalten und ändern sich mit Spiel-Updates.
- **Nur für die private Nutzung.** Verschaffe dir damit keine Vorteile gegenüber anderen Spielern und verbreite keine Adressen oder Anleitungen, die dafür gedacht sind.
- **Nur Windows.** Der Scanner nutzt Windows-Systemfunktionen.
- **Antivirus:** Programme, die fremden Speicher lesen und schreiben, können von Virenscannern als verdächtig markiert werden. Das ist bei Trainern normal. Prüfe den Quellcode (er ist im Klartext) und starte nur Dateien, denen du vertraust.

---

## Funktionen

**MODS-Tab**
- Speed-Multiplikator (Slider)
- Jump-Höhe (Slider)
- Gravitation (Slider)
- Wetter ändern (Sonnig, Bewölkt, Regen, Sturm, Nebel, Schnee)
- Tageszeit (0–24 h)
- „HALTEN"-Option: schreibt einen Wert dauerhaft neu, damit das Spiel ihn nicht zurücksetzt
- Presets: Normal, Super Jump, Moon, Turbo

**SCANNER-Tab**
- Wert-Scanner im Stil von Cheat Engine (float / int)
- First Scan und Next Scan (Exakt, Geändert, Unverändert, Größer, Kleiner)
- Treffer direkt überschreiben
- Treffer einer Funktion (speed, jump, gravity, time_of_day, weather) zuweisen

**Sonstiges**
- Matrix-Regen-Animation und Konsole mit Statusmeldungen
- Demo-Modus: Ohne laufendes Spiel läuft das Menü weiter und schreibt nur ins Log

---

## Voraussetzungen

- Windows 10 / 11 (64 Bit)
- Python 3.10 oder neuer (https://www.python.org/downloads/)
- Python-Paket `pymem`
- Skate 4 (der Prozess muss laufen, damit du dich verbinden kannst)

---

## Installation

1. Lege `skate4_modmenu.py` in einen eigenen Ordner.
2. Öffne eine Eingabeaufforderung (oder das Terminal in PyCharm) in diesem Ordner.
3. Installiere die Abhängigkeit:

```
pip install pymem
```

`tkinter` ist bei der Standard-Installation von Python für Windows bereits dabei.

---

## Starten

1. Starte **Skate 4** im **Offline- bzw. Einzelspieler-Modus**.
2. Starte das Mod-Menü:

```
python skate4_modmenu.py
```

3. Klicke im Menü auf **VERBINDEN**.
   - Oben steht dann `STATUS: VERBUNDEN`.
   - Steht dort `DEMO-MODUS`, hat die Verbindung nicht geklappt (siehe Fehlerbehebung).

Falls nötig, starte die Eingabeaufforderung bzw. PyCharm **als Administrator**, damit auf den Spielprozess zugegriffen werden kann.

Beim ersten Start wird die Datei `skate4_offsets.json` neben dem Skript erzeugt.

---

## Bedienung

### Wichtig vorab: Adressen
Das Menü kann nur Werte ändern, wenn für die jeweilige Funktion eine Speicheradresse hinterlegt ist. Ohne Adresse erscheint in der Konsole „keine Adresse konfiguriert". Die Adressen findest du mit dem **SCANNER-Tab** oder mit Cheat Engine (siehe unten).

### MODS-Tab
- **Slider** bewegen: Der Wert wird sofort ins Spiel geschrieben.
- **HALTEN** aktivieren: Der Wert wird ständig neu geschrieben. Deaktiviere es, wenn du zum normalen Spielverhalten zurück willst.
- **Wetter:** Eintrag im Dropdown wählen und auf **SETZEN** klicken.
- **Presets:** Setzen Speed, Jump und Gravitation auf einmal.

### SCANNER-Tab – Adressen finden
1. Mit dem Spiel **VERBINDEN**.
2. **Typ** wählen (`float` für Kommazahlen wie Speed oder Gravitation, `int` für ganze Zahlen wie Wetter-IDs).
3. Den **aktuellen Wert** eingeben und **FIRST SCAN** klicken.
4. Im Spiel den Wert ändern (z. B. das Wetter wechseln).
5. **Modus** wählen und **NEXT SCAN** klicken:
   - *Exakt*: neuen Wert eingeben, nur passende Treffer bleiben
   - *Geändert / Unverändert*: vergleicht mit dem letzten Scan
   - *Größer / Kleiner*: Wert ist gestiegen bzw. gesunken
6. Schritte 4 und 5 wiederholen, bis nur noch wenige Treffer übrig sind.
7. Einen Treffer markieren, dann:
   - **SCHREIBEN**: überschreibt den Wert an dieser Adresse (zum Testen)
   - **ZUWEISEN**: speichert die Adresse für die gewählte Funktion

**Tipps**
- Float-Werte wie `9.81` passen beim ersten Scan nicht immer exakt. Dann mit *Geändert* und *Unverändert* filtern.
- Angezeigt werden maximal 500 Treffer, intern sind bis zu 500.000 möglich.
- Treffer mit `[Modul+0x...]` liegen im Hauptmodul und werden **dauerhaft** in der JSON gespeichert.
- Alle anderen Treffer (Heap) gelten **nur für die aktuelle Spielsitzung**. Nach einem Neustart des Spiels musst du neu scannen. Für dauerhafte Adressen brauchst du einen Pointer-Scan (z. B. mit Cheat Engine).

---

## Konfiguration (`skate4_offsets.json`)

```json
{
    "process_name": "Skate.exe",
    "module_name": "Skate.exe",
    "features": {
        "speed": { "chain": [], "type": "float", "default": 1.0 }
    },
    "weather_values": { "Sonnig": 0, "Regen": 2 }
}
```

| Feld | Bedeutung |
|------|-----------|
| `process_name` | Name des Spielprozesses (im Task-Manager prüfen) |
| `module_name` | Hauptmodul des Spiels, normalerweise identisch zum Prozessnamen |
| `chain` | Pointer-Kette: erster Wert = Offset vom Modulstart, weitere Werte = Offsets für jede weitere Dereferenzierung |
| `type` | `float` oder `int` |
| `default` | Startwert des Sliders |
| `weather_values` | Zuordnung Wettername zu Zahlenwert im Spiel (an das Spiel anpassen) |

---

## Fehlerbehebung

| Problem | Mögliche Lösung |
|---------|-----------------|
| `pymem fehlt` | `pip install pymem` ausführen |
| Verbindung fehlgeschlagen | Läuft das Spiel? Stimmt `process_name`? Als Administrator starten |
| „keine Adresse konfiguriert" | Adresse mit dem Scanner finden und zuweisen oder in der JSON eintragen |
| Scanner findet nichts | Typ prüfen (float/int), anderen Modus nutzen, Wert im Spiel wirklich ändern |
| Zu viele Treffer | Wert im Spiel ändern und mehrfach NEXT SCAN ausführen |
| Wert springt zurück | „HALTEN" aktivieren |
| Spiel stürzt ab | Falsche Adresse beschrieben. Spiel neu starten und neu scannen |
| Scanner meldet Windows-Fehler | Das Tool läuft nur unter Windows |

---

## Dateien

| Datei | Beschreibung |
|-------|--------------|
| `skate4_modmenu.py` | Das Mod-Menü inkl. Scanner |
| `skate4_offsets.json` | Wird beim ersten Start erzeugt, enthält Adressen und Einstellungen |
| `README.md` | Diese Anleitung |

---

## Haftungsausschluss

Dieses Projekt steht in keiner Verbindung zu Electronic Arts, Full Circle oder den Entwicklern von Skate. „Skate" und alle zugehörigen Marken gehören ihren jeweiligen Inhabern. Die Software wird „wie besehen" bereitgestellt, ohne jegliche Gewährleistung. Du bist selbst dafür verantwortlich, sie im Einklang mit den Nutzungsbedingungen des Spiels und den geltenden Gesetzen zu verwenden. Für Account-Sperren, Datenverlust oder sonstige Schäden wird keine Haftung übernommen.

---

## Lizenz

Noch nicht festgelegt. Ergänze hier deine gewünschte Lizenz (z. B. MIT), falls du das Projekt weitergeben möchtest.