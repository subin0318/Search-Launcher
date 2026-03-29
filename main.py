"""
main.py
- 검색 런처 진입점
- PyQt5 앱 초기화 및 LauncherWindow 표시
"""

import sys

try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QObject, pyqtSignal
from PyQt5.QtGui import QFont
import keyboard

from ui import LauncherWindow
from single_instance import ensure_single_instance, set_quit_callback, release


class HotkeyBridge(QObject):
    toggle_requested = pyqtSignal()
    quit_requested = pyqtSignal()


def main():
    if not ensure_single_instance():
        sys.exit(0)

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("Search Launcher")
    app.setQuitOnLastWindowClosed(False)

    font = QFont("Segoe UI", 10)
    app.setFont(font)

    window = LauncherWindow()
    window.show()
    window.search_input.setFocus()

    bridge = HotkeyBridge()
    is_quitting = False
    hotkey_handles = []

    def show_window():
        window._move_to_active_screen() 
        if window.isMinimized():
            window.showNormal()
        else:
            window.show()

        window.raise_()
        window.activateWindow()
        window.search_input.setFocus()
        window.search_input.clear()

    def hide_window():
        window.hide()

    def toggle_window():
        if window.isVisible():
            hide_window()
        else:
            show_window()

    def cleanup():
        # hotkey 개별 해제
        for handle in hotkey_handles:
            try:
                keyboard.remove_hotkey(handle)
            except Exception:
                pass
        hotkey_handles.clear()

        # 남은 후킹 정리
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass

        try:
            keyboard.unhook_all()
        except Exception:
            pass

        try:
            release()
        except Exception:
            pass

    def quit_app():
        nonlocal is_quitting
        if is_quitting:
            return
        is_quitting = True

        cleanup()
        app.quit()
    
    window.set_quit_callback(quit_app)

    # Qt 메인 스레드에서만 UI 조작
    bridge.toggle_requested.connect(toggle_window)
    bridge.quit_requested.connect(quit_app)

    # 전역 핫키 콜백에서는 signal만 emit
    def hotkey_toggle_callback():
        bridge.toggle_requested.emit()

    # Alt+Space는 윈도우 시스템 메뉴와 충돌 가능성이 있어서
    # 불안정하면 ctrl+space 또는 ctrl+shift+space로 바꾸는 게 낫다.
    h1 = keyboard.add_hotkey("Ctrl+Shift+Space", hotkey_toggle_callback)
    hotkey_handles.append(h1)

    app.aboutToQuit.connect(cleanup)
    set_quit_callback(quit_app)

    ret = app.exec_()
    sys.exit(ret)


if __name__ == "__main__":
    main()