"""
single_instance.py
- 나중에 실행된 인스턴스가 우선순위를 가짐
- 기존 인스턴스에 종료 신호를 보내고 새 인스턴스가 실행됨
"""

import sys
import socket
import threading

_LOCK_PORT = 47391
_server_socket = None
_quit_callback = None


def set_quit_callback(fn):
    """기존 인스턴스가 종료 신호를 받았을 때 호출할 함수 등록."""
    global _quit_callback
    _quit_callback = fn


def _listen_for_quit():
    """새 인스턴스가 보내는 종료 신호를 대기."""
    global _server_socket
    while _server_socket:
        try:
            conn, _ = _server_socket.accept()
            conn.recv(16)
            conn.close()
            if _quit_callback:
                _quit_callback()  # 기존 인스턴스 종료
        except Exception:
            break


def _try_socket_lock() -> bool:
    """포트 바인딩 성공 시 첫 번째 인스턴스."""
    global _server_socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", _LOCK_PORT))
        sock.listen(5)
        _server_socket = sock
        t = threading.Thread(target=_listen_for_quit, daemon=True)
        t.start()
        return True
    except OSError:
        return False


def _send_quit_signal():
    """기존 인스턴스에 종료 신호 전송."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect(("127.0.0.1", _LOCK_PORT))
        sock.send(b"QUIT")
        sock.close()
    except Exception:
        pass


def ensure_single_instance() -> bool:
    """
    포트 바인딩 실패 시 기존 인스턴스에 종료 신호를 보내고
    잠시 대기 후 포트를 다시 점유한다.

    Returns:
        True  → 새 인스턴스로 정상 실행
        False → 포트 재점유 실패 (드문 경우)
    """
    if _try_socket_lock():
        return True  # 첫 번째 실행

    # 기존 인스턴스 종료 요청
    _send_quit_signal()

    # 기존 인스턴스가 포트를 해제할 때까지 재시도
    import time
    for _ in range(20):       # 최대 2초 대기
        time.sleep(0.1)
        if _try_socket_lock():
            return True

    return False  # 재점유 실패


def release():
    """앱 종료 시 소켓 잠금 해제."""
    global _server_socket
    if _server_socket:
        try:
            _server_socket.close()
        except Exception:
            pass
        _server_socket = None