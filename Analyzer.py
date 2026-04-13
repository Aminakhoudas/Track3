import sounddevice as sd
import numpy as np
import socket
import time
import os
import sys
import tkinter as tk
from threading import Thread
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# ═══════════════════════════════════════════════
#  CONFIGURATION
#  PC    : 192.168.0.101  (this machine)
#  Phone : 192.168.0.185  (Pydroid 3)
# ═══════════════════════════════════════════════
PHONE_IP = '192.168.0.185'
PORT     = 6666

# Thresholds for token classification
THRESHOLD_WARN = 0.6    # above this  → WARNING
THRESHOLD_CRIT = 1.8    # above this  → CRITICAL


class Analyzer:
    def __init__(self, root):
        self.root = root
        self.root.title("ENSTA · ACOUSTIC INTELLIGENCE  —  PC NODE  192.168.0.101")
        self.root.geometry("950x620")
        self.root.configure(bg='#050505')

        # Rolling waveform history (200 points)
        self.history = [0.0] * 200

        # Thread-safe slot: network thread writes here, main thread reads
        self._pending = None

        self._build_ui()
        self.root.after(40, self._poll)   # poll every 40ms on main thread

    # ─────────────────────────────────────────────
    #  UI
    # ─────────────────────────────────────────────
    def _build_ui(self):
        # ── Header ──────────────────────────────
        hdr = tk.Frame(self.root, bg='#050505')
        hdr.pack(fill=tk.X)
        tk.Frame(hdr, height=3, bg='#bc13fe').pack(fill=tk.X)   # neon top line

        tk.Label(hdr, text="ENSTA  ACOUSTIC  INTELLIGENCE",
                 fg='#bc13fe', bg='#050505',
                 font=('Courier New', 20, 'bold')).pack(pady=(12, 4))
        tk.Label(hdr, text="PC NODE  ·  192.168.0.101   →   PHONE  192.168.0.185",
                 fg='#444466', bg='#050505',
                 font=('Courier New', 9)).pack(pady=(0, 10))

        # ── Waveform chart ───────────────────────
        chart_frame = tk.Frame(self.root, bg='#0a0a12',
                               highlightbackground='#1a1a2e', highlightthickness=1)
        chart_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=(0, 10))

        self.fig, self.ax = plt.subplots(figsize=(8, 3.6), facecolor='#0a0a12')
        self.ax.set_facecolor('#0a0a12')

        # Main waveform line
        self.line_plot, = self.ax.plot(self.history, color='#00e5ff', linewidth=1.8)

        # Threshold lines
        self.ax.axhline(y=THRESHOLD_WARN, color='#ffb300', linewidth=0.8,
                        linestyle='--', alpha=0.6, label='WARNING threshold')
        self.ax.axhline(y=THRESHOLD_CRIT, color='#ff1744', linewidth=0.8,
                        linestyle='--', alpha=0.6, label='CRITICAL threshold')

        self.ax.set_xlim(0, 199)
        self.ax.set_ylim(0, 3)
        self.ax.set_ylabel("Intensity", color='#444466', fontsize=8)
        self.ax.set_xlabel("Time →", color='#444466', fontsize=8)
        self.ax.grid(color='#0f0f20', linestyle='-', linewidth=0.5)
        for spine in self.ax.spines.values():
            spine.set_color('#1a1a2e')
        self.ax.tick_params(colors='#444466', labelsize=7)
        self.ax.legend(loc='upper right', fontsize=7,
                       facecolor='#0a0a12', edgecolor='#1a1a2e',
                       labelcolor='#888899')
        self.fig.tight_layout(pad=1.5)

        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # ── Injection buttons ────────────────────
        btn_row = tk.Frame(self.root, bg='#050505')
        btn_row.pack(fill=tk.X, padx=30, pady=(0, 8))

        tk.Label(btn_row, text="SIMULATION:", fg='#444466', bg='#050505',
                 font=('Courier New', 9)).pack(side=tk.LEFT, padx=(0, 12))

        for label, cmd, fg in [
            ("● LIVE MIC",       self._live,    '#00e5ff'),
            ("◆ INJECT WARNING", self._warn,    '#ffb300'),
            ("✖ INJECT CRITICAL",self._crit,    '#ff1744'),
        ]:
            tk.Button(btn_row, text=label, command=cmd,
                      bg='#0d0d1a', fg=fg, activebackground='#1a1a2e',
                      activeforeground=fg, relief=tk.FLAT,
                      font=('Courier New', 10, 'bold'),
                      padx=16, pady=6, cursor='hand2',
                      highlightbackground='#1a1a2e',
                      highlightthickness=1).pack(side=tk.LEFT, padx=6)

        self._sim_token = None   # None = live mic

        # ── Status bar ───────────────────────────
        bar = tk.Frame(self.root, bg='#0d0d1a', height=44)
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        tk.Frame(bar, height=1, bg='#1a1a2e').pack(fill=tk.X)

        self.dot = tk.Label(bar, text='●', fg='#00e5ff',
                            bg='#0d0d1a', font=('Arial', 14))
        self.dot.pack(side=tk.LEFT, padx=(20, 6))

        self.status = tk.Label(bar, text='INITIALIZING...',
                               fg='#ccccdd', bg='#0d0d1a',
                               font=('Courier New', 11))
        self.status.pack(side=tk.LEFT)

        self.intlbl = tk.Label(bar, text='INT: 0.000',
                               fg='#bc13fe', bg='#0d0d1a',
                               font=('Courier New', 11, 'bold'))
        self.intlbl.pack(side=tk.RIGHT, padx=24)

    # ─────────────────────────────────────────────
    #  Simulation buttons
    # ─────────────────────────────────────────────
    def _live(self):
        self._sim_token = None
        self._set_status('LIVE MIC STREAM', '#00e5ff')

    def _warn(self):
        self._sim_token = '1'
        self._set_status('SIM: WARNING injected', '#ffb300')

    def _crit(self):
        self._sim_token = '111'
        self._set_status('SIM: CRITICAL injected', '#ff1744')

    def _set_status(self, msg, color):
        self.status.config(text=msg, fg=color)
        self.dot.config(fg=color)

    # ─────────────────────────────────────────────
    #  Thread-safe update pipeline
    # ─────────────────────────────────────────────
    def push(self, intensity, token):
        """Called from network thread — only writes to slot."""
        self._pending = (intensity, token)

    def _poll(self):
        """Runs on main thread every 40ms — applies pending update."""
        if self._pending is not None:
            intensity, token = self._pending
            self._pending = None
            self._draw(intensity, token)
        self.root.after(40, self._poll)

    def _draw(self, intensity, token):
        """Updates chart and labels — always on main thread."""
        # Slide history
        self.history.append(intensity)
        self.history.pop(0)

        # Color by state
        color = ('#00e5ff' if token == '0'
                 else '#ffb300' if token == '1'
                 else '#ff1744')

        self.line_plot.set_ydata(self.history)
        self.line_plot.set_color(color)
        self.canvas.draw_idle()

        state = {'0': 'IDLE', '1': 'WARNING', '111': 'CRITICAL'}.get(token, token)
        self.dot.config(fg=color)
        self.intlbl.config(text=f'INT: {intensity:.3f}', fg=color)
        if self._sim_token is None:
            self.status.config(
                text=f'LIVE  ·  {state}  ·  sending to phone 192.168.0.185',
                fg=color)

    # ─────────────────────────────────────────────
    #  Shutdown (scheduled on main thread by network thread)
    # ─────────────────────────────────────────────
    def shutdown(self):
        overlay = tk.Toplevel(self.root)
        overlay.attributes('-fullscreen', True)
        overlay.configure(bg='black')
        tk.Label(overlay, text='⚠  CRITICAL BREACH',
                 fg='#ff1744', bg='black',
                 font=('Courier New', 34, 'bold')).pack(expand=True)
        cnt = tk.Label(overlay, text='', fg='#ff1744', bg='black',
                       font=('Courier New', 20))
        cnt.pack()

        def cd(n):
            if n > 0:
                cnt.config(text=f'SHUTDOWN IN {n}s')
                self.root.after(1000, cd, n - 1)
            else:
                os.system('shutdown /s /t 1' if sys.platform == 'win32'
                          else 'shutdown -h now')
        cd(5)


# ═══════════════════════════════════════════════
#  NETWORK THREAD
# ═══════════════════════════════════════════════
def network_loop(app: Analyzer):
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.settimeout(5)
    connected = False

    try:
        client.connect((PHONE_IP, PORT))
        client.settimeout(0.05)
        connected = True
        app.root.after(0, lambda: app._set_status(
            '✔  LINKED TO PHONE  192.168.0.185', '#00e5ff'))
    except (ConnectionRefusedError, socket.timeout, OSError):
        app.root.after(0, lambda: app._set_status(
            'OFFLINE — phone not reachable', '#ff1744'))

    while True:
        # ── Capture audio ──────────────────────────────────────────────────
        try:
            rec = sd.rec(int(0.1 * 44100), samplerate=44100, channels=1)
            sd.wait()
            intensity = float(np.linalg.norm(rec))
        except Exception:
            intensity = 0.0

        # ── Classify token ─────────────────────────────────────────────────
        if app._sim_token is not None:
            # Simulation override
            token = app._sim_token
            intensity = 2.5 if token == '111' else (1.0 if token == '1' else 0.2)
        else:
            token = ('111' if intensity > THRESHOLD_CRIT
                     else '1' if intensity > THRESHOLD_WARN
                     else '0')

        # ── Send to phone ──────────────────────────────────────────────────
        if connected:
            try:
                client.send(token.encode())
                msg = client.recv(1024).decode()
                if 'SHUTDOWN' in msg:
                    app.root.after(0, app.shutdown)
                    break
            except socket.timeout:
                pass
            except OSError:
                connected = False

        # ── Update UI ──────────────────────────────────────────────────────
        app.push(intensity, token)
        time.sleep(0.01)


# ═══════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════
if __name__ == '__main__':
    root = tk.Tk()
    app  = Analyzer(root)
    Thread(target=network_loop, args=(app,), daemon=True).start()
    root.mainloop()