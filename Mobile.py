import socket
import os
import time
import sys

# ═══════════════════════════════════════════════
#  CONFIGURATION
#  Phone : 192.168.0.185  (this device)
#  PC    : 192.168.0.101  (sender)
# ═══════════════════════════════════════════════
HOST = '0.0.0.0'   # listen on all interfaces
PORT = 6666

# ── ANSI colors (work in Pydroid 3 terminal) ──
R  = "\033[0m"          # reset
B  = "\033[1m"          # bold
G  = "\033[92m"         # green
Y  = "\033[93m"         # yellow
RD = "\033[91m"         # red
C  = "\033[96m"         # cyan
P  = "\033[95m"         # purple
DM = "\033[2m"          # dim


def clear():
    os.system("cls" if sys.platform == "win32" else "clear")


# ═══════════════════════════════════════════════
#  BIG STATE SCREENS
# ═══════════════════════════════════════════════

def show_idle(pkt, uptime):
    clear()
    print(f"""
{G}{B}
╔══════════════════════════════════════════╗
║                                          ║
║          ●   S Y S T E M                ║
║              I D L E                    ║
║                                          ║
║       Environment is quiet.             ║
║       No threats detected.              ║
║                                          ║
╚══════════════════════════════════════════╝
{R}
  {DM}PKT #{pkt:05d}   UPTIME {uptime}   TOKEN [0]{R}
""")


def show_warning(pkt, uptime):
    clear()
    print(f"""
{Y}{B}
╔══════════════════════════════════════════╗
║                                          ║
║       ◆   W A R N I N G                 ║
║                                          ║
║       High acoustic activity            ║
║       detected. Monitor closely.        ║
║                                          ║
╚══════════════════════════════════════════╝
{R}
  {DM}PKT #{pkt:05d}   UPTIME {uptime}   TOKEN [1]{R}
""")


def show_critical(pkt, uptime, conn):
    clear()
    print(f"""
{RD}{B}
╔══════════════════════════════════════════╗
║                                          ║
║   ✖  C R I T I C A L   B R E A C H    ║
║                                          ║
║   EXTREME noise detected!               ║
║   Sending SHUTDOWN to PC...             ║
║                                          ║
╚══════════════════════════════════════════╝
{R}
  {DM}PKT #{pkt:05d}   UPTIME {uptime}   TOKEN [111]{R}
""")
    # Send shutdown order to PC
    try:
        conn.send("SHUTDOWN".encode())
        print(f"  {RD}{B}⚡  SHUTDOWN command sent → PC [192.168.0.101]{R}\n")
    except OSError:
        pass


# ═══════════════════════════════════════════════
#  SERVER MAIN
# ═══════════════════════════════════════════════

def start_server():
    pkt        = 0
    last_token = None
    t0         = time.time()

    clear()
    print(f"""
{P}{B}
╔══════════════════════════════════════════╗
║   ENSTA · ACOUSTIC INTELLIGENCE         ║
║   PHONE NODE  ·  192.168.0.185          ║
║   PORT {PORT}                              ║
╚══════════════════════════════════════════╝
{R}
  {C}Listening for PC [192.168.0.101] ...{R}
""")

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(1)

    try:
        conn, addr = server.accept()
    except KeyboardInterrupt:
        print(f"\n  {DM}Interrupted.{R}")
        server.close()
        return

    clear()
    print(f"\n  {G}{B}✔  CONNECTED — PC @ {addr[0]}:{addr[1]}{R}\n")
    time.sleep(1)

    # ── Receive loop ──────────────────────────────────────────────────────────
    while True:
        try:
            raw = conn.recv(1024)
            if not raw:
                print(f"\n  {Y}PC disconnected.{R}")
                break

            token = raw.decode().strip()
            pkt  += 1

            # Format uptime
            elapsed = int(time.time() - t0)
            m, s    = divmod(elapsed, 60)
            uptime  = f"{m:02d}:{s:02d}"

            # Only redraw when state changes (avoids flicker)
            if token != last_token:
                last_token = token
                if token == "0":
                    show_idle(pkt, uptime)
                elif token == "1":
                    show_warning(pkt, uptime)
                elif token == "111":
                    show_critical(pkt, uptime, conn)
                else:
                    clear()
                    print(f"\n  {DM}Unknown token: [{token}]{R}\n")
            else:
                # Same state — just update the packet counter line quietly
                print(f"\r  {DM}PKT #{pkt:05d}   UPTIME {uptime}   TOKEN [{token}]{R}",
                      end='', flush=True)

        except KeyboardInterrupt:
            print(f"\n  {DM}Stopped by user.{R}")
            break
        except (ConnectionResetError, BrokenPipeError, OSError):
            print(f"\n  {Y}Connection lost.{R}")
            break

    conn.close()
    server.close()
    print(f"\n  {DM}Server closed.{R}\n")


# ═══════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════
if __name__ == "__main__":
    start_server()