# app_main.py
import socket, threading, time, webbrowser
from app import create_app, start_background_jobs

HOST = "127.0.0.1"
PORT = 5000

def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((HOST, port)) == 0

def main():
    if port_in_use(PORT):
        webbrowser.open(f"http://{HOST}:{PORT}/")
        return

    app = create_app()
    start_background_jobs(app)

    def run_server():
        app.run(host=HOST, port=PORT, threaded=True)

    threading.Thread(target=run_server, daemon=True).start()
    time.sleep(0.8)
    webbrowser.open(f"http://{HOST}:{PORT}/")

    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()
