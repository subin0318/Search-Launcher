# Search Launcher — 실행 방법

## 필수 설치 명령어

```bash
pip install PyQt5
```

> PyQt5 하나만 설치하면 됩니다.
> Python 3.9 이상, Windows 환경에서 실행하세요.

---

## 파일 구조

```
search_launcher/
├── main.py               ← 실행 진입점
├── ui.py                 ← PyQt5 UI (검색창, 결과 리스트)
├── search.py             ← 파일/앱 검색 로직
├── launcher.py           ← 항목 실행 로직
└── single_instance.py    ← 단일 인스턴스 제어
```

---

## 실행 방법

```bash
python main.py
```

---

## 사용 방법

| 동작 | 설명 |
|------|------|
| 타이핑 | 검색어 입력 → 실시간 검색 |
| ↑ / ↓ 방향키 | 결과 리스트 이동 |
| Enter | 선택 항목 실행 |
| 더블클릭 | 항목 실행 |
| Esc | 프로그램 종료 |
| 창 드래그 | 원하는 위치로 이동 |

---

## 검색 대상 경로

- 시작 메뉴 바로가기 (`%APPDATA%\Microsoft\Windows\Start Menu\Programs`)
- 공용 시작 메뉴 (`%ProgramData%\Microsoft\Windows\Start Menu\Programs`)
- 바탕화면 (사용자 / 공용)
- `C:\Program Files`
- `C:\Program Files (x86)`
- 사용자 폴더: Documents, Downloads, Pictures, Music, Videos

---

## 실행 규칙

| 타입 | 동작 |
|------|------|
| `.exe` | 직접 실행 |
| `.lnk` | Windows 바로가기 실행 |
| 일반 파일 | 기본 연결 프로그램으로 열기 |
| 폴더 | 파일 탐색기로 열기 |
