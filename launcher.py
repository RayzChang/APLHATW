"""
台股交易推手 — 控制台啟動器 (開發模式)

啟動後端 API，並同時啟動前端 Dev Server。
"""

import webbrowser
import threading
import time
import subprocess
import os

def run_api():
    import uvicorn
    from config.settings import API_PORT
    try:
        uvicorn.run("api.app:app", host="0.0.0.0", port=API_PORT, log_level="info")
    except OSError as e:
        if "10048" in str(e) or "address already in use" in str(e).lower():
            alt_port = API_PORT + 1
            print(f"Port {API_PORT} in use, trying {alt_port}...")
            os.environ["API_PORT"] = str(alt_port)
            uvicorn.run("api.app:app", host="0.0.0.0", port=alt_port, log_level="info")
        else:
            raise

def run_frontend():
    os.chdir(os.path.join(os.path.dirname(__file__), "frontend"))
    subprocess.run("npm run dev", shell=True)

if __name__ == "__main__":
    print("=" * 50)
    print("台股交易推手 - 啟動中...")
    print("=" * 50)
    
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()
    
    time.sleep(2)
    
    frontend_thread = threading.Thread(target=run_frontend, daemon=True)
    frontend_thread.start()
    
    time.sleep(3)
    # The Vite dev server defaults to port 5173
    url = f"http://localhost:5173"
    webbrowser.open(url)
    print(f"前端已啟動: {url}")
    print("=" * 50)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n已停止")
