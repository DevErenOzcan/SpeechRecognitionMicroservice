import os
import subprocess
import time
import pytest
import websockets
import asyncio
import signal
import socket

# === Ayarlar ===
DJANGO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../django_server"))
WAV_FILE = os.path.join(os.path.dirname(__file__), "test.wav")
DAPHNE_PORT = 8080
daphne_process = None

# === Yardımcı Fonksiyon: Daphne ayakta mı kontrol et ===
def wait_for_port(host, port, timeout=10):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    raise RuntimeError(f"{host}:{port} bağlantısı zaman aşımına uğradı.")

# === Daphne'yi başlatan fixture ===
@pytest.fixture(scope="module", autouse=True)
def start_daphne():
    global daphne_process

    env = os.environ.copy()
    env["DJANGO_SETTINGS_MODULE"] = "django_server.settings"
    env["PYTHONUNBUFFERED"] = "1"

    daphne_command = [
        "daphne",
        "-b", "127.0.0.1",
        "-p", str(DAPHNE_PORT),
        "django_server.asgi:application"
    ]

    daphne_process = subprocess.Popen(
        daphne_command,
        cwd=DJANGO_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        preexec_fn=os.setsid  # process grubunda başlat (Linux için)
    )

    # Daphne portu açılana kadar bekle
    try:
        wait_for_port("127.0.0.1", DAPHNE_PORT, timeout=10)
    except RuntimeError as e:
        # Daphne loglarını göster (debug kolaylığı için)
        if daphne_process:
            output, _ = daphne_process.communicate(timeout=3)
            print("Daphne çıktı:\n", output.decode())
        raise e

    yield  # Testleri çalıştır

    # Test sonrası Daphne'yi kapat
    if daphne_process:
        os.killpg(os.getpgid(daphne_process.pid), signal.SIGTERM)
        daphne_process.wait()

# === Test: WebSocket bağlantısı kur, WAV dosyası gönder ===
@pytest.mark.asyncio
async def test_ws_with_wav():
    uri = f"ws://127.0.0.1:{DAPHNE_PORT}/meeting/"
    assert os.path.exists(WAV_FILE), "test.wav bulunamadı."

    async with websockets.connect(uri) as websocket:
        print("WebSocket bağlantısı kuruldu.")

        with open(WAV_FILE, "rb") as f:
            data = f.read()

        await websocket.send(data)
        print("test.wav gönderildi.")

        response = await websocket.recv()
        print("Gelen cevap:", response)

        assert response == "null", f"Beklenen 'null', ama gelen: {response}"
