"""Keeps the Scouts Board proxy alive.

Runs silently (pythonw, no console). Every few seconds it checks whether the
proxy is answering on its port; if not, it (re)starts proxy.py. Launched at
logon from the Windows Startup folder, so the local app is always up.
"""
import os, sys, time, socket, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get('PORT', '8000'))
HOST = '127.0.0.1'


def proxy_up():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1.5)
    try:
        s.connect((HOST, PORT))
        return True
    except OSError:
        return False
    finally:
        s.close()


def start_proxy():
    # sys.executable is pythonw.exe here -> proxy runs with no console window
    flags = 0x08000000 if os.name == 'nt' else 0  # CREATE_NO_WINDOW
    subprocess.Popen([sys.executable, os.path.join(HERE, 'proxy.py')],
                     cwd=HERE, creationflags=flags)


if __name__ == '__main__':
    while True:
        try:
            if not proxy_up():
                start_proxy()
                time.sleep(4)  # give it a moment to bind before re-checking
        except Exception:
            pass
        time.sleep(20)
