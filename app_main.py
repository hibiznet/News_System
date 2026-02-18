# app_main.py
import socket, threading, time, webbrowser, os, sys
from app import create_app, start_background_jobs
from pathlib import Path
from PIL import Image, ImageDraw

HOST = "127.0.0.1"
PORT = 5000

# 전역 서버 관리
_app = None
_server_thread = None
_running = True
_console_visible = False  # 콘솔 창 처음에는 숨김

# Windows 콘솔 제어
def toggle_console():
    """Windows 콘솔 창 표시/숨김 토글"""
    global _console_visible
    try:
        if sys.platform == 'win32':
            import ctypes
            kernel32 = ctypes.windll.kernel32
            hwnd = kernel32.GetConsoleWindow()
            if hwnd:
                if _console_visible:
                    ctypes.windll.user32.ShowWindow(hwnd, 0)
                    _console_visible = False
                else:
                    ctypes.windll.user32.ShowWindow(hwnd, 5)
                    _console_visible = True
    except Exception as e:
        print(f"콘솔 토글 실패: {e}")

def hide_console():
    """콘솔 창 숨기기"""
    global _console_visible
    try:
        if sys.platform == 'win32' and _console_visible:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            hwnd = kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)
                _console_visible = False
    except:
        pass

def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((HOST, port)) == 0

def create_tray_icon():
    """시스템 트레이용 아이콘 생성"""
    try:
        import pystray
        
        # 간단한 아이콘 생성 (파란색 배경에 흰 텍스트)
        size = (64, 64)
        image = Image.new('RGB', size, color='#1e7bff')
        draw = ImageDraw.Draw(image)
        # NS 텍스트 (News System)
        draw.text((20, 20), "NS", fill='white')
        
        return image
    except:
        # pystray 없으면 None 반환
        return None

def open_admin(icon=None, item=None):
    """관리자 패널 열기"""
    webbrowser.open(f"http://{HOST}:{PORT}/admin/console.html")

def open_home(icon=None, item=None):
    """홈페이지 열기"""
    webbrowser.open(f"http://{HOST}:{PORT}/")

def toggle_console_menu(icon=None, item=None):
    """트레이 메뉴에서 콘솔 토글"""
    toggle_console()

def exit_app(icon=None, item=None):
    """앱 종료"""
    global _running, _app
    _running = False
    if icon:
        icon.stop()
    # 0.5초 후 프로세스 종료 (스레드 생성 피함)
    import atexit
    atexit.register(lambda: os.kill(os.getpid(), 9) if sys.platform == 'win32' else os.kill(os.getpid(), 15))

def setup_tray():
    """시스템 트레이 설정"""
    try:
        import pystray
        
        icon_image = create_tray_icon()
        if icon_image is None:
            return None
        
        menu = (
            pystray.MenuItem('🏠 대시보드', open_home),
            pystray.MenuItem('🎛️ 관리 패널', open_admin),
            pystray.MenuItem('-', None),
            pystray.MenuItem('👁️ 로그 숨기기/보기', toggle_console_menu),
            pystray.MenuItem('-', None),
            pystray.MenuItem('❌ 끝내기', exit_app),
        )
        
        icon = pystray.Icon(
            "News_System",
            icon_image,
            "News_System - SOOP 방송 대시보드",
            menu
        )
        
        return icon
    except ImportError:
        print("⚠️ pystray 라이브러리가 설치되지 않았습니다.")
        print("Windows Tray 기능을 사용하려면: pip install pystray")
        return None

def main():
    global _app, _server_thread, _running
    
    if port_in_use(PORT):
        webbrowser.open(f"http://{HOST}:{PORT}/")
        return

    _app = create_app()
    start_background_jobs(_app)

    def run_server():
        global _running
        _app.run(host=HOST, port=PORT, threaded=True, use_reloader=False)

    _server_thread = threading.Thread(target=run_server, daemon=False)
    _server_thread.start()
    time.sleep(0.8)
    webbrowser.open(f"http://{HOST}:{PORT}/")

    # Windows 환경이면 트레이 아이콘 설정
    if sys.platform == 'win32':
        tray_icon = setup_tray()
        if tray_icon:
            print("📌 시스템 트레이에서 News_System을 찾을 수 있습니다.")
            print("💡 팁: 트레이 메뉴에서 '로그 숨기기'를 선택하면 콘솔 창이 숨겨집니다.")
            try:
                tray_icon.run()
            except KeyboardInterrupt:
                exit_app()
        else:
            # 트레이 실패하면 그냥 대기
            while _running:
                time.sleep(1)
    else:
        # Linux/Mac: 트레이 없이 그냥 실행
        while _running:
            time.sleep(1)
if __name__ == "__main__":
    main()
