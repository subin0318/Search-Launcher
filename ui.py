"""
ui.py
- PyQt5 기반 검색 런처 UI
- 검색창, 결과 리스트, 상태 표시줄로 구성
- 아이콘은 Windows Shell 아이콘 추출 시도 후 기본 아이콘으로 폴백
"""

from typing import List, Dict
import time
import keyword

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QApplication,
    QFrame,
    QMessageBox,
)
from PyQt5.QtCore import (
    Qt,
    QThread,
    pyqtSignal,
    QTimer,
    QSize,
    QEvent,
)
from PyQt5.QtGui import (
    QIcon,
    QFont,
    QPixmap,
    QKeyEvent,
)

from search import search_files
from launcher import launch_item


# ── 아이콘 추출 (Windows 전용, 실패 시 None 반환) ──────────────────────────
def _get_file_icon(path: str) -> QIcon | None:
    try:
        from PyQt5.QtWinExtras import QWinThumbnailToolBar  # noqa - 존재 확인용
    except ImportError:
        pass

    try:
        from PyQt5.QtWidgets import QFileIconProvider
        from PyQt5.QtCore import QFileInfo
        provider = QFileIconProvider()
        icon = provider.icon(QFileInfo(path))
        if icon and not icon.isNull():
            return icon
    except Exception:
        pass
    return None


def _make_fallback_icon(item_type: str) -> QIcon:
    """타입별 기본 이모지/텍스트 아이콘을 픽스맵으로 생성한다."""
    from PyQt5.QtGui import QPainter, QPixmap, QColor, QFont
    emoji = {"app": "⚙", "file": "📄", "folder": "📁"}.get(item_type, "📄")
    px = QPixmap(32, 32)
    px.fill(QColor(0, 0, 0, 0))
    painter = QPainter(px)
    font = QFont()
    font.setPixelSize(22)
    painter.setFont(font)
    painter.drawText(px.rect(), Qt.AlignCenter, emoji)
    painter.end()
    return QIcon(px)


# ── 백그라운드 검색 스레드 ─────────────────────────────────────────────────
class SearchWorker(QThread):
    results_ready = pyqtSignal(list, int)  # List[Dict], token

    def __init__(self, keyword: str, token: int):
        super().__init__()
        self._last_launch_path = ""
        self._last_launch_time = 0
        self._launch_cooldown_ms = 3000
        self.keyword = keyword
        self.token = token

    def run(self):
        results = search_files(self.keyword)
        self.results_ready.emit(results, self.token)


# ── 커스텀 리스트 아이템 위젯 ─────────────────────────────────────────────
class ResultItemWidget(QWidget):
    """이름 + 경로를 2행으로 표시하는 커스텀 위젯."""

    def __init__(self, name: str, path: str, item_type: str, parent=None):
        super().__init__(parent)
        self.item_type = item_type

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(10)

        # 아이콘
        icon_label = QLabel()
        icon_label.setFixedSize(32, 32)
        icon = _get_file_icon(path)
        if icon is None:
            icon = _make_fallback_icon(item_type)
        pixmap = icon.pixmap(QSize(28, 28))
        icon_label.setPixmap(pixmap)
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)

        # 텍스트 영역
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(1)

        name_label = QLabel(name)
        name_label.setFont(QFont("Segoe UI", 10, QFont.Medium))
        name_label.setStyleSheet("color: #E8E8E8;")

        path_label = QLabel(path)
        path_label.setToolTip(path)
        path_label.setFont(QFont("Segoe UI", 8))
        path_label.setStyleSheet("color: #7A7A8C;")
        path_label.setWordWrap(False)

        text_layout.addWidget(name_label)
        text_layout.addWidget(path_label)
        layout.addLayout(text_layout)
        layout.addStretch()

        # 타입 뱃지
        type_colors = {
            "app":    ("#3D6FBF", "#82AAFF"),
            "file":   ("#2D5A3D", "#69D08A"),
            "folder": ("#5A3D2D", "#D09A69"),
        }
        bg, fg = type_colors.get(item_type, ("#3A3A4A", "#AAAACC"))
        type_label = QLabel(item_type.upper())
        type_label.setFont(QFont("Segoe UI", 7, QFont.Bold))
        type_label.setStyleSheet(
            f"color: {fg}; background: {bg};"
            f"border-radius: 4px; padding: 1px 6px;"
        )
        type_label.setFixedHeight(18)
        layout.addWidget(type_label)


# ── 메인 런처 윈도우 ──────────────────────────────────────────────────────
class LauncherWindow(QWidget):
    def __init__(self):
        super().__init__()
        self._worker: SearchWorker | None = None
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._start_search)
        self._current_items: List[Dict] = []

        self._is_confirming_exit = False
        self._is_launching = False
        self._search_token = 0
        self._quit_callback = None          # ← 추가: 콜백 초기화

        self._setup_window()
        self._setup_ui()
        self._apply_style()

    def set_quit_callback(self, fn):        # ← 추가: 콜백 주입 메서드
        self._quit_callback = fn


# ── 윈도우 설정 ──────────────────────────────────────────────────────
    def _setup_window(self):
        self.setWindowTitle("Search Launcher")
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumWidth(680)
        self.setMinimumHeight(80)

        self._move_to_active_screen()   # ← 초기 위치 설정

    def _move_to_active_screen(self):
        """마우스 커서가 있는 모니터 중앙 상단에 창을 배치한다."""
        from PyQt5.QtGui import QCursor

        cursor_pos = QCursor.pos()
        screen = QApplication.screenAt(cursor_pos) or QApplication.primaryScreen()
        geometry = screen.geometry()

        w = 680
        x = geometry.x() + (geometry.width() - w) // 2
        y = geometry.y() + int(geometry.height() * 0.22)
        self.setGeometry(x, y, w, 80)

    def closeEvent(self, event):
        event.accept()

        if self._debounce_timer.isActive():
            self._debounce_timer.stop()

        if self._worker is not None:
            try:
                if self._worker.isRunning():
                    self._worker.quit()
                    self._worker.wait(1000)
            except Exception:
                pass
            self._worker = None

        if self._quit_callback:
            self._quit_callback()

    # ── UI 구성 ──────────────────────────────────────────────────────────
    def _setup_ui(self):
        self._container = QFrame(self)
        self._container.setObjectName("container")
        self._container.setGeometry(0, 0, self.width(), self.height())

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._container)

        inner = QVBoxLayout(self._container)
        inner.setContentsMargins(16, 14, 16, 14)
        inner.setSpacing(10)

        # ── 검색창 행 ──────────────────────────────────────────────
        search_row = QHBoxLayout()
        search_row.setSpacing(10)

        search_icon = QLabel("🔍")
        search_icon.setFont(QFont("Segoe UI Emoji", 14))
        search_icon.setFixedWidth(28)
        search_row.addWidget(search_icon)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("앱, 파일, 폴더 검색...")
        self.search_input.setObjectName("searchInput")
        self.search_input.setFont(QFont("Segoe UI", 13))
        self.search_input.setFrame(False)
        self.search_input.textChanged.connect(self._on_text_changed)
        self.search_input.installEventFilter(self)
        search_row.addWidget(self.search_input)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setFont(QFont("Segoe UI", 8))
        self.status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.status_label.setFixedWidth(80)
        search_row.addWidget(self.status_label)

        inner.addLayout(search_row)

        # ── 구분선 ──────────────────────────────────────────────────
        self._divider = QFrame()
        self._divider.setFrameShape(QFrame.HLine)
        self._divider.setObjectName("divider")
        self._divider.hide()
        inner.addWidget(self._divider)

        # ── 결과 리스트 ─────────────────────────────────────────────
        self.result_list = QListWidget()
        self.result_list.setObjectName("resultList")
        self.result_list.setFont(QFont("Segoe UI", 10))
        self.result_list.setFrameShape(QFrame.NoFrame)
        self.result_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.result_list.setSpacing(1)
        self.result_list.hide()
        self.result_list.itemActivated.connect(self._on_item_activated)
        inner.addWidget(self.result_list)

        # ── 안내 라벨 ───────────────────────────────────────────────
        self.empty_label = QLabel("검색 결과 없음")
        self.empty_label.setObjectName("emptyLabel")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setFont(QFont("Segoe UI", 10))
        self.empty_label.hide()
        inner.addWidget(self.empty_label)

    # ── 스타일시트 ────────────────────────────────────────────────────────
    def _apply_style(self):
        self.setStyleSheet("""
            QWidget {
                background: transparent;
            }
            #container {
                background: rgba(22, 22, 30, 0.97);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 16px;
            }
            #searchInput {
                background: transparent;
                color: #F0F0F5;
                selection-background-color: #3A6FBF;
                border: none;
                padding: 0px;
            }
            #searchInput::placeholder {
                color: #55556A;
            }
            #statusLabel {
                color: #55556A;
            }
            #divider {
                color: rgba(255,255,255,0.07);
                background: rgba(255,255,255,0.07);
                border: none;
                max-height: 1px;
                min-height: 1px;
            }
            #resultList {
                background: transparent;
                color: #E0E0EA;
                outline: none;
                border: none;
            }
            #resultList::item {
                border-radius: 8px;
                padding: 0px;
            }
            #resultList::item:selected {
                background: rgba(60, 110, 200, 0.35);
            }
            #resultList::item:hover {
                background: rgba(255,255,255,0.05);
            }
            #emptyLabel {
                color: #55556A;
                padding: 12px 0px;
            }
        """)

    # ── 이벤트 필터 (키보드 네비게이션) ──────────────────────────────────
    def eventFilter(self, obj, event):
        if obj is self.search_input and isinstance(event, QKeyEvent) and event.type() == QEvent.KeyPress:
            key = event.key()
            if key == Qt.Key_Down:
                self._move_selection(1)
                return True
            elif key == Qt.Key_Up:
                self._move_selection(-1)
                return True
            elif key == Qt.Key_Return or key == Qt.Key_Enter:
                self._launch_selected()
                return True
            elif key == Qt.Key_Escape:
                self._confirm_exit()
                return True
        return super().eventFilter(obj, event)

    def _move_selection(self, delta: int):
        count = self.result_list.count()
        if count == 0:
            return
        current = self.result_list.currentRow()
        new_row = max(0, min(count - 1, current + delta))
        self.result_list.setCurrentRow(new_row)

    def _set_launch_lock(self, locked: bool):
        self._is_launching = locked

        if locked:
            self.status_label.setText("실행 중...")
        else:
            if self._current_items:
                self.status_label.setText(f"{len(self._current_items)}개 결과")
            else:
                self.status_label.setText("")

    def _launch_current_row(self, row: int):
        if 0 <= row < len(self._current_items):
            self._set_launch_lock(True)
            try:
                launch_item(self._current_items[row])
            except Exception:
                self._set_launch_lock(False)
                self.status_label.setText("실행 실패")
                return

            QTimer.singleShot(500, lambda: self._set_launch_lock(False))

    def _launch_selected(self):
        self._launch_current_row(self.result_list.currentRow())

    def _on_item_activated(self, list_item: QListWidgetItem):
        row = self.result_list.row(list_item)
        self._launch_current_row(row)

    # ── 검색 로직 ─────────────────────────────────────────────────────────
    def _on_text_changed(self, text: str):
        self._debounce_timer.start(200)
        if not text.strip():
            self._show_empty_state()

    def _start_search(self):
        keyword = self.search_input.text().strip()
        if not keyword:
            self._show_empty_state()
            return

        # ← 새 검색 전에 이전 워커 정리
        if self._worker is not None and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(500)

        self.status_label.setText("검색 중...")
        self._search_token += 1
        token = self._search_token

        self._worker = SearchWorker(keyword, token)
        self._worker.results_ready.connect(self._on_results_ready)
        self._worker.start()

    def _on_results_ready(self, results: List[Dict], token: int):
        if token != self._search_token:
            return

        self._current_items = results
        self.result_list.clear()

        if not results:
            self._show_no_results()
            return

        self._divider.show()
        self.empty_label.hide()
        self.result_list.show()

        for item in results:
            list_item = QListWidgetItem(self.result_list)
            widget = ResultItemWidget(
                name=item["name"],
                path=item["path"],
                item_type=item["type"],
            )
            list_item.setSizeHint(widget.sizeHint())
            self.result_list.setItemWidget(list_item, widget)

        if self.result_list.count() > 0:
            self.result_list.setCurrentRow(0)

        count = len(results)
        self.status_label.setText(f"{count}개 결과")
        self._resize_to_content()

    def _show_empty_state(self):
        self._current_items = []
        self.result_list.clear()
        self.result_list.hide()
        self.empty_label.hide()
        self._divider.hide()
        self.status_label.setText("")
        self._resize_to_content()

    def _show_no_results(self):
        self.result_list.hide()
        self._divider.show()
        self.empty_label.show()
        self.status_label.setText("0개 결과")
        self._resize_to_content()

    def _resize_to_content(self):
        """결과 개수에 맞게 윈도우 높이를 동적으로 조정한다."""
        base_height = 70
        count = self.result_list.count()

        if self.result_list.isVisible() and count > 0:
            item_height = 56
            max_visible = 8
            visible = min(count, max_visible)
            list_height = visible * item_height + 12
            total = base_height + 16 + list_height
        elif self.empty_label.isVisible():
            total = base_height + 16 + 46
        else:
            total = base_height

        self._container.setFixedHeight(total)
        self.setFixedHeight(total)

    def _confirm_exit(self):
        if self._is_confirming_exit:
            return

        self._is_confirming_exit = True

        msg = QMessageBox(self)
        msg.setWindowTitle("종료 확인")
        msg.setText("Search Launcher를 종료하시겠습니까?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #FFFFFF;
            }
            QMessageBox QLabel {
                color: #222222;
                font-size: 11pt;
                font-family: 'Segoe UI';
            }
            QPushButton {
                background-color: #F3F3F3;
                color: #222222;
                border: 1px solid #D0D0D0;
                border-radius: 6px;
                padding: 5px 20px;
                font-family: 'Segoe UI';
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #E8E8E8;
                border: 1px solid #BEBEBE;
            }
            QPushButton:pressed {
                background-color: #DCDCDC;
            }
        """)

        result = msg.exec_()
        self._is_confirming_exit = False

        if result == QMessageBox.Yes:
            self.close()

    # ── 윈도우 드래그 ─────────────────────────────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and hasattr(self, "_drag_pos"):
            self.move(event.globalPos() - self._drag_pos)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._container.setGeometry(0, 0, self.width(), self.height())

    def keyPressEvent(self, event):
        super().keyPressEvent(event)