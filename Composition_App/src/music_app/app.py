"""Main application window — ties together the staff, audio engine, and editor."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QEvent, QPropertyAnimation, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QSizePolicy,
    QMainWindow, QVBoxLayout, QWidget, QLabel, QStatusBar, QScrollArea,
    QFileDialog, QHBoxLayout, QPushButton, QInputDialog, QMessageBox,
)

from .audio_engine import AudioEngine
from .commands import SequenceEditor
from .models import Sequence, PITCH_ORDER, KEY_SIGNATURES
from .server_client import ServerClient
from .staff_widget import StaffWidget
from . import dbUtil


class MainWindow(QMainWindow):
    """The primary application window."""

    _TONIC_TO_CHROMATIC: dict[str, int] = {
        "C": 0,
        "B#": 0,
        "C#": 1,
        "Db": 1,
        "D": 2,
        "D#": 3,
        "Eb": 3,
        "E": 4,
        "Fb": 4,
        "E#": 5,
        "F": 5,
        "F#": 6,
        "Gb": 6,
        "G": 7,
        "G#": 8,
        "Ab": 8,
        "A": 9,
        "A#": 10,
        "Bb": 10,
        "B": 11,
        "Cb": 11,
    }

    def __init__(self, data_dir: Path, example_path: Path | None = None) -> None:
        super().__init__()

        self.setWindowTitle("Music App — Treble Clef")
        self.setMinimumSize(900, 420)
        self.resize(1000, 520)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # ── Core objects ─────────────────────────────────────────
        self._audio = AudioEngine(data_dir, parent=self)

        if example_path and example_path.exists():
            self._sequence = Sequence.from_file(example_path)
        else:
            self._sequence = Sequence(name="Empty", bpm=120, notes=[])

        self._editor = SequenceEditor(self._sequence, parent=self)
        self._edit_cursors = [0, 0]
        self._active_edit_cursor_slot = 0
        self._active_cursor_focus = 0  # 0: edit cursor 1, 1: edit cursor 2, 2: playback cursor
        self._playback_cursor_index = 0
        self._playback_start_index = 0
        self._last_modified_cursor_kind = "playback"
        self._key_cycle_origin_key = self._sequence.key
        self._key_cycle_base_indices: list[int | None] = []
        self._applying_key_cycle = False
        self._project_root = data_dir.parent
        self._shutdown_complete = False

        # ── Widgets ──────────────────────────────────────────────
        self._staff = StaffWidget()
        self._staff.set_sequence(self._sequence)

        ts = f"{self._sequence.time_sig_num}/{self._sequence.time_sig_den}"
        key = self._sequence.key
        self._title_label = QLabel(
            f"  {self._sequence.name}  —  Key: {key}  —  {ts}  —  {self._sequence.bpm} BPM"
        )
        self._load_json_button = QPushButton("Upload")
        self._save_json_button = QPushButton("Download")
        self._upload_button = QPushButton("Load JSON")
        self._download_button = QPushButton("Save JSON")
        self._load_json_button.setFixedHeight(28)
        self._save_json_button.setFixedHeight(28)
        self._upload_button.setFixedHeight(28)
        self._download_button.setFixedHeight(28)
        self._load_json_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._save_json_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._upload_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._download_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._load_json_button.setAutoDefault(False)
        self._save_json_button.setAutoDefault(False)
        self._upload_button.setAutoDefault(False)
        self._download_button.setAutoDefault(False)
        self._load_json_button.setDefault(False)
        self._save_json_button.setDefault(False)
        self._upload_button.setDefault(False)
        self._download_button.setDefault(False)
        self._load_json_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_json_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._upload_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._download_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._load_json_button.clicked.connect(self._load_json_sequence)
        self._save_json_button.clicked.connect(self._save_json_sequence)
        self._upload_button.clicked.connect(self._upload_json_file)
        self._download_button.clicked.connect(self._download_json_file)

        # Per-lane sample bank selectors (left side)
        self._bank_combo_boxes: dict[int, QComboBox] = {}
        self._left_panel = QWidget()
        self._left_panel.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self._left_panel.setMinimumWidth(150)
        self._left_panel.setMaximumWidth(150)
        
        # Create instrument rows and position them to align with staff lines
        available_banks = self._audio.available_sample_banks()
        self._instrument_rows: dict[int, QWidget] = {}
        
        # Calculate staff positions (matching StaffWidget constants)
        STAFF_TOP_MARGIN = 30
        LINE_SPACING = 13
        STAFF_HEIGHT = 4 * LINE_SPACING  # 52
        INSTRUMENT_GAP = 42
        
        # Top staff center: STAFF_TOP_MARGIN + STAFF_HEIGHT/2 = 30 + 26 = 56
        # Bottom staff center: STAFF_TOP_MARGIN + STAFF_HEIGHT + INSTRUMENT_GAP + STAFF_HEIGHT/2 = 30 + 52 + 42 + 26 = 150
        staff_positions = [56, 150]
        
        for inst in (0, 1):
            row = QWidget(self._left_panel)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(6, 0, 6, 0)
            row_layout.setSpacing(4)

            label = QLabel(f"I{inst + 1}")
            label.setMinimumWidth(14)
            combo = QComboBox()
            combo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            combo.setMinimumWidth(110)
            combo.setMaximumWidth(120)
            combo.setMinimumHeight(22)
            combo.setToolTip("Select default sample bank")
            for bank in available_banks:
                combo.addItem(bank, bank)

            # Default instrument 0 to Guitar-Acoustic, instrument 1 to Guitar-Nylon.
            preferred_defaults = {0: "Guitar-Acoustic", 1: "Guitar-Nylon"}
            preferred_default = preferred_defaults.get(inst, "Piano")
            idx = combo.findData(preferred_default)
            if idx < 0:
                for i in range(combo.count()):
                    data = combo.itemData(i)
                    if isinstance(data, str) and data.lower() == preferred_default.lower():
                        idx = i
                        break
            if idx < 0:
                for i in range(combo.count()):
                    data = combo.itemData(i)
                    if isinstance(data, str) and preferred_default.lower() in data.lower():
                        idx = i
                        break
            if idx < 0 and combo.count() > 0:
                idx = 0
            if idx >= 0:
                combo.setCurrentIndex(idx)
                self._audio.set_default_sample_bank(inst, combo.itemData(idx))

            combo.currentIndexChanged.connect(
                lambda _idx, instrument=inst, box=combo: self._on_instrument_bank_changed(
                    instrument,
                    box.currentData(),
                )
            )

            self._bank_combo_boxes[inst] = combo
            row_layout.addWidget(label)
            row_layout.addWidget(combo)
            
            # Position the row to align with its staff
            row.move(0, staff_positions[inst] - 11)  # -11 to center the 22px high row
            row.resize(150, 22)
            self._instrument_rows[inst] = row

        # Scroll area for the staff (in case it gets tall with 2 lines)
        self._scroll = QScrollArea()
        self._scroll.setWidget(self._staff)
        self._scroll.setWidgetResizable(True)
        # Keep keyboard editing on the main window (arrow keys/tab/backspace)
        self._scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._staff.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Smooth scroll animations
        self._h_anim = QPropertyAnimation(self._scroll.horizontalScrollBar(), b"value", self)
        self._h_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._v_anim = QPropertyAnimation(self._scroll.verticalScrollBar(), b"value", self)
        self._v_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._top_bar = QWidget()
        top_bar_layout = QHBoxLayout(self._top_bar)
        top_bar_layout.setContentsMargins(6, 0, 6, 0)
        top_bar_layout.setSpacing(8)
        top_bar_layout.addWidget(self._title_label, stretch=1)
        top_bar_layout.addWidget(self._load_json_button)
        top_bar_layout.addWidget(self._save_json_button)
        top_bar_layout.addWidget(self._upload_button)
        top_bar_layout.addWidget(self._download_button)

        self._content_row = QWidget()
        content_layout = QHBoxLayout(self._content_row)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        content_layout.addWidget(self._left_panel)
        content_layout.addWidget(self._scroll, stretch=1)

        # Gesture guide strip (above keyboard-controls status line)
        self._gesture_guide_label = QLabel(
            "Gestures: Swipe ↑=PITCH_UP, Swipe ↓=PITCH_DOWN, Open-palm ←/→=SCROLL FWD/BACK, "
            "Peace=SWITCH_STAFF, Pinch=TOGGLE_PLAYBACK, Thumb+Index+Middle=ADD_NOTE, "
            "Pinky only=DELETE_NOTE, Index+Pinky=TOGGLE_INSTRUMENT, "
            "Index+Middle+Ring=SPLIT_NOTE, Thumb+Pinky=MERGE_NOTE, Fist=MAKE_REST"
        )
        self._gesture_guide_label.setWordWrap(False)

        layout.addWidget(self._top_bar)
        layout.addWidget(self._content_row, stretch=1)
        layout.addWidget(self._gesture_guide_label)
        self.setCentralWidget(central)
        self.setFocus()
        self._reset_key_cycle_memory()
        self._refresh_title()
        self._apply_light_theme()

        # Redirect mouse-wheel from vertical to horizontal scrolling
        self._scroll.viewport().installEventFilter(self)

        # ── Status bar ───────────────────────────────────────────
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage(
            "Space: play | ←→: navigate | ↑↓: pitch | W/S: tempo ± | Backspace: delete | Tab: switch staff | T: toggle cursor (1/2/playback) | K: cycle key"
        )

        # ── Signals ──────────────────────────────────────────────
        self._audio.note_playing.connect(self._on_note_playing)
        self._audio.playback_finished.connect(self._on_playback_finished)
        self._editor.cursor_changed.connect(self._on_editor_cursor_changed)
        self._editor.sequence_changed.connect(self._on_sequence_changed)
        self._sync_staff_edit_cursors()

        # ── MuseAid server connection ────────────────────────────
        self._server_client = ServerClient(parent=self)
        self._server_client.command_received.connect(self._on_remote_command)
        self._server_client.sequence_received.connect(self._on_remote_sequence)
        self._server_client.connected.connect(
            lambda: self._status.showMessage("Connected to MuseAid server")
        )
        self._server_client.finished.connect(
            lambda: self._request_global_shutdown("Server client closed — shutting down")
        )
        self._audio.destroyed.connect(
            lambda: self._request_global_shutdown("Audio engine closed — shutting down")
        )
        self._server_client.start()

    def _request_global_shutdown(self, reason: str | None = None) -> None:
        """Shut down all subsystems and quit the application.

        Any critical subsystem teardown funnels through this function so
        closing one component closes the whole app.
        """
        if reason:
            self._status.showMessage(reason)

        self._shutdown()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def _on_instrument_bank_changed(self, instrument: int, sample_bank: str | None) -> None:
        """Apply UI-selected default sample bank for an instrument lane."""
        self._audio.set_default_sample_bank(instrument, sample_bank)
        label = sample_bank if sample_bank else "Auto"
        self._status.showMessage(f"Instrument {instrument + 1} bank: {label}")

    # ── Scroll direction fix ────────────────────────────────────

    def eventFilter(self, obj, event):  # noqa: N802
        """Redirect vertical mouse-wheel scrolling to horizontal."""
        if obj is self._scroll.viewport() and event.type() == QEvent.Type.Wheel:
            delta = event.angleDelta().y()
            hbar = self._scroll.horizontalScrollBar()
            hbar.setValue(hbar.value() - delta)
            return True  # consume the event
        return super().eventFilter(obj, event)

    # ── Key handling ─────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        key = event.key()

        if key == Qt.Key.Key_Space:
            self._toggle_playback()
            event.accept()
            return
        elif key == Qt.Key.Key_Left:
            if self._active_cursor_focus == 2:
                self._move_playback_cursor(-1)
            else:
                self._editor.execute("move_left")
            event.accept()
            return
        elif key == Qt.Key.Key_Right:
            if self._active_cursor_focus == 2:
                self._move_playback_cursor(1)
            else:
                self._editor.execute("move_right")
            event.accept()
            return
        elif key == Qt.Key.Key_Up:
            self._editor.execute("pitch_up")
            self._preview_current_note()
            event.accept()
            return
        elif key == Qt.Key.Key_Down:
            self._editor.execute("pitch_down")
            self._preview_current_note()
            event.accept()
            return
        elif key == Qt.Key.Key_Backspace:
            self._editor.execute("delete_note")
            event.accept()
            return
        elif key == Qt.Key.Key_Tab:
            self._switch_edit_staff()
            event.accept()
            return
        elif key == Qt.Key.Key_T:
            self._toggle_active_edit_cursor()
            event.accept()
            return
        elif key == Qt.Key.Key_K:
            self._cycle_key_signature()
            event.accept()
            return
        elif key == Qt.Key.Key_W:
            self._adjust_tempo(5)
            event.accept()
            return
        elif key == Qt.Key.Key_S:
            self._adjust_tempo(-5)
            event.accept()
            return
        elif key == Qt.Key.Key_U:
            self._editor.execute("split_note")
            event.accept()
            return
        elif key == Qt.Key.Key_I:
            self._editor.execute("merge_note")
            event.accept()
            return
        elif key == Qt.Key.Key_O:
            self._editor.execute("make_rest")
            event.accept()
            return
        else:
            super().keyPressEvent(event)

    def focusNextPrevChild(self, next: bool) -> bool:  # noqa: A002
        """Disable focus traversal on Tab/Shift+Tab so Tab is an edit command."""
        return False

    def _toggle_playback(self) -> None:
        if self._audio.is_playing:
            self._audio.stop()
            if self._sequence.notes:
                self._playback_cursor_index = self._clamp_cursor(self._playback_start_index)
                self._staff.set_playback_cursor(self._playback_cursor_index)
                self._autoscroll_to_note(self._playback_cursor_index)
            self._status.showMessage("Stopped")
        else:
            self._status.showMessage("Playing...")
            start_index = self._clamp_cursor(self._playback_cursor_index) if self._sequence.notes else 0
            self._playback_start_index = start_index
            self._staff.set_playback_cursor(start_index)
            self._audio.play_sequence(self._sequence, start_index=start_index)

    # ── Slots ────────────────────────────────────────────────────

    def _on_note_playing(self, index: int) -> None:
        self._playback_cursor_index = self._clamp_cursor(index)
        self._last_modified_cursor_kind = "playback"
        self._staff.set_playback_cursor(index)
        self._autoscroll_to_note(index)
        if 0 <= index < len(self._sequence.notes):
            note = self._sequence.notes[index]
            label = "REST" if note.is_rest else note.pitch
            self._status.showMessage(
                f"Playing: {label} ({note.note_type}, beat {note.beat})"
            )

    def _on_playback_finished(self) -> None:
        if self._sequence.notes:
            self._playback_cursor_index = self._clamp_cursor(self._playback_start_index)
            self._staff.set_playback_cursor(self._playback_cursor_index)
            self._autoscroll_to_note(self._playback_cursor_index)
        else:
            self._staff.clear_playback_cursor()
        self._status.showMessage(
            "Space: play | ←→: navigate | ↑↓: pitch | W/S: tempo ± | Backspace: delete | Tab: switch staff | T: toggle cursor (1/2/playback) | K: cycle key"
        )

    def _on_sequence_changed(self) -> None:
        self._playback_cursor_index = self._clamp_cursor(self._playback_cursor_index)
        self._playback_start_index = self._clamp_cursor(self._playback_start_index)
        self._sync_staff_edit_cursors()
        self._staff.set_sequence(self._sequence)
        if self._sequence.notes:
            self._staff.set_playback_cursor(self._playback_cursor_index)
        if not self._applying_key_cycle:
            self._reset_key_cycle_memory()
        self._refresh_title()

    def _refresh_title(self) -> None:
        ts = f"{self._sequence.time_sig_num}/{self._sequence.time_sig_den}"
        self._title_label.setText(
            f"  {self._sequence.name}  —  Key: {self._sequence.key}  —  {ts}  —  {self._sequence.bpm} BPM"
        )

    def _adjust_tempo(self, delta_bpm: int) -> None:
        old = self._sequence.bpm
        self._sequence.bpm = max(30, min(280, self._sequence.bpm + delta_bpm))
        if self._sequence.bpm != old:
            self._refresh_title()
            self._status.showMessage(f"Tempo: {self._sequence.bpm} BPM")

    def _preview_current_note(self) -> None:
        note = self._editor.current_note
        if note is None or note.is_rest:
            return
        self._audio.play_note(note.pitch, note.instrument, note.sample_bank)

    def _apply_light_theme(self) -> None:
        main_bg = "#f4f6fb"
        status_bg = "#eef2ff"
        status_fg = "#2b3553"
        status_border = "#d8def0"
        header_bg = "qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #fbfcff, stop:1 #eef2ff)"
        header_border = "#dbe3f6"
        title_color = "#22304d"
        button_bg = "#e9eeff"
        button_border = "#c8d4ff"
        button_fg = "#233862"
        button_hover = "#dce5ff"
        button_press = "#cfdcff"
        scroll_bg = "#f4f6fb"
        bar_bg = "#edf1fb"
        handle_bg = "#c6d2f4"

        self.setStyleSheet(
            f"QMainWindow {{ background: {main_bg}; }}"
            f"QStatusBar {{ background: {status_bg}; color: {status_fg}; border-top: 1px solid {status_border}; padding-left: 8px; }}"
        )
        self._top_bar.setStyleSheet(
            f"background: {header_bg};"
            f"border-bottom: 1px solid {header_border};"
        )
        self._title_label.setStyleSheet(
            f"font-size: 14px; font-weight: 700; padding: 8px 10px; color: {title_color}; background: transparent;"
        )
        self._gesture_guide_label.setStyleSheet(
            f"background: {header_bg};"
            f"border-top: 1px solid {header_border};"
            f"border-bottom: 1px solid {header_border};"
            f"padding: 4px 10px;"
            f"color: {title_color};"
            "font-size: 11px;"
            "font-weight: 600;"
        )
        self._left_panel.setStyleSheet(
            f"background: {scroll_bg};"
            "border: none;"
            f"min-width: 150px;"
            f"max-width: 150px;"
        )
        self._content_row.setStyleSheet(f"background: {scroll_bg};")
        button_style = (
            "QPushButton {"
            f"  background: {button_bg};"
            f"  border: 1px solid {button_border};"
            "  border-radius: 8px;"
            f"  color: {button_fg};"
            "  font-weight: 600;"
            "  padding: 4px 10px;"
            "}"
            f"QPushButton:hover {{ background: {button_hover}; }}"
            f"QPushButton:pressed {{ background: {button_press}; }}"
        )
        self._load_json_button.setStyleSheet(button_style)
        self._save_json_button.setStyleSheet(button_style)
        self._upload_button.setStyleSheet(button_style)
        self._download_button.setStyleSheet(button_style)
        combo_style = (
            "QComboBox {"
            f"  background: {button_bg};"
            f"  border: 1px solid {button_border};"
            "  border-radius: 8px;"
            f"  color: {button_fg};"
            "  font-size: 11px;"
            "  padding: 2px 18px 2px 6px;"
            "  outline: none;"
            "}"
            f"QComboBox:hover {{ background: {button_hover}; border-radius: 8px; }}"
            f"QComboBox:focus {{ background: {button_hover}; border: 2px solid {button_border}; border-radius: 8px; outline: none; }}"
            f"QComboBox:pressed {{ background: {button_press}; border-radius: 8px; }}"
            "QComboBox QAbstractItemView {"
            f"  background: {button_bg};"
            f"  border: 1px solid {button_border};"
            f"  color: {button_fg};"
            "  font-size: 11px;"
            "  border-radius: 4px;"
            "}"
        )
        for box in self._bank_combo_boxes.values():
            box.setStyleSheet(combo_style)
        self._scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: {scroll_bg}; }}"
            f"QScrollBar:vertical, QScrollBar:horizontal {{ background: {bar_bg}; border-radius: 6px; }}"
            "QScrollBar::handle:vertical, QScrollBar::handle:horizontal {"
            f" background: {handle_bg}; border-radius: 6px; min-height: 22px; min-width: 22px; }}"
        )

    @staticmethod
    def _key_tonic(key_name: str) -> str:
        return key_name[:-1] if key_name.endswith("m") else key_name

    def _tonic_index(self, tonic: str) -> int | None:
        return self._TONIC_TO_CHROMATIC.get(tonic)

    def _reset_key_cycle_memory(self) -> None:
        self._key_cycle_origin_key = self._sequence.key
        self._key_cycle_base_indices = []
        for note in self._sequence.notes:
            if note.is_rest or note.pitch not in PITCH_ORDER:
                self._key_cycle_base_indices.append(None)
            else:
                self._key_cycle_base_indices.append(PITCH_ORDER.index(note.pitch))

    def _cycle_key_signature(self) -> None:
        keys = sorted(KEY_SIGNATURES.keys(), key=lambda k: (k.endswith("m"), k))
        current_idx = keys.index(self._sequence.key) if self._sequence.key in keys else 0
        new_key = keys[(current_idx + 1) % len(keys)]

        old_key = self._sequence.key
        if len(self._key_cycle_base_indices) != len(self._sequence.notes):
            self._reset_key_cycle_memory()

        old_tonic = self._key_tonic(self._key_cycle_origin_key)
        new_tonic = self._key_tonic(new_key)
        old_idx = self._tonic_index(old_tonic)
        new_idx = self._tonic_index(new_tonic)
        if old_idx is None or new_idx is None:
            self._status.showMessage(f"Unsupported key change: {old_key} → {new_key}")
            return

        semitone_shift = (new_idx - old_idx) % 12
        for i, note in enumerate(self._sequence.notes):
            base_idx = self._key_cycle_base_indices[i] if i < len(self._key_cycle_base_indices) else None
            if base_idx is None:
                continue
            new_pitch_idx = max(0, min(len(PITCH_ORDER) - 1, base_idx + semitone_shift))
            note.pitch = PITCH_ORDER[new_pitch_idx]

        self._sequence.key = new_key
        self._applying_key_cycle = True
        try:
            self._on_sequence_changed()
        finally:
            self._applying_key_cycle = False
        self._status.showMessage(f"Key changed: {old_key} → {new_key}")

    def _on_editor_cursor_changed(self, index: int) -> None:
        if self._active_cursor_focus != 2:
            self._edit_cursors[self._active_edit_cursor_slot] = self._clamp_cursor(index)
            self._last_modified_cursor_kind = f"edit{self._active_edit_cursor_slot}"
            self._autoscroll_to_note(self._edit_cursors[self._active_edit_cursor_slot])
        self._sync_staff_edit_cursors()

    def _toggle_active_edit_cursor(self) -> None:
        self._active_cursor_focus = (self._active_cursor_focus + 1) % 3

        if self._active_cursor_focus == 2:
            self._status.showMessage("Active cursor: Playback")
            if self._sequence.notes:
                self._staff.set_playback_cursor(self._clamp_cursor(self._playback_cursor_index))
                self._last_modified_cursor_kind = "playback"
                self._autoscroll_to_note(self._playback_cursor_index)
            return

        self._active_edit_cursor_slot = self._active_cursor_focus
        self._status.showMessage(f"Active cursor: {self._active_edit_cursor_slot + 1}")
        self._editor.cursor = self._clamp_cursor(self._edit_cursors[self._active_edit_cursor_slot])

    def _move_playback_cursor(self, delta: int) -> None:
        if not self._sequence.notes:
            return
        self._playback_cursor_index = self._clamp_cursor(self._playback_cursor_index + delta)
        self._last_modified_cursor_kind = "playback"
        self._staff.set_playback_cursor(self._playback_cursor_index)
        self._autoscroll_to_note(self._playback_cursor_index)

    def _clamp_cursor(self, index: int) -> int:
        if not self._sequence.notes:
            return 0
        return max(0, min(index, len(self._sequence.notes) - 1))

    def _sync_staff_edit_cursors(self) -> None:
        primary = self._clamp_cursor(self._edit_cursors[0]) if self._sequence.notes else -1
        secondary = self._clamp_cursor(self._edit_cursors[1]) if self._sequence.notes else -1
        self._edit_cursors[0] = 0 if primary == -1 else primary
        self._edit_cursors[1] = 0 if secondary == -1 else secondary
        self._staff.set_cursors(primary, secondary, self._active_edit_cursor_slot)

    def _import_midi(self) -> None:
        """Import a MIDI file into the current sequence."""
        start_dir = str(self._project_root)
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import MIDI",
            start_dir,
            "MIDI Files (*.mid *.midi)",
        )
        if not file_path:
            return

        try:
            new_seq = import_midi(Path(file_path))
            self._sequence = new_seq
            self._editor.sequence = self._sequence
            self._edit_cursors = [0, 0]
            self._active_edit_cursor_slot = 0
            self._active_cursor_focus = 0
            self._playback_cursor_index = 0
            self._playback_start_index = 0
            self._editor.cursor = 0
            self._staff.set_sequence(self._sequence)
            self._staff.set_playback_cursor(0 if self._sequence.notes else -1)
            self._reset_key_cycle_memory()
            self._refresh_title()
            self._status.showMessage(f"Imported MIDI: {Path(file_path).name}")
        except Exception as exc:  # pragma: no cover - GUI feedback path
            self._status.showMessage(f"MIDI import failed: {exc}")

    def _load_json_sequence(self) -> None:
        """Load a sequence JSON by ID from MongoDB."""
        id_input, ok = QInputDialog.getInt(
            self,
            "Load Sequence",
            "Enter sequence ID:",
            value=1,
            min=1,
            max=999999
        )
        if not ok:
            return

        try:
            self._status.showMessage(f"Loading sequence with ID: {id_input}...")
            
            # Check if entry exists first
            if not dbUtil.entry_exists(id_input):
                self._status.showMessage(f"No sequence found with ID: {id_input}")
                return
            
            # Fetch the entry from MongoDB
            entry = dbUtil.get_entry_by_id(id_input)
            if entry and "data" in entry:
                sequence_data = entry["data"]
                
                # Create a new sequence from the fetched data
                if isinstance(sequence_data, str):
                    # If the data is a JSON string, use it directly
                    new_sequence = Sequence.from_json(sequence_data)
                else:
                    # If the data is a dict, convert to JSON string first
                    import json
                    json_str = json.dumps(sequence_data) if isinstance(sequence_data, dict) else str(sequence_data)
                    new_sequence = Sequence.from_json(json_str)
                
                # Update the current sequence
                self._sequence = new_sequence
                
                # Update the editor with the new sequence
                self._editor.sequence = new_sequence
                self._editor.cursor = 0  # Reset cursor to beginning
                
                # Update the staff widget
                self._staff.set_sequence(self._sequence)
                
                # Reset cursors and refresh UI
                self._edit_cursors = [0, 0]
                self._playback_cursor_index = 0
                self._playback_start_index = 0
                self._active_edit_cursor_slot = 0
                self._active_cursor_focus = 0
                
                # Sync staff cursors and refresh display
                self._sync_staff_edit_cursors()
                self._refresh_title()
                self._reset_key_cycle_memory()
                
                # Emit signals to update UI components
                self._editor.sequence_changed.emit()
                self._editor.cursor_changed.emit(0)
                
                self._status.showMessage(f"Successfully loaded sequence '{new_sequence.name}' (ID: {id_input})")
            else:
                self._status.showMessage(f"Invalid data format for sequence ID: {id_input}")
                
        except Exception as exc:  # pragma: no cover - GUI feedback path
            self._status.showMessage(f"Load failed for ID {id_input}: {exc}")

    def _save_json_sequence(self) -> None:
        """Save the current sequence to MongoDB database."""
        id_input, ok = QInputDialog.getInt(
            self,
            "Save Sequence",
            "Enter sequence ID:",
            value=1,
            min=1,
            max=999999
        )
        if not ok:
            return

        try:
            self._status.showMessage(f"Saving sequence to database with ID: {id_input}...")
            
            # Convert sequence to JSON format
            sequence_json = self._sequence.to_json()
            
            # Check if entry already exists
            if dbUtil.entry_exists(id_input):
                reply = QMessageBox.question(
                    self,
                    "Confirm Overwrite",
                    f"A sequence with ID {id_input} already exists. Do you want to overwrite it?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    self._status.showMessage("Save cancelled")
                    return
            
            # Save to MongoDB
            result = dbUtil.add_entry(id_input, sequence_json)
            
            if result:
                self._status.showMessage(f"Successfully saved sequence '{self._sequence.name}' to database (ID: {id_input})")
            else:
                self._status.showMessage(f"Failed to save sequence to database")
                
        except Exception as exc:
            self._status.showMessage(f"Database save failed: {exc}")

    def _upload_json_file(self) -> None:
        """Load a sequence JSON from the examples directory."""
        start_dir = Path(self._project_root) / "examples"
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Sequence JSON",
            str(start_dir),
            "JSON Files (*.json)",
        )
        if not file_path:
            return

        try:
            new_seq = Sequence.from_file(Path(file_path))
            self._sequence = new_seq
            self._editor.sequence = self._sequence
            self._edit_cursors = [0, 0]
            self._active_edit_cursor_slot = 0
            self._active_cursor_focus = 0
            self._playback_cursor_index = 0
            self._playback_start_index = 0
            self._editor.cursor = 0
            self._staff.set_sequence(self._sequence)
            self._staff.set_playback_cursor(0 if self._sequence.notes else -1)
            self._reset_key_cycle_memory()
            self._refresh_title()
            self._status.showMessage(f"Loaded JSON: {Path(file_path).name}")
        except Exception as exc:  # pragma: no cover - GUI feedback path
            self._status.showMessage(f"JSON load failed: {exc}")

    def _download_json_file(self) -> None:
        """Save the current sequence JSON into the examples directory."""
        start_dir = Path(self._project_root) / "examples"
        start_dir.mkdir(parents=True, exist_ok=True)
        default_name = f"{self._sequence.name.replace(' ', '_')}.json"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Sequence JSON",
            str(start_dir / default_name),
            "JSON Files (*.json)",
        )
        if not file_path:
            return

        out = Path(file_path)
        if out.suffix.lower() != ".json":
            out = out.with_suffix(".json")

        try:
            self._sequence.save(out)
            self._status.showMessage(f"Saved JSON: {out.name}")
        except Exception as exc:  # pragma: no cover - GUI feedback path
            self._status.showMessage(f"JSON save failed: {exc}")

    def _export_midi(self) -> None:
        """Export current sequence as MIDI."""
        default_name = f"{self._sequence.name.replace(' ', '_')}.mid"
        start_dir = str(self._project_root)
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export MIDI",
            str(Path(start_dir) / default_name),
            "MIDI Files (*.mid)",
        )
        if not file_path:
            return

        out = Path(file_path)
        if out.suffix.lower() != ".mid":
            out = out.with_suffix(".mid")

        try:
            export_midi(self._sequence, out)
            self._status.showMessage(f"Exported MIDI: {out.name}")
        except Exception as exc:  # pragma: no cover - GUI feedback path
            self._status.showMessage(f"MIDI export failed: {exc}")

    def _switch_edit_staff(self) -> None:
        """Switch editing focus to the other instrument at the same beat.

        This changes cursor selection only (does not mutate note data).
        """
        if not self._sequence.notes:
            return
        current_index = self._editor.cursor
        if current_index < 0 or current_index >= len(self._sequence.notes):
            return

        current = self._sequence.notes[current_index]
        target_instrument = 1 if current.instrument == 0 else 0

        # Prefer same beat, then nearest beat in opposite instrument
        same_beat_idx = None
        nearest_idx = None
        nearest_dist = float("inf")

        for i, note in enumerate(self._sequence.notes):
            if note.instrument != target_instrument:
                continue
            if note.beat == current.beat:
                same_beat_idx = i
                break
            dist = abs(note.beat - current.beat)
            if dist < nearest_dist:
                nearest_dist = dist
                nearest_idx = i

        new_index = same_beat_idx if same_beat_idx is not None else nearest_idx
        if new_index is not None:
            self._editor.cursor = new_index

    def _autoscroll_to_note(self, index: int) -> None:
        """Keep playback centered with smooth, predictive scrolling.

        This is not purely note-position snapping:
        - Uses a dead-zone so tiny movements don't constantly recenter.
        - Uses look-ahead toward the next note for smoother motion.
        - Animates scrollbar movement with easing.
        """
        center = self._staff.note_center(index)
        if center is None:
            return

        x, y = center

        # Predictive look-ahead: bias toward next note if available
        if self._sequence and index + 1 < len(self._sequence.notes):
            next_center = self._staff.note_center(index + 1)
            if next_center is not None:
                nx, ny = next_center
                x = int(x * 0.7 + nx * 0.3)
                y = int(y * 0.8 + ny * 0.2)

        hbar = self._scroll.horizontalScrollBar()
        vbar = self._scroll.verticalScrollBar()
        viewport_w = self._scroll.viewport().width()
        viewport_h = self._scroll.viewport().height()

        # Dead-zone: only scroll when note exits a comfortable focus region
        focus_left = hbar.value() + int(viewport_w * 0.30)
        focus_right = hbar.value() + int(viewport_w * 0.70)
        focus_top = vbar.value() + int(viewport_h * 0.30)
        focus_bottom = vbar.value() + int(viewport_h * 0.70)

        target_x = hbar.value()
        target_y = vbar.value()

        if x < focus_left or x > focus_right:
            target_x = x - viewport_w // 2
        if y < focus_top or y > focus_bottom:
            target_y = y - viewport_h // 2

        target_x = max(hbar.minimum(), min(hbar.maximum(), target_x))
        target_y = max(vbar.minimum(), min(vbar.maximum(), target_y))

        # Skip tiny adjustments
        if abs(target_x - hbar.value()) < 3:
            target_x = hbar.value()
        if abs(target_y - vbar.value()) < 3:
            target_y = vbar.value()

        if target_x == hbar.value() and target_y == vbar.value():
            return

        # Duration scales lightly with tempo for natural feel
        bpm = self._sequence.bpm if self._sequence else 120
        duration = max(110, min(240, int(180 * (120 / max(60, bpm)))))

        self._h_anim.stop()
        self._h_anim.setDuration(duration)
        self._h_anim.setStartValue(hbar.value())
        self._h_anim.setEndValue(target_x)
        self._h_anim.start()

        self._v_anim.stop()
        self._v_anim.setDuration(duration)
        self._v_anim.setStartValue(vbar.value())
        self._v_anim.setEndValue(target_y)
        self._v_anim.start()

    # ── Remote (server) event handlers ──────────────────────────

    def _on_remote_command(self, command: str) -> None:
        """Handle a command received from the MuseAid server (via gestures)."""
        if command == "toggle_playback":
            self._toggle_playback()
        elif command == "switch_edit_staff":
            self._switch_edit_staff()
        else:
            self._editor.execute(command)

    def _on_remote_sequence(self, sequence_json: str) -> None:
        """Handle a full sequence update from the server (via Gemini/speech)."""
        try:
            new_seq = Sequence.from_json(sequence_json)
        except Exception:
            return

        # Ignore empty sequences from the server (e.g. the default "Untitled"
        # that the server sends on first connect).  We don't want to blow away
        # the locally-loaded composition with nothing.
        if not new_seq.notes:
            return

        self._sequence = new_seq
        self._editor.sequence = self._sequence
        self._edit_cursors = [0, 0]
        self._active_edit_cursor_slot = 0
        self._active_cursor_focus = 0
        self._playback_cursor_index = 0
        self._playback_start_index = 0
        self._editor.cursor = 0
        self._staff.set_sequence(self._sequence)
        self._staff.set_playback_cursor(0 if self._sequence.notes else -1)
        self._reset_key_cycle_memory()
        self._refresh_title()
        self._status.showMessage(
            f"Sequence updated from server — {len(new_seq.notes)} notes"
        )

    def _shutdown(self) -> None:
        """Release background resources exactly once."""
        if self._shutdown_complete:
            return
        self._shutdown_complete = True

        # Stop local playback first so no more timer callbacks fire during teardown.
        try:
            self._audio.stop()
        except Exception:
            pass

        # Then stop network background thread and finally release audio backend.
        try:
            self._server_client.stop()
        except Exception:
            pass

        try:
            self._audio.cleanup()
        except Exception:
            pass

    def closeEvent(self, event) -> None:  # noqa: N802
        self._shutdown()
        super().closeEvent(event)
