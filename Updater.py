import requests
import os
import sys
import time
import subprocess

DOWNLOAD_URL = "https://github.com/JwInventur/user_ui/raw/refs/heads/main/User_UI.exe"
EXE_NAME = "User_UI.exe" 

def download_new_exe(url, filename):
    print(f"Lade neue Version von {url} ...")
    response = requests.get(url, stream=True)
    response.raise_for_status()
    with open(filename + ".new", "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    print("Download abgeschlossen.")

def replace_exe(filename):
    # Versuche, die alte EXE zu ersetzen
    if os.path.exists(filename):
        try:
            os.remove(filename)
            print(f"{filename} entfernt.")
        except Exception as e:
            print(f"Fehler beim Entfernen der alten EXE: {e}")
            sys.exit(1)
    os.rename(filename + ".new", filename)
    print(f"Neue EXE wurde zu {filename} verschoben.")

def start_new_exe(filename):
    print(f"Starte {filename} ...")
    subprocess.Popen([filename], shell=True)

if __name__ == "__main__":
    # Kurze Wartezeit, damit das Hauptprogramm sicher beendet ist
    time.sleep(1)
    try:
        download_new_exe(DOWNLOAD_URL, EXE_NAME)
        replace_exe(EXE_NAME)
        start_new_exe(EXE_NAME)
    except Exception as e:
        print(f"Update fehlgeschlagen: {e}")
    print("Updater beendet sich.")
    sys.exit()
