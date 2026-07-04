"""桌面啟動器 — 打包後的進入點:起本機伺服器,就緒後自動開瀏覽器。

行為:
- 若 port 已被占用(通常代表程式已在執行),直接開瀏覽器連過去,不再起第二份。
- 否則於背景執行緒等 server 就緒後開瀏覽器,主執行緒跑 uvicorn。
- 關閉方式:關閉本視窗(console)即停止伺服器;資料都在 data/animal_an.db。
"""
import socket
import threading
import time
import webbrowser

import uvicorn

from web.app import app

HOST = "127.0.0.1"
PORT = 8000


def _port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def _open_when_ready(host: str, port: int, url: str, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _port_in_use(host, port):
            webbrowser.open(url)
            return
        time.sleep(0.3)


def main() -> None:
    url = f"http://{HOST}:{PORT}"
    if _port_in_use(HOST, PORT):
        print(f"Animal-AN ERP 已在執行,開啟瀏覽器: {url}")
        webbrowser.open(url)
        return

    print("Animal-AN 進銷存系統啟動中…")
    print(f"瀏覽器將自動開啟 {url}(關閉本視窗即停止系統)")
    threading.Thread(
        target=_open_when_ready, args=(HOST, PORT, url), daemon=True).start()
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
