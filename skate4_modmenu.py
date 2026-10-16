"""
SKATE 4 // MATRIX MOD MENU  (v2 mit Scanner)
---------------------------------------------
Python 3.10+, nur Windows   |   pip install pymem

WICHTIG:
- Nur offline / im Einzelspieler benutzen. Online-Spiele mit Anti-Cheat
  (EA Javelin / EAC) koennen dich dafuer bannen.
- Offsets stehen in 'skate4_offsets.json' (wird beim ersten Start erzeugt).
  Mit dem SCANNER-Tab kannst du Adressen direkt finden und einer Funktion zuweisen.
- Liegt eine Adresse im Hauptmodul (Skate.exe), wird sie dauerhaft als Offset
  gespeichert. Heap-Adressen (typisch fuer Spielwerte) gelten nur fuer die
  aktuelle Spielsitzung, dafuer bräuchtest du einen Pointer-Scan (nicht enthalten).
- Ohne verbundenes Spiel laeuft das Menue im DEMO-Modus (nur Log-Ausgabe).

SCANNER-ABLAUF (wie Cheat Engine):
  1. Typ waehlen (float/int), aktuellen Wert eingeben -> FIRST SCAN
  2. Im Spiel den Wert aendern (z.B. Wetter wechseln, Speed aendern)
  3. NEXT SCAN mit Modus (Exakt / Geaendert / Unveraendert / Groesser / Kleiner)
  4. Wiederholen, bis nur noch wenige Treffer uebrig sind
  5. Treffer markieren -> Wert schreiben oder einer Funktion zuweisen
"""

import ctypes
import json
import os
import random
import struct
import threading
import time
import tkinter as tk
from tkinter import ttk

try:
    import pymem
    import pymem.process
    HAS_PYMEM = True
except ImportError:
    HAS_PYMEM = False

CONFIG_FILE = "skate4_offsets.json"

DEFAULT_CONFIG = {
    "process_name": "Skate.exe",
    "module_name": "Skate.exe",
    "features": {
        "speed":       {"chain": [], "type": "float", "default": 1.0},
        "jump":        {"chain": [], "type": "float", "default": 1.0},
        "gravity":     {"chain": [], "type": "float", "default": -9.81},
        "time_of_day": {"chain": [], "type": "float", "default": 12.0},
        "weather":     {"chain": [], "type": "int",   "default": 0},
    },
    "weather_values": {
        "Sonnig": 0, "Bewoelkt": 1, "Regen": 2,
        "Sturm": 3, "Nebel": 4, "Schnee": 5,
    },
}

GREEN = "#00ff41"
DIM = "#008f11"
DARKGREEN = "#003b00"
BLACK = "#000000"
FONT = ("Consolas", 10)
FONT_B = ("Consolas", 11, "bold")
FONT_T = ("Consolas", 18, "bold")

# ---- Windows-Speicherregionen ------------------------------------------------
MEM_COMMIT = 0x1000
PAGE_NOACCESS = 0x01
PAGE_GUARD = 0x100
WRITABLE = 0x04 | 0x08 | 0x40 | 0x80   # RW, WRITECOPY, EXEC_RW, EXEC_WRITECOPY
MAX_RESULTS = 500_000
CHUNK = 32 * 1024 * 1024


class MBI(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", ctypes.c_uint32),
        ("RegionSize", ctypes.c_size_t),
        ("State", ctypes.c_uint32),
        ("Protect", ctypes.c_uint32),
        ("Type", ctypes.c_uint32),
    ]


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4)


def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return json.loads(json.dumps(DEFAULT_CONFIG))
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# --------------------------------------------------------------------------
# Speicher-Zugriff
# --------------------------------------------------------------------------
class GameMemory:
    def __init__(self, cfg, log):
        self.cfg = cfg
        self.log = log
        self.pm = None
        self.base = 0
        self.mod_size = 0
        self.overrides = {}   # feature -> absolute Adresse (nur diese Sitzung)

    @property
    def attached(self):
        return self.pm is not None

    def attach(self):
        if not HAS_PYMEM:
            self.log("pymem fehlt -> 'pip install pymem'. DEMO-Modus aktiv.")
            return False
        try:
            self.pm = pymem.Pymem(self.cfg["process_name"])
            mod = pymem.process.module_from_name(
                self.pm.process_handle, self.cfg["module_name"])
            self.base = mod.lpBaseOfDll
            self.mod_size = mod.SizeOfImage
            self.log(f"Verbunden mit {self.cfg['process_name']} "
                     f"(Base 0x{self.base:X})")
            return True
        except Exception as e:
            self.pm = None
            self.log(f"Verbindung fehlgeschlagen: {e}")
            return False

    def detach(self):
        if self.pm:
            try:
                self.pm.close_process()
            except Exception:
                pass
        self.pm = None
        self.overrides.clear()
        self.log("Getrennt.")

    def in_module(self, addr):
        return self.base <= addr < self.base + self.mod_size

    def _resolve(self, chain):
        addr = self.base + chain[0]
        for off in chain[1:]:
            addr = self.pm.read_longlong(addr) + off
        return addr

    # ---- direkter Zugriff (Scanner) ----
    def read_bytes(self, addr, n):
        return self.pm.read_bytes(addr, n)

    def write_at(self, addr, dtype, value):
        try:
            if dtype == "float":
                self.pm.write_float(addr, float(value))
            else:
                self.pm.write_int(addr, int(value))
            return True
        except Exception as e:
            self.log(f"Schreibfehler bei 0x{addr:X}: {e}")
            return False

    def regions(self):
        """Liefert (Start, Groesse) aller lesbaren+beschreibbaren Regionen."""
        try:
            vq = ctypes.windll.kernel32.VirtualQueryEx
        except AttributeError:
            self.log("Scanner funktioniert nur unter Windows.")
            return
        vq.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                       ctypes.POINTER(MBI), ctypes.c_size_t]
        handle = self.pm.process_handle
        addr = 0
        mbi = MBI()
        while addr < 0x7FFFFFFF0000:
            if not vq(handle, ctypes.c_void_p(addr), ctypes.byref(mbi),
                      ctypes.sizeof(mbi)):
                break
            size = mbi.RegionSize
            if (mbi.State == MEM_COMMIT
                    and mbi.Protect & WRITABLE
                    and not mbi.Protect & (PAGE_GUARD | PAGE_NOACCESS)):
                yield mbi.BaseAddress, size
            addr = (mbi.BaseAddress or 0) + size

    # ---- Feature schreiben ----
    def write(self, name, value):
        feat = self.cfg["features"][name]
        if not feat["chain"] and name not in self.overrides:
            self.log(f"[{name}] keine Adresse konfiguriert -> {value}")
            return False
        if not self.attached:
            self.log(f"[DEMO] {name} = {value}")
            return False
        try:
            if name in self.overrides:
                addr = self.overrides[name]
            else:
                addr = self._resolve(feat["chain"])
            return self.write_at(addr, feat["type"], value)
        except Exception as e:
            self.log(f"[{name}] Schreibfehler: {e}")
            return False


# --------------------------------------------------------------------------
# Scanner
# --------------------------------------------------------------------------
class Scanner:
    def __init__(self, mem, log):
        self.mem = mem
        self.log = log
        self.dtype = "float"
        self.results = []     # Liste von [adresse, bytes_alt]

    @staticmethod
    def pack(dtype, v):
        return struct.pack("<f", float(v)) if dtype == "float" else struct.pack("<i", int(v))

    @staticmethod
    def unpack(dtype, b):
        return struct.unpack("<f" if dtype == "float" else "<i", b)[0]

    def reset(self):
        self.results = []

    def first_scan(self, dtype, value, progress):
        self.dtype = dtype
        pat = self.pack(dtype, value)
        found = []
        regs = list(self.mem.regions() or [])
        for i, (base, size) in enumerate(regs):
            for off in range(0, size, CHUNK):
                n = min(CHUNK, size - off)
                n -= n % 4
                if n <= 0:
                    continue
                try:
                    data = self.mem.read_bytes(base + off, n)
                except Exception:
                    continue
                idx = data.find(pat)
                while idx != -1:
                    if idx % 4 == 0:
                        found.append([base + off + idx, pat])
                        if len(found) >= MAX_RESULTS:
                            self.log(f"Limit {MAX_RESULTS} erreicht - Scan gekappt. "
                                     "Wert aendern und NEXT SCAN nutzen.")
                            self.results = found
                            return len(found)
                    idx = data.find(pat, idx + 1)
            if i % 25 == 0:
                progress(f"Scanne Region {i + 1}/{len(regs)} ... {len(found)} Treffer")
        self.results = found
        return len(found)

    def next_scan(self, mode, value, progress):
        dtype = self.dtype
        target = None
        if mode == "Exakt":
            target = self.pack(dtype, value)
        keep = []
        total = len(self.results)
        for i, (addr, old) in enumerate(self.results):
            try:
                cur = self.mem.read_bytes(addr, 4)
            except Exception:
                continue
            if mode == "Exakt":
                ok = cur == target
            elif mode == "Geaendert":
                ok = cur != old
            elif mode == "Unveraendert":
                ok = cur == old
            else:
                a, b = self.unpack(dtype, cur), self.unpack(dtype, old)
                ok = a > b if mode == "Groesser" else a < b
            if ok:
                keep.append([addr, cur])
            if i % 20000 == 0:
                progress(f"Filtere {i}/{total} ...")
        self.results = keep
        return len(keep)


# --------------------------------------------------------------------------
# GUI
# --------------------------------------------------------------------------
class MatrixRain(tk.Canvas):
    def __init__(self, master, height=80, **kw):
        super().__init__(master, height=height, bg=BLACK,
                         highlightthickness=0, **kw)
        self.chars = "ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿ0123456789ABCDEFZ"
        self.cell = 14
        self.trail = 8
        self.cols = {}
        self.after(60, self._tick)

    def _tick(self):
        w, h = self.winfo_width(), self.winfo_height()
        n_cols = max(1, w // self.cell)
        shades = [GREEN, GREEN, DIM, DIM, "#006b0e", DARKGREEN, "#002200"]
        for c in range(n_cols):
            col = self.cols.setdefault(c, {"y": random.randint(-10, 0), "items": []})
            col["y"] += 1
            if col["y"] * self.cell > h + self.trail * self.cell:
                col["y"] = random.randint(-8, 0)
            if col["y"] >= 0:
                item = self.create_text(c * self.cell + 7, col["y"] * self.cell,
                                        text=random.choice(self.chars),
                                        fill="#ccffcc", font=("Consolas", 11))
                col["items"].append(item)
            while len(col["items"]) > self.trail:
                self.delete(col["items"].pop(0))
            for i, it in enumerate(reversed(col["items"][:-1])):
                self.itemconfig(it, fill=shades[min(i, len(shades) - 1)])
        self.after(70, self._tick)


class ModMenu(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SKATE 4 // MOD MENU")
        self.configure(bg=BLACK)
        self.geometry("600x900")
        self.minsize(560, 800)

        self.cfg = load_config()
        self.mem = GameMemory(self.cfg, self.log)
        self.scanner = Scanner(self.mem, self.log)
        self.freeze = {}
        self.running = True
        self.busy = False

        self._style()
        self._build()
        self.after(200, lambda: self.log("System bereit. Folge dem weissen Kaninchen..."))
        threading.Thread(target=self._freeze_loop, daemon=True).start()
        self.protocol("WM_DELETE_WINDOW", self._close)

    # ---------- Styling ----------
    def _style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("M.TCombobox", fieldbackground=BLACK, background=BLACK,
                    foreground=GREEN, arrowcolor=GREEN, bordercolor=GREEN,
                    selectbackground=BLACK, selectforeground=GREEN)
        s.configure("TNotebook", background=BLACK, borderwidth=0)
        s.configure("TNotebook.Tab", background=BLACK, foreground=GREEN,
                    font=FONT_B, padding=[16, 5], borderwidth=1)
        s.map("TNotebook.Tab", background=[("selected", DARKGREEN)],
              foreground=[("selected", GREEN)])
        self.option_add("*TCombobox*Listbox.background", BLACK)
        self.option_add("*TCombobox*Listbox.foreground", GREEN)
        self.option_add("*TCombobox*Listbox.selectBackground", DARKGREEN)

    def _label(self, parent, text, font=FONT, fg=GREEN):
        return tk.Label(parent, text=text, bg=BLACK, fg=fg, font=font)

    def _button(self, parent, text, cmd):
        return tk.Button(parent, text=text, command=cmd, bg=BLACK, fg=GREEN,
                         activebackground=GREEN, activeforeground=BLACK,
                         relief="flat", bd=1, highlightbackground=GREEN,
                         highlightthickness=1, font=FONT_B, cursor="hand2")

    def _entry(self, parent, width=12):
        return tk.Entry(parent, bg=BLACK, fg=GREEN, insertbackground=GREEN,
                        font=FONT, width=width, relief="flat",
                        highlightbackground=GREEN, highlightthickness=1)

    def _section(self, parent, title):
        f = tk.LabelFrame(parent, text=f" {title} ", bg=BLACK, fg=GREEN,
                          font=FONT_B, bd=1, relief="solid")
        f.pack(fill="x", padx=8, pady=5)
        return f

    # ---------- Aufbau ----------
    def _build(self):
        MatrixRain(self).pack(fill="x")
        self._label(self, "[ SKATE 4 // MOD MENU ]", FONT_T).pack(pady=(4, 0))
        self.status = self._label(self, "STATUS: GETRENNT", FONT, DIM)
        self.status.pack()

        row = tk.Frame(self, bg=BLACK)
        row.pack(pady=6)
        self._button(row, "VERBINDEN", self._attach).pack(side="left", padx=6)
        self._button(row, "TRENNEN", self._detach).pack(side="left", padx=6)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=6, pady=4)
        tab_mods = tk.Frame(nb, bg=BLACK)
        tab_scan = tk.Frame(nb, bg=BLACK)
        nb.add(tab_mods, text="MODS")
        nb.add(tab_scan, text="SCANNER")
        self._build_mods(tab_mods)
        self._build_scanner(tab_scan)

        sec = tk.LabelFrame(self, text=" CONSOLE ", bg=BLACK, fg=GREEN,
                            font=FONT_B, bd=1, relief="solid")
        sec.pack(fill="x", padx=12, pady=(0, 8))
        self.console = tk.Text(sec, height=7, bg=BLACK, fg=GREEN,
                               font=("Consolas", 9), insertbackground=GREEN,
                               bd=0, state="disabled")
        self.console.pack(fill="x", padx=6, pady=6)

    def _build_mods(self, tab):
        sec = self._section(tab, "PLAYER")
        self._slider(sec, "Speed-Multiplikator", "speed", 0.1, 10.0, 0.1)
        self._slider(sec, "Jump-Hoehe", "jump", 0.1, 10.0, 0.1)
        self.gravity = self._slider(sec, "Gravitation", "gravity", -30.0, -1.0, 0.1)

        sec = self._section(tab, "WELT")
        row = tk.Frame(sec, bg=BLACK)
        row.pack(fill="x", padx=8, pady=6)
        self._label(row, "Wetter:").pack(side="left")
        self.weather_var = tk.StringVar(value=list(self.cfg["weather_values"])[0])
        ttk.Combobox(row, textvariable=self.weather_var, state="readonly",
                     values=list(self.cfg["weather_values"]),
                     style="M.TCombobox", width=14, font=FONT).pack(side="left", padx=8)
        self._button(row, "SETZEN", self._set_weather).pack(side="left")
        self._slider(sec, "Tageszeit (0-24h)", "time_of_day", 0.0, 24.0, 0.25,
                     freeze=False)

        sec = self._section(tab, "PRESETS")
        row = tk.Frame(sec, bg=BLACK)
        row.pack(pady=6)
        for text, args in (("NORMAL", (1, 1, -9.81)), ("SUPER JUMP", (1, 6, -9.81)),
                           ("MOON", (1.5, 4, -2.5)), ("TURBO", (5, 2, -9.81))):
            self._button(row, text, lambda a=args: self._preset(*a)).pack(side="left", padx=4)

    def _build_scanner(self, tab):
        sec = self._section(tab, "SCAN")
        r1 = tk.Frame(sec, bg=BLACK)
        r1.pack(fill="x", padx=8, pady=4)
        self._label(r1, "Typ:").pack(side="left")
        self.s_type = tk.StringVar(value="float")
        ttk.Combobox(r1, textvariable=self.s_type, state="readonly",
                     values=["float", "int"], style="M.TCombobox",
                     width=7, font=FONT).pack(side="left", padx=6)
        self._label(r1, "Wert:").pack(side="left", padx=(8, 0))
        self.s_value = self._entry(r1)
        self.s_value.pack(side="left", padx=6)
        self._button(r1, "FIRST SCAN", self._first_scan).pack(side="left", padx=4)
        self._button(r1, "RESET", self._scan_reset).pack(side="left", padx=4)

        r2 = tk.Frame(sec, bg=BLACK)
        r2.pack(fill="x", padx=8, pady=4)
        self._label(r2, "Modus:").pack(side="left")
        self.s_mode = tk.StringVar(value="Exakt")
        ttk.Combobox(r2, textvariable=self.s_mode, state="readonly",
                     values=["Exakt", "Geaendert", "Unveraendert", "Groesser", "Kleiner"],
                     style="M.TCombobox", width=13, font=FONT).pack(side="left", padx=6)
        self._button(r2, "NEXT SCAN", self._next_scan).pack(side="left", padx=4)

        self.s_status = self._label(sec, "Bereit.", FONT, DIM)
        self.s_status.pack(anchor="w", padx=8, pady=(2, 6))

        sec = self._section(tab, "TREFFER")
        lf = tk.Frame(sec, bg=BLACK)
        lf.pack(fill="both", expand=True, padx=6, pady=6)
        sb = tk.Scrollbar(lf, bg=BLACK, troughcolor=BLACK)
        sb.pack(side="right", fill="y")
        self.listbox = tk.Listbox(lf, height=9, bg=BLACK, fg=GREEN, font=("Consolas", 9),
                                  selectbackground=DARKGREEN, selectforeground=GREEN,
                                  highlightbackground=GREEN, highlightthickness=1,
                                  bd=0, yscrollcommand=sb.set, exportselection=False)
        self.listbox.pack(side="left", fill="both", expand=True)
        sb.config(command=self.listbox.yview)

        sec = self._section(tab, "AKTION AUF AUSWAHL")
        r3 = tk.Frame(sec, bg=BLACK)
        r3.pack(fill="x", padx=8, pady=4)
        self._label(r3, "Neuer Wert:").pack(side="left")
        self.s_write = self._entry(r3, 10)
        self.s_write.pack(side="left", padx=6)
        self._button(r3, "SCHREIBEN", self._scan_write).pack(side="left", padx=4)
        r4 = tk.Frame(sec, bg=BLACK)
        r4.pack(fill="x", padx=8, pady=(2, 6))
        self._label(r4, "Zuweisen an:").pack(side="left")
        self.s_assign = tk.StringVar(value="speed")
        ttk.Combobox(r4, textvariable=self.s_assign, state="readonly",
                     values=list(self.cfg["features"]), style="M.TCombobox",
                     width=12, font=FONT).pack(side="left", padx=6)
        self._button(r4, "ZUWEISEN", self._scan_assign).pack(side="left", padx=4)

    def _slider(self, parent, text, name, lo, hi, step, freeze=True):
        default = self.cfg["features"][name]["default"]
        frame = tk.Frame(parent, bg=BLACK)
        frame.pack(fill="x", padx=8, pady=3)
        self._label(frame, text).pack(anchor="w")
        row = tk.Frame(frame, bg=BLACK)
        row.pack(fill="x")
        var = tk.DoubleVar(value=default)
        tk.Scale(row, from_=lo, to=hi, resolution=step, orient="horizontal",
                 variable=var, bg=BLACK, fg=GREEN, troughcolor=DARKGREEN,
                 highlightthickness=0, activebackground=GREEN, bd=0,
                 font=FONT, length=300,
                 command=lambda v, n=name: self.mem.write(n, float(v))
                 ).pack(side="left", fill="x", expand=True)
        if freeze:
            fv = tk.BooleanVar(value=False)
            tk.Checkbutton(row, text="HALTEN", variable=fv, bg=BLACK, fg=GREEN,
                           selectcolor=BLACK, activebackground=BLACK,
                           activeforeground=GREEN, font=FONT).pack(side="left", padx=6)
            self.freeze[name] = (fv, var)
        setattr(self, f"var_{name}", var)
        return var

    # ---------- Mod-Aktionen ----------
    def _set_weather(self):
        name = self.weather_var.get()
        val = self.cfg["weather_values"][name]
        self.log(f"Wetter -> {name} ({val})")
        self.mem.write("weather", val)

    def _preset(self, speed, jump, grav):
        self.var_speed.set(speed)
        self.var_jump.set(jump)
        self.var_gravity.set(grav)
        for n, v in (("speed", speed), ("jump", jump), ("gravity", grav)):
            self.mem.write(n, v)
        self.log(f"Preset: speed={speed} jump={jump} gravity={grav}")

    def _attach(self):
        ok = self.mem.attach()
        self.status.config(text="STATUS: VERBUNDEN" if ok else "STATUS: DEMO-MODUS",
                           fg=GREEN if ok else DIM)

    def _detach(self):
        self.mem.detach()
        self.scanner.reset()
        self.listbox.delete(0, "end")
        self.status.config(text="STATUS: GETRENNT", fg=DIM)

    def _freeze_loop(self):
        while self.running:
            if self.mem.attached:
                for name, (flag, var) in list(self.freeze.items()):
                    try:
                        if flag.get():
                            self.mem.write(name, var.get())
                    except Exception:
                        pass
            time.sleep(0.05)

    # ---------- Scanner-Aktionen ----------
    def _parse(self, text, dtype):
        text = text.strip().replace(",", ".")
        return float(text) if dtype == "float" else int(float(text))

    def _progress(self, msg):
        self.after(0, lambda: self.s_status.config(text=msg))

    def _run_scan(self, job):
        if self.busy:
            self.log("Scan laeuft noch...")
            return
        if not self.mem.attached:
            self.log("Erst mit dem Spiel VERBINDEN (Scanner braucht den Prozess).")
            return
        self.busy = True

        def worker():
            try:
                n = job()
                self.after(0, lambda: self._finish_scan(n))
            except Exception as e:
                self.log(f"Scan-Fehler: {e}")
            finally:
                self.busy = False

        threading.Thread(target=worker, daemon=True).start()

    def _first_scan(self):
        dtype = self.s_type.get()
        try:
            val = self._parse(self.s_value.get(), dtype)
        except ValueError:
            self.log("Ungueltiger Wert.")
            return
        self._run_scan(lambda: self.scanner.first_scan(dtype, val, self._progress))

    def _next_scan(self):
        if not self.scanner.results:
            self.log("Erst einen FIRST SCAN machen.")
            return
        mode = self.s_mode.get()
        val = None
        if mode == "Exakt":
            try:
                val = self._parse(self.s_value.get(), self.scanner.dtype)
            except ValueError:
                self.log("Ungueltiger Wert.")
                return
        self._run_scan(lambda: self.scanner.next_scan(mode, val, self._progress))

    def _scan_reset(self):
        self.scanner.reset()
        self.listbox.delete(0, "end")
        self.s_status.config(text="Zurueckgesetzt.")

    def _finish_scan(self, n):
        self.s_status.config(text=f"{n} Treffer.")
        self.log(f"Scan fertig: {n} Treffer.")
        self.listbox.delete(0, "end")
        dtype = self.scanner.dtype
        for addr, _old in self.scanner.results[:500]:
            try:
                cur = self.scanner.unpack(dtype, self.mem.read_bytes(addr, 4))
                cur = f"{cur:.4f}" if dtype == "float" else str(cur)
            except Exception:
                cur = "?"
            tag = (f"  [Modul+0x{addr - self.mem.base:X}]"
                   if self.mem.in_module(addr) else "")
            self.listbox.insert("end", f"0x{addr:X}   {cur}{tag}")
        if n > 500:
            self.log("Es werden nur die ersten 500 Treffer angezeigt - weiter filtern.")

    def _selected(self):
        sel = self.listbox.curselection()
        if not sel:
            self.log("Erst einen Treffer in der Liste markieren.")
            return None
        return self.scanner.results[sel[0]][0]

    def _scan_write(self):
        addr = self._selected()
        if addr is None:
            return
        dtype = self.scanner.dtype
        try:
            val = self._parse(self.s_write.get(), dtype)
        except ValueError:
            self.log("Ungueltiger Wert.")
            return
        if self.mem.write_at(addr, dtype, val):
            self.log(f"0x{addr:X} <- {val}")

    def _scan_assign(self):
        addr = self._selected()
        if addr is None:
            return
        name = self.s_assign.get()
        feat = self.cfg["features"][name]
        feat["type"] = self.scanner.dtype
        if self.mem.in_module(addr):
            feat["chain"] = [addr - self.mem.base]
            self.mem.overrides.pop(name, None)
            save_config(self.cfg)
            self.log(f"{name} -> Modul+0x{addr - self.mem.base:X} (dauerhaft gespeichert)")
        else:
            self.mem.overrides[name] = addr
            save_config(self.cfg)
            self.log(f"{name} -> 0x{addr:X} (nur diese Sitzung, Heap-Adresse)")

    # ---------- Log ----------
    def log(self, msg):
        def _do():
            if not hasattr(self, "console"):
                return
            self.console.config(state="normal")
            self.console.insert("end", f"> {msg}\n")
            self.console.see("end")
            self.console.config(state="disabled")
        try:
            self.after(0, _do)
        except Exception:
            pass

    def _close(self):
        self.running = False
        self.mem.detach()
        self.destroy()


if __name__ == "__main__":
    ModMenu().mainloop()