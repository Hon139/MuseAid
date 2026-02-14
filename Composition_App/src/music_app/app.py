"""Main application window — ties together the staff, audio engine, and editor."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QEvent, QPropertyAnimation, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QMainWindow, QVBoxLayout, QWidget, QLabel, QStatusBar, QScrollArea,
    QFileDialog,
)

from .audio_engine import AudioEngine
from .commands import SequenceEditor
from .midi_support import export_midi, import_midi
from .models import Sequence
from .server_client import ServerClient
from .staff_widget import StaffWidget


class MainWindow(QMainWindow):
    """The primary application window."""

    def __init__(self, data_dir: Path, example_path: Path | None = None) -> None:
        super().__init__()

        self.setWindowTitle("Music App — Treble Clef")
        self.setMinimumSize(1100, 500)
        self.resize(1200, 600)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # ── Core objects ─────────────────────────────────────────
        self._audio = AudioEngine(data_dir, parent=self)

        if example_path and example_path.exists():
            self._sequence = Sequence.from_file(example_path)
        else:
            self._sequence = Sequence(name="Empty", bpm=120, notes=[])

        self._editor = SequenceEditor(self._sequence, parent=self)
        self._project_root = data_dir.parent

        # ── Widgets ──────────────────────────────────────────────
        self._staff = StaffWidget()
        self._staff.set_sequence(self._sequence)

        ts = f"{self._sequence.time_sig_num}/{self._sequence.time_sig_den}"
        key = self._sequence.key
        title_label = QLabel(
            f"  {self._sequence.name}  —  Key: {key}  —  {ts}  —  {self._sequence.bpm} BPM"
        )
        title_label.setStyleSheet(
            "font-size: 18px; font-weight: bold; padding: 10px; color: #333;"
            "background-color: #ffffff;"
        )

        # Scroll area for the staff (in case it gets tall with 2 lines)
        self._scroll = QScrollArea()
        self._scroll.setWidget(self._staff)
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("border: none; background-color: #ffffff;")
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
        layout.addWidget(title_label)
        layout.addWidget(self._scroll, stretch=1)
        self.setCentralWidget(central)
        self.setFocus()

        # File menu for MIDI import/export
        file_menu = self.menuBar().addMenu("File")
        import_midi_action = file_menu.addAction("Import MIDI...")
        import_midi_action.triggered.connect(self._import_midi)
        export_midi_action = file_menu.addAction("Export MIDI...")
        export_midi_action.triggered.connect(self._export_midi)

        # Redirect mouse-wheel from vertical to horizontal scrolling
        self._scroll.viewport().installEventFilter(self)

        # ── Status bar ───────────────────────────────────────────
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage(
            "Space: play | ←→: navigate | ↑↓: pitch | Backspace: delete | Tab: switch staff"
        )

        # ── Signals ──────────────────────────────────────────────
        self._audio.note_playing.connect(self._on_note_playing)
        self._audio.playback_finished.connect(self._on_playback_finished)
        self._editor.cursor_changed.connect(self._staff.set_cursor)
        self._editor.sequence_changed.connect(self._on_sequence_changed)

        # ── MuseAid server connection ────────────────────────────
        self._server_client = ServerClient(parent=self)
        self._server_client.command_received.connect(self._on_remote_command)
        self._server_client.sequence_received.connect(self._on_remote_sequence)
        self._server_client.connected.connect(
            lambda: self._status.showMessage("Connected to MuseAid server")
        )
        self._server_client.start()

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
            self._editor.execute("move_left")
            event.accept()
            return
        elif key == Qt.Key.Key_Right:
            self._editor.execute("move_right")
            event.accept()
            return
        elif key == Qt.Key.Key_Up:
            self._editor.execute("pitch_up")
            event.accept()
            return
        elif key == Qt.Key.Key_Down:
            self._editor.execute("pitch_down")
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
        else:
            super().keyPressEvent(event)

    def focusNextPrevChild(self, next: bool) -> bool:  # noqa: A002
        """Disable focus traversal on Tab/Shift+Tab so Tab is an edit command."""
        return False

    def _toggle_playback(self) -> None:
        if self._audio.is_playing:
            self._audio.stop()
            self._staff.clear_highlight()
            self._status.showMessage("Stopped")
        else:
            self._status.showMessage("Playing...")
            self._audio.play_sequence(self._sequence)

    # ── Slots ────────────────────────────────────────────────────

    def _on_note_playing(self, index: int) -> None:
        self._staff.set_highlight(index)
        self._autoscroll_to_note(index)
        if 0 <= index < len(self._sequence.notes):
            note = self._sequence.notes[index]
            label = "REST" if note.is_rest else note.pitch
            self._status.showMessage(
                f"Playing: {label} ({note.note_type}, beat {note.beat})"
            )

    def _on_playback_finished(self) -> None:
        self._staff.clear_highlight()
        self._status.showMessage(
            "Space: play | ←→: navigate | ↑↓: pitch | Backspace: delete | Tab: switch staff"
        )

    def _on_sequence_changed(self) -> None:
        self._staff.set_sequence(self._sequence)

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
            self._editor.cursor = 0
            self._staff.set_sequence(self._sequence)
            self._status.showMessage(f"Imported MIDI: {Path(file_path).name}")
        except Exception as exc:  # pragma: no cover - GUI feedback path
            self._status.showMessage(f"MIDI import failed: {exc}")

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
        self._editor.cursor = 0
        self._staff.set_sequence(self._sequence)
        self._status.showMessage(
            f"Sequence updated from server — {len(new_seq.notes)} notes"
        )

    def closeEvent(self, event) -> None:  # noqa: N802
        self._server_client.stop()
        self._audio.cleanup()
        super().closeEvent(event)
