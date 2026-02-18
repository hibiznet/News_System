News_System
- Flask 기반의 뉴스/방송 오버레이 통합 시스템입니다.
- RSS 뉴스, 주식 데이터, 방송 API, 시스템 메트릭 등을 수집하여 JSON 기반 Overlay UI 및 Admin 패널에 제공합니다.

1. 개요
# News_System은 다음을 목표로 합니다:

- 실시간 뉴스 수집 및 가공
- 주식/지수 데이터 자동 갱신
- 방송용 Overlay 데이터 관리
- Admin UI를 통한 텍스트/레이아웃 제어
- 시스템 리소스 모니터링 API 제공
- 서버는 Flask 기반이며, 데이터는 JSON 파일 형태로 관리됩니다.

2. 기술 스택
| 구분             | 기술                 |
| -------------- | --------------------- |
| Backend        | Python, Flask         |
| Data Parsing   | feedparser            |
| Stock API      | yfinance              |
| System Metrics | psutil                |
| Frontend       | HTML, CSS, JavaScript |
| 데이터 저장         | JSON 파일 기반      |

3. 디렉토리 구조
News_System/
│
├── app.py                  # Flask 메인 서버
├── rss_to_news.py          # RSS → news.json 변환 스크립트
├── requirements.txt        # Python 의존성
├── test.py                 # 테스트 스크립트
│
├── admin/                  # 관리자 UI
├── overlay/                # 방송 오버레이 정적 페이지 및 JSON
├── shared/                 # 공통 코드
└── .vscode/

4. 주요 기능
4.1 RSS 뉴스 자동 수집
# 연합뉴스 RSS:
- https://www.yna.co.kr/rss/news.xml

- feedparser 사용
- 불필요 키워드 제거 후 news.json 생성
- 주기적 자동 갱신 (기본 5분)

4.2 주식 데이터 수집
- yfinance 기반
- 주요 지수/종목 데이터 자동 갱신
- JSON 파일로 저장

4.3 방송 데이터 연동
- SOOP API 기반 TOP 방송 데이터
- 신인 스트리머 데이터 수집
- JSON 변환 후 Overlay 제공

※ API 키는 환경변수로 관리 필요
4.4 Overlay 제어 API
| 엔드포인트           | 설명            |
| --------------- | ------------- |
| `/api/breaking` | 속보 텍스트 저장     |
| `/api/banner`   | 배너 텍스트 저장     |
| `/api/theme`    | 스타일 테마 설정     |
| `/api/layout`   | 4분할 레이아웃 설정   |
| `/api/live`     | 라이브 상태/텍스트 설정 |
| `/api/metrics`  | 시스템 리소스 정보    |

4.5 시스템 모니터링
- CPU
- Memory
- Disk
- Network
- psutil 기반으로 JSON 반환

5. 실행 방법
5.1 Python 설치
- Python 3.9+ 권장
# 현재 python 3.12버전으로 개발되어 있음. 버전이 다르면 오류남.

5.2 의존성 설치
- pip install -r requirements.txt

5.3 환경 변수 설정 (예시)
- export SOOP_CLIENT_ID=your_client_id
- export SOOP_CLIENT_SECRET=your_secret

Windows:
- set SOOP_CLIENT_ID=your_client_id
- set SOOP_CLIENT_SECRET=your_secret

5.4 서버 실행
- python app.py

기본 접속:
- http://localhost:5000/

Admin:
- http://localhost:5000/admin/

6. 아키텍처 개요
[ External Sources ]
   ├── RSS (뉴스)
   ├── Stock API (yfinance)
   ├── SOOP API
   └── Indeed RSS

        ↓ (주기적 갱신)

[ Background Threads ]
        ↓
[ JSON Storage (overlay/*.json) ]
        ↓
[ Flask API ]
        ↓
[ Overlay UI / Admin UI ]

7. 자동 갱신 구조
- 별도 스레드에서 5분 주기 갱신
- 예외 발생 시 로그 출력
- JSON 파일 overwrite 방식

8. 개선 권장 사항
8.1 설정 분리
- 환경설정을 .env 또는 config.yaml로 분리

8.2 로깅 체계 개선
- logging 모듈 도입
- 파일 로깅 지원
- 
8.3 데이터 저장 구조 개선
- JSON 파일 → SQLite/PostgreSQL 전환 고려

8.4 모듈화
- RSS, Stock, SOOP, Metrics 로직을 서비스 모듈로 분리

8.5 Docker 지원
- Dockerfile 작성
- docker-compose 구성

9. 향후 확장 아이디어
- WebSocket 기반 실시간 푸시
- AI 뉴스 요약 기능 추가
- 방송용 자동 자막 생성
- 관리자 인증 시스템 도입
- 다중 채널 Overlay 지원

10. 라이선스

## Installer 사용법 (아래 설치로 exe 파일 생성) ## 
- py -3.12 -m PyInstaller --noconfirm --clean --name News_System --onedir --add-data "overlay;overlay" --add-data "admin;admin" --add-data "shared;shared" --add-data "backgrounds;backgrounds" app_main.py
- py -3.12 -m PyInstaller --noconfirm --clean --windowed --name News_System --onedir --add-data "overlay;overlay" --add-data "admin;admin" --add-data "shared;shared" --add-data "backgrounds;backgrounds" app_main.py
