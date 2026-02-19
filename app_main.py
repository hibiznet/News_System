# app_main.py
import socket, threading, time, webbrowser, os, sys
import requests
from app import create_app, start_background_jobs
from pathlib import Path
from PIL import Image, ImageDraw
import ctypes
from datetime import datetime

HOST = "127.0.0.1"
PORT = 5000
APP_VERSION = "1.0.0"

# 전역 서버 관리
_app = None
_server_thread = None
_running = True
_console_visible = False  # 콘솔 창 처음에는 숨김
_console_hwnd = None  # 콘솔 윈도우 핸들 캐시

# ==========================================
# 로깅 유틸리티
# ==========================================

# 로그 파일 경로 (AppData)
_LOG_DIR = None
_LOG_FILE = None

def _init_log_file():
    """로그 파일 디렉토리 초기화"""
    global _LOG_DIR, _LOG_FILE
    try:
        _LOG_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "News_System" / "logs"
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        _LOG_FILE = _LOG_DIR / "app.log"
    except Exception as e:
        print(f"[로그 파일 초기화 실패] {e}")

def _write_log(level: str, msg: str):
    """로그를 파일과 콘솔에 기록"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {level} {msg}"
    print(log_msg)
    
    # 파일에도 기록
    try:
        if _LOG_FILE:
            with open(_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(log_msg + "\n")
    except:
        pass  # 파일 쓰기 실패는 무시

def log_info(msg: str):
    """정보 로그 출력"""
    _write_log("ℹ️ ", msg)

def log_success(msg: str):
    """성공 로그 출력"""
    _write_log("✅", msg)

def log_warning(msg: str):
    """경고 로그 출력"""
    _write_log("⚠️ ", msg)

def log_error(msg: str):
    """에러 로그 출력"""
    _write_log("❌", msg)

def log_action(msg: str):
    """액션 로그 출력"""
    _write_log("🔧", msg)

# 모듈 로드 시 로그 파일 초기화
_init_log_file()

# ==========================================
# Windows 콘솔 제어
# ==========================================
def get_console_hwnd():
    """콘솔 윈도우 핸들 획득 (캐시)"""
    global _console_hwnd
    if _console_hwnd is None:
        try:
            if sys.platform == 'win32':
                kernel32 = ctypes.windll.kernel32
                hwnd = kernel32.GetConsoleWindow()
                if hwnd and hwnd != 0:  # 유효한 핸들인지 확인
                    _console_hwnd = hwnd
                    log_info("콘솔 윈도우 핸들 획득 완료")
                else:
                    log_warning("콘솔 윈도우가 존재하지 않습니다 (exe로 실행된 것으로 보임)")
                    _console_hwnd = 0  # 명시적으로 없음으로 표시
        except Exception as e:
            log_error(f"콘솔 핸들 획득 실패: {type(e).__name__}: {str(e)}")
            _console_hwnd = 0
    return _console_hwnd if _console_hwnd != 0 else None

def toggle_console():
    """Windows 콘솔 창 표시/숨김 토글"""
    global _console_visible
    try:
        if sys.platform != 'win32':
            log_warning("Windows가 아닌 플랫폼에서는 콘솔 제어 미지원")
            return
        
        hwnd = get_console_hwnd()
        if not hwnd:
            log_warning("콘솔 윈도우를 찾을 수 없습니다. (exe로 실행된 경우, 별도의 콘솔 창이 없을 수 있습니다)")
            log_info("💡 팁: 콘솔 로그는 트레이 아이콘 우클릭 > 관리 패널에서 확인할 수 있습니다.")
            return
        
        # 토글: 현재 상태 반대로 설정
        if _console_visible:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
            _console_visible = False
            log_success("콘솔 창을 숨겼습니다")
        else:
            ctypes.windll.user32.ShowWindow(hwnd, 1)  # SW_SHOWNORMAL
            _console_visible = True
            log_success("콘솔 창을 표시했습니다")
    except Exception as e:
        log_error(f"콘솔 토글 실패: {type(e).__name__}: {str(e)}")

def hide_console():
    """콘솔 창 숨기기"""
    global _console_visible
    try:
        if sys.platform != 'win32':
            return
        
        hwnd = get_console_hwnd()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
            _console_visible = False
            log_info("콘솔 창을 숨겼습니다")
        # hwnd가 없으면 (exe 실행 시) 조용히 무시
    except Exception as e:
        log_warning(f"콘솔 숨기기 오류: {type(e).__name__}: {str(e)}")

def port_in_use(port: int) -> bool:
    """포트 사용 여부 확인"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            result = s.connect_ex((HOST, port))
            in_use = result == 0
            if in_use:
                log_warning(f"포트 {port}이 이미 사용 중입니다")
            return in_use
    except Exception as e:
        log_error(f"포트 확인 오류: {type(e).__name__}: {str(e)}")
        return True  # 오류 시 포트가 사용 중인 것으로 가정 (안전)

def create_tray_icon():
    """시스템 트레이용 아이콘 생성"""
    try:
        # 간단한 아이콘 생성 (파란색 배경에 흰 텍스트)
        size = (64, 64)
        image = Image.new('RGB', size, color='#1e7bff')
        draw = ImageDraw.Draw(image)
        # NS 텍스트 (News System)
        draw.text((20, 20), "NS", fill='white')
        
        log_info("트레이 아이콘 생성 완료")
        return image
    except Exception as e:
        log_error(f"트레이 아이콘 생성 실패: {type(e).__name__}: {str(e)}")
        return None

def open_admin(icon=None, item=None):
    """관리자 패널 열기"""
    try:
        url = f"http://{HOST}:{PORT}/admin/console.html"
        log_action(f"관리자 패널 열기: {url}")
        webbrowser.open(url)
        log_success("관리자 패널을 브라우저에서 열었습니다")
    except Exception as e:
        log_error(f"관리자 패널 열기 실패: {type(e).__name__}: {str(e)}")

def open_home(icon=None, item=None):
    """홈페이지 열기"""
    try:
        url = f"http://{HOST}:{PORT}/"
        log_action(f"대시보드 열기: {url}")
        webbrowser.open(url)
        log_success("대시보드를 브라우저에서 열었습니다")
    except Exception as e:
        log_error(f"대시보드 열기 실패: {type(e).__name__}: {str(e)}")

def toggle_console_menu(icon=None, item=None):
    """트레이 메뉴에서 콘솔 토글 (스레드 안전)"""
    # 백그라운드 스레드에서 실행되므로 별도 스레드로 처리
    log_action("콘솔 표시 중...")
    
    def do_toggle():
        hwnd = get_console_hwnd()
        if hwnd:
            # 콘솔이 있으면 콘솔 토글
            toggle_console()
        else:
            # 콘솔이 없으면 새로운 콘솔 창 열기
            try:
                import subprocess
                # 현재 Python 실행 파일과 앱을 새 콘솔에서 실행
                script_path = Path(__file__).resolve()
                subprocess.Popen(
                    [sys.executable, str(script_path)],
                    creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
                )
                log_info("새 콘솔 창에서 앱이 실행되었습니다")
            except Exception as e:
                log_error(f"새 콘솔 창 열기 실패: {e}")
    
    threading.Thread(target=do_toggle, daemon=True).start()

def exit_app(icon=None, item=None):
    """앱 종료"""
    global _running, _app
    log_action("News System 종료 중...")
    _running = False
    
    # 트레이 아이콘 정지
    if icon:
        try:
            icon.stop()
            log_info("트레이 아이콘 정지 완료")
        except Exception as e:
            log_warning(f"트레이 아이콘 정지 오류: {type(e).__name__}: {str(e)}")
    
    # 0.5초 대기 후 프로세스 즉시 종료
    time.sleep(0.5)
    log_success("News System이 종료되었습니다")
    os._exit(0)

def setup_tray():
    """시스템 트레이 설정"""
    try:
        import pystray
        log_info("pystray 라이브러리 로드 완료")
        
        icon_image = create_tray_icon()
        if icon_image is None:
            log_error("트레이 아이콘 생성 실패")
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
        
        log_success("트레이 아이콘 세팅 완료")
        return icon
    except ImportError as e:
        log_error(f"pystray 라이브러리 미설치: {str(e)}")
        log_warning("Windows Tray 기능을 사용하려면: pip install pystray")
        return None
    except Exception as e:
        log_error(f"트레이 설정 실패: {type(e).__name__}: {str(e)}")
        return None

def main():
    global _app, _server_thread, _running, _console_visible
    
    print("\n" + "="*60)
    log_info(f"News System v{APP_VERSION} 시작")
    log_info(f"플랫폼: {sys.platform}, Python: {sys.version.split()[0]}")
    print("="*60 + "\n")
    
    # 시작 시 콘솔 창 실제로 숨김
    if sys.platform == 'win32':
        hide_console()
    
    # 포트 확인
    log_info(f"포트 확인 중... ({HOST}:{PORT})")
    if port_in_use(PORT):
        # 포트가 이미 사용 중이면 기존 앱 연결 시도
        log_warning(f"포트 {PORT}이 이미 사용 중입니다. 기존 프로세스 확인 중...")
        try:
            response = requests.get(f"http://{HOST}:{PORT}", timeout=2)
            if response.status_code < 500:  # 정상 응답이면 기존 앱 실행 중
                log_success("기존 프로세스가 실행 중입니다!")
                log_action("브라우저에서 기존 앱에 연결 중...")
                webbrowser.open(f"http://{HOST}:{PORT}/")
                time.sleep(1)  # 브라우저 열릴 시간 제공
                log_info("1초 후 현재 프로세스를 종료합니다. 기존 앱으로 전환됩니다.")
                time.sleep(1)
                return
        except requests.exceptions.Timeout:
            log_warning("기존 프로세스가 응답하지 않습니다. (타임아웃)")
        except requests.exceptions.ConnectionError:
            log_warning("기존 프로세스에 연결할 수 없습니다. (연결 거부)")
        except Exception as e:
            log_warning(f"기존 프로세스 확인 실패: {type(e).__name__}: {str(e)}")
        
        # 응답 없으면 좀비 프로세스 - 잠시 대기 후 진행
        log_warning("포트 해제 대기 중... (최대 30초)")
        for i in range(30):
            if not port_in_use(PORT):
                log_success(f"포트가 해제되었습니다! ({i}초 대기)")
                break
            if i % 5 == 0 and i > 0:
                log_info(f"계속 대기 중... ({i}초 경과)")
            time.sleep(1)
        else:
            log_error(f"포트 {PORT}이 30초 이상 해제되지 않았습니다!")
            log_error("기존 프로세스를 수동으로 종료하고 다시 시도하세요.")
            log_error("프로세스를 종료합니다.")
            return

    # Flask 앱 생성
    try:
        log_action("Flask 앱 생성 중...")
        _app = create_app()
        log_success("Flask 앱 생성 완료")
    except Exception as e:
        log_error(f"Flask 앱 생성 실패: {type(e).__name__}: {str(e)}")
        return
    
    # 백그라운드 작업 시작
    try:
        log_action("백그라운드 작업 시작 중...")
        start_background_jobs(_app)
        log_success("백그라운드 작업 시작 완료")
    except Exception as e:
        log_error(f"백그라운드 작업 시작 실패: {type(e).__name__}: {str(e)}")
        return

    # Flask 서버 스레드 생성
    def run_server():
        global _running
        try:
            log_info(f"Flask 서버 시작... ({HOST}:{PORT})")
            _app.run(host=HOST, port=PORT, threaded=True, use_reloader=False)
        except Exception as e:
            log_error(f"Flask 서버 실행 오류: {type(e).__name__}: {str(e)}")
            _running = False
        finally:
            log_info("Flask 서버 종료됨")

    # 서버 스레드를 데몬 스레드로 (메인 프로세스 종료 시 자동 종료)
    try:
        _server_thread = threading.Thread(target=run_server, daemon=True, name="FlaskServer")
        _server_thread.start()
        log_success("서버 스레드 시작 완료")
    except Exception as e:
        log_error(f"서버 스레드 시작 실패: {type(e).__name__}: {str(e)}")
        return
    
    # 서버 준비 대기 (1초)
    log_info("서버 준비 중... (1초 대기)")
    time.sleep(1.0)
    
    # 브라우저 열기
    try:
        url = f"http://{HOST}:{PORT}/"
        log_action(f"기본 대시보드 열기: {url}")
        webbrowser.open(url)
        log_success("브라우저에서 대시보드가 열렸습니다")
    except Exception as e:
        log_warning(f"브라우저 열기 실패: {type(e).__name__}: {str(e)}")
        log_warning(f"수동으로 http://{HOST}:{PORT}에 접속하세요.")

    # Windows 환경이면 트레이 아이콘 설정
    if sys.platform == 'win32':
        log_info("Windows 환경 감지. 트레이 아이콘 설정 중...")
        tray_icon = setup_tray()
        if tray_icon:
            log_success("시스템 트레이에 News_System이 추가되었습니다!")
            log_info("💡 팁:")
            log_info("  - 🏠 대시보드: 메인 대시보드 열기")
            log_info("  - 🎛️ 관리 패널: 관리자 설정 페이지 열기")
            log_info("  - 👁️ 로그 숨기기/보기: 콘솔 창 토글")
            log_info("  - ❌ 끝내기: News System 종료")
            try:
                # 트레이 실행 (블로킹)
                log_info("트레이 아이콘 실행 대기 중...")
                tray_icon.run()
            except KeyboardInterrupt:
                log_warning("사용자 중단 감지!")
                exit_app(tray_icon)
            except Exception as e:
                log_error(f"트레이 실행 오류: {type(e).__name__}: {str(e)}")
                exit_app(tray_icon)
        else:
            # 트레이 실패하면 콘솔에서 대기
            log_error("트레이 아이콘 설정 실패!")
            log_warning("콘솔 창에서 실행 중입니다. Ctrl+C로 종료하세요.")
            try:
                while _running:
                    time.sleep(1)
            except KeyboardInterrupt:
                log_warning("사용자 중단 감지!")
                exit_app()
            except Exception as e:
                log_error(f"콘솔 대기 중 오류: {type(e).__name__}: {str(e)}")
    else:
        # Linux/Mac: 트레이 없이 그냥 실행
        log_info(f"플랫폼: {sys.platform} (트레이 미지원)")
        log_info("Ctrl+C로 News System을 종료하세요.")
        try:
            while _running:
                time.sleep(1)
        except KeyboardInterrupt:
            log_warning("사용자 중단 감지!")
            exit_app()
        except Exception as e:
            log_error(f"메인 루프 오류: {type(e).__name__}: {str(e)}")
            

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log_error(f"예상치 못한 오류: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        time.sleep(3)
        os._exit(1)
