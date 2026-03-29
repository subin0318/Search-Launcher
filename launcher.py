"""
launcher.py
- 검색 결과 항목을 실행하는 모듈
- .exe → 직접 실행
- .lnk → 바로가기 실행
- 일반 파일 → 기본 연결 프로그램으로 열기
- 폴더 → 탐색기로 열기
"""

import os
import subprocess
import time
from typing import Dict

# 마지막 실행 기록 {path: 실행시각}
_last_launch_times: dict = {}
LAUNCH_COOLDOWN = 2.0  # 초 — 같은 항목을 이 시간 안에 중복 실행 방지


def launch_item(item: Dict) -> bool:
    path = item.get("path", "")
    item_type = item.get("type", "file")

    if not path:
        return False

    if not os.path.exists(path):
        print(f"[launcher] 경로가 존재하지 않음: {path}")
        return False

    # ── 쿨다운 체크 ──────────────────────────────────────
    now = time.monotonic()
    last = _last_launch_times.get(path, 0)
    if now - last < LAUNCH_COOLDOWN:
        print(f"[launcher] 쿨다운 중, 무시: {path}")
        return False
    _last_launch_times[path] = now
    # ─────────────────────────────────────────────────────

    try:
        if item_type == "folder":
            return _open_folder(path)
        else:
            return _open_file(path)
    except Exception as e:
        print(f"[launcher] 실행 오류: {e}")
        return False


def _open_folder(path: str) -> bool:
    try:
        os.startfile(path)
        return True
    except Exception as e:
        print(f"[launcher] 폴더 열기 실패: {e}")
        try:
            subprocess.Popen(["explorer", path])
            return True
        except Exception as e2:
            print(f"[launcher] explorer 실행 실패: {e2}")
            return False


def _open_file(path: str) -> bool:
    _, ext = os.path.splitext(path)
    ext_lower = ext.lower()

    try:
        if ext_lower == ".exe":
            work_dir = os.path.dirname(path)
            subprocess.Popen([path], cwd=work_dir)
        else:
            os.startfile(path)
        return True
    except Exception as e:
        print(f"[launcher] 파일 실행 실패 ({path}): {e}")
        return False