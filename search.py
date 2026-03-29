"""
search.py
- 파일 및 앱 검색 로직을 담당하는 모듈
- 시작 메뉴, 바탕화면, Program Files, 사용자 폴더 등을 검색
"""

import os
import glob
from pathlib import Path
from typing import List, Dict

# 검색 결과 최대 개수
MAX_RESULTS = 30


def get_search_paths() -> List[str]:
    """검색 대상 경로 목록을 반환한다."""
    paths = []
    user_profile = os.environ.get("USERPROFILE", "C:\\Users\\Default")
    appdata = os.environ.get("APPDATA", "")
    programdata = os.environ.get("PROGRAMDATA", "C:\\ProgramData")

    candidates = [
        # 시작 메뉴 (사용자)
        os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs"),
        # 시작 메뉴 (전체)
        os.path.join(programdata, "Microsoft", "Windows", "Start Menu", "Programs"),
        # 바탕화면 (사용자)
        os.path.join(user_profile, "Desktop"),
        # 바탕화면 (공용)
        os.path.join("C:\\Users", "Public", "Desktop"),
        # Program Files
        "C:\\Program Files",
        "C:\\Program Files (x86)",
        # 사용자 폴더 내 주요 위치
        os.path.join(user_profile, "Documents"),
        os.path.join(user_profile, "Downloads"),
        os.path.join(user_profile, "Pictures"),
        os.path.join(user_profile, "Music"),
        os.path.join(user_profile, "Videos"),
    ]

    for p in candidates:
        if p and os.path.isdir(p):
            paths.append(p)

    return paths


def search_files(keyword: str) -> List[Dict]:
    """
    키워드로 파일/앱/폴더를 검색하여 결과 리스트를 반환한다.
    각 항목은 {'name': str, 'path': str, 'type': str} 형태.
    type: 'app' | 'file' | 'folder'
    """
    if not keyword or len(keyword.strip()) == 0:
        return []

    keyword_lower = keyword.strip().lower()
    results: List[Dict] = []
    seen_paths = set()

    search_paths = get_search_paths()

    # 검색 확장자 우선순위: .lnk, .exe 먼저, 나머지는 일반 파일
    priority_exts = {".lnk", ".exe"}
    PATH_DEPTH_MAP = {
    "C:\\Program Files":       1,
    "C:\\Program Files (x86)": 1,
}

    for base_path in search_paths:
        try:
            depth = PATH_DEPTH_MAP.get(base_path, 4)  # 기본은 4, Program Files는 1
            _walk_and_collect(
                base_path, keyword_lower, results, seen_paths, priority_exts,
                max_depth=depth   # ← 여기에 depth 전달
            )
        except (PermissionError, OSError):
            continue

    # 우선순위 정렬: 앱(exe/lnk) → 파일 → 폴더, 이름 기준 알파벳순
    def sort_key(item):
        order = {"app": 0, "file": 1, "folder": 2}
        return (order.get(item["type"], 3), item["name"].lower())

    results.sort(key=sort_key)
    return results[:MAX_RESULTS]


def _walk_and_collect(
    base_path: str,
    keyword_lower: str,
    results: list,
    seen_paths: set,
    priority_exts: set,
    max_depth: int = 4,
    current_depth: int = 0,
):
    """재귀적으로 디렉터리를 탐색하며 일치하는 항목을 수집한다."""
    if current_depth > max_depth:
        return
    if len(results) >= MAX_RESULTS:
        return

    try:
        entries = list(os.scandir(base_path))
    except (PermissionError, OSError):
        return

    for entry in entries:
        if len(results) >= MAX_RESULTS:
            break

        try:
            name = entry.name
            path = entry.path

            if path in seen_paths:
                continue

            # 숨김 파일/폴더 제외 (이름이 .으로 시작하는 경우)
            if name.startswith("."):
                continue

            name_lower = name.lower()

            if entry.is_dir(follow_symlinks=False):
                # 폴더 자체가 키워드와 일치하면 추가
                if keyword_lower in name_lower:
                    seen_paths.add(path)
                    results.append(
                        {
                            "name": name,
                            "path": path,
                            "type": "folder",
                        }
                    )
                # 하위 폴더 재귀 탐색
                _walk_and_collect(
                    path,
                    keyword_lower,
                    results,
                    seen_paths,
                    priority_exts,
                    max_depth,
                    current_depth + 1,
                )

            elif entry.is_file(follow_symlinks=True):
                stem, ext = os.path.splitext(name)
                ext_lower = ext.lower()

                # 키워드가 파일명(확장자 제외)에 포함되는지 확인
                if keyword_lower not in stem.lower():
                    continue

                seen_paths.add(path)

                if ext_lower in priority_exts:
                    results.append(
                        {
                            "name": stem,  # 확장자 제외한 이름
                            "path": path,
                            "type": "app",
                        }
                    )
                else:
                    results.append(
                        {
                            "name": name,
                            "path": path,
                            "type": "file",
                        }
                    )

        except (PermissionError, OSError):
            continue
