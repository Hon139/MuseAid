"""Treble clef staff widget.

Renders up to 2 wrapped systems. Each system contains two staves:
- instrument 1 on top
- instrument 2 underneath

Notes that share the same beat are aligned vertically (same X) so
simultaneous playback is displayed as simultaneous notation.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QColor, QBrush, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QWidget

from .models import FLAT_POSITIONS, Note, NoteType, Sequence, SHARP_POSITIONS


STAFF_POSITIONS: dict[str, int] = {
    "C4": -6,
    "D4": -5,
    "E4": -4,
    "F4": -3,
    "G4": -2,
    "A4": -1,
    "B4": 0,
    "C5": 1,
    "D5": 2,
    "E5": 3,
    "F5": 4,
    "G5": 5,
    "A5": 6,
    "B5": 7,
}


def _get_staff_position(pitch: str) -> int:
    return STAFF_POSITIONS.get(pitch.replace("#", ""), 0)


def _is_sharp(pitch: str) -> bool:
    return "#" in pitch


class StaffWidget(QWidget):
    # Layout
    STAFF_LEFT_MARGIN = 120
    STAFF_RIGHT_MARGIN = 60
    STAFF_TOP_MARGIN = 70
    LINE_SPACING = 20
    NOTE_SPACING = 80
    NOTE_HEAD_RX = 10
    NOTE_HEAD_RY = 8
    STEM_LENGTH = 55

    KEY_SIG_X_START = 50
    STAFF_SYSTEM_GAP = 90
    INSTRUMENT_GAP = 75  # gap between top and bottom instrument staff

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sequence: Sequence | None = None
        self._highlight_index: int = -1
        self._cursor_index: int = -1
        self._beat_order: list[float] = []
        self._beat_rank: dict[float, int] = {}

        self.setMinimumWidth(950)
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(palette.ColorRole.Window, QColor(255, 255, 255))
        self.setPalette(palette)

    # ---- public API ----
    def set_sequence(self, sequence: Sequence) -> None:
        self._sequence = sequence
        self._rebuild_beat_map()
        self._update_height()
        self.update()

    def set_highlight(self, index: int) -> None:
        self._highlight_index = index
        self.update()

    def clear_highlight(self) -> None:
        self._highlight_index = -1
        self.update()

    def set_cursor(self, index: int) -> None:
        self._cursor_index = index
        self.update()

    def note_center(self, index: int) -> tuple[int, int] | None:
        """Return the pixel center (x, y) for a note index.

        Used by the main window for autoscroll.
        """
        if not self._sequence or index < 0 or index >= len(self._sequence.notes):
            return None

        note = self._sequence.notes[index]
        ln = self._line_for_note(note)
        idx = self._index_in_line_for_note(note)
        x = int(self._note_x(idx))

        if note.is_rest:
            y = int(self._staff_line_y(ln, 2, note.instrument))
        else:
            y = int(self._note_y(ln, _get_staff_position(note.pitch), note.instrument))

        return (x, y)

    # ---- beat mapping (for simultaneous alignment) ----
    def _rebuild_beat_map(self) -> None:
        if not self._sequence:
            self._beat_order = []
            self._beat_rank = {}
            return
        beats = sorted({n.beat for n in self._sequence.notes})
        self._beat_order = beats
        self._beat_rank = {b: i for i, b in enumerate(beats)}

    # ---- spacing helpers ----
    def _key_sig_width(self) -> float:
        if not self._sequence:
            return 0
        num_acc, _ = self._sequence.key_info
        if num_acc == 0:
            return 0
        return num_acc * 14 + 10

    def _time_sig_x(self) -> float:
        return self.STAFF_LEFT_MARGIN + self.KEY_SIG_X_START + self._key_sig_width()

    def _first_note_x_offset(self) -> float:
        return self.KEY_SIG_X_START + self._key_sig_width() + 45

    def _beats_per_line(self) -> int:
        available = (
            self.width()
            - self.STAFF_LEFT_MARGIN
            - self._first_note_x_offset()
            - self.STAFF_RIGHT_MARGIN
        )
        if available <= 0:
            return 1
        return max(1, int(available / self.NOTE_SPACING) + 1)

    def _num_lines(self) -> int:
        if not self._beat_order:
            return 1
        bpl = self._beats_per_line()
        return min(2, (len(self._beat_order) + bpl - 1) // bpl)

    def _line_for_note(self, note: Note) -> int:
        rank = self._beat_rank.get(note.beat, 0)
        return min(rank // self._beats_per_line(), 1)

    def _index_in_line_for_note(self, note: Note) -> int:
        rank = self._beat_rank.get(note.beat, 0)
        line = self._line_for_note(note)
        return rank - line * self._beats_per_line()

    def _line_for_beat_rank(self, rank: int) -> int:
        return min(rank // self._beats_per_line(), 1)

    def _index_in_line_for_beat_rank(self, rank: int) -> int:
        line = self._line_for_beat_rank(rank)
        return rank - line * self._beats_per_line()

    def _staff_height(self) -> float:
        return 4 * self.LINE_SPACING

    def _system_height(self) -> float:
        # two staves + stems + inter-staff gap + padding
        return (2 * self._staff_height()) + self.INSTRUMENT_GAP + (2 * self.STEM_LENGTH) + 40

    def _update_height(self) -> None:
        n = self._num_lines()
        h = self.STAFF_TOP_MARGIN + n * self._system_height()
        if n > 1:
            h += self.STAFF_SYSTEM_GAP * (n - 1)
        h += 60
        self.setMinimumHeight(int(h))

    def _system_top_y(self, line_num: int) -> float:
        y = self.STAFF_TOP_MARGIN
        if line_num > 0:
            y += line_num * (self._system_height() + self.STAFF_SYSTEM_GAP)
        return y

    def _staff_top_y(self, line_num: int, instrument: int) -> float:
        top = self._system_top_y(line_num)
        if instrument == 0:
            return top
        return top + self._staff_height() + self.INSTRUMENT_GAP

    def _staff_line_y(self, line_num: int, staff_line_idx: int, instrument: int) -> float:
        return self._staff_top_y(line_num, instrument) + staff_line_idx * self.LINE_SPACING

    def _note_y(self, line_num: int, staff_pos: int, instrument: int) -> float:
        middle_y = self._staff_line_y(line_num, 2, instrument)
        return middle_y - staff_pos * (self.LINE_SPACING / 2)

    def _note_x(self, idx_in_line: int) -> float:
        return self.STAFF_LEFT_MARGIN + self._first_note_x_offset() + idx_in_line * self.NOTE_SPACING

    # ---- paint ----
    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        n_lines = self._num_lines()
        for ln in range(n_lines):
            for inst in (0, 1):
                self._draw_staff_lines(p, ln, inst)
                self._draw_treble_clef(p, ln, inst)
                if self._sequence:
                    self._draw_key_signature(p, ln, inst)
                    self._draw_time_signature(p, ln, inst)

        if self._sequence:
            for i, note in enumerate(self._sequence.notes):
                ln = self._line_for_note(note)
                if ln >= n_lines:
                    continue
                idx = self._index_in_line_for_note(note)
                if note.is_rest:
                    self._draw_rest(p, i, note, ln, idx)
                else:
                    self._draw_note(p, i, note, ln, idx)
            self._draw_bar_lines(p, n_lines)

        p.end()

    # ---- shared notation elements ----
    def _draw_staff_lines(self, p: QPainter, ln: int, instrument: int) -> None:
        p.setPen(QPen(QColor(80, 80, 80), 1.2))
        right = self.width() - self.STAFF_RIGHT_MARGIN
        for i in range(5):
            y = self._staff_line_y(ln, i, instrument)
            p.drawLine(int(self.STAFF_LEFT_MARGIN), int(y), int(right), int(y))

    def _draw_key_signature(self, p: QPainter, ln: int, instrument: int) -> None:
        if not self._sequence:
            return
        num_acc, is_sharps = self._sequence.key_info
        if num_acc == 0:
            return

        positions = SHARP_POSITIONS if is_sharps else FLAT_POSITIONS
        symbol = "♯" if is_sharps else "♭"

        p.setFont(QFont("serif", 16, QFont.Weight.Bold))
        p.setPen(QColor(40, 40, 40))

        x_start = self.STAFF_LEFT_MARGIN + self.KEY_SIG_X_START
        for i in range(num_acc):
            pos = positions[i]
            y = self._note_y(ln, pos, instrument)
            x = x_start + i * 14
            p.drawText(int(x - 5), int(y + 6), symbol)

    def _draw_time_signature(self, p: QPainter, ln: int, instrument: int) -> None:
        if not self._sequence:
            return
        x = self._time_sig_x() + 15
        p.setFont(QFont("serif", 22, QFont.Weight.Bold))
        p.setPen(QColor(40, 40, 40))

        top = self._staff_line_y(ln, 0, instrument)
        mid = self._staff_line_y(ln, 2, instrument)
        bot = self._staff_line_y(ln, 4, instrument)

        num_rect = QRectF(x - 15, top - 2, 30, mid - top + 4)
        den_rect = QRectF(x - 15, mid - 2, 30, bot - mid + 4)
        p.drawText(num_rect, Qt.AlignmentFlag.AlignCenter, str(self._sequence.time_sig_num))
        p.drawText(den_rect, Qt.AlignmentFlag.AlignCenter, str(self._sequence.time_sig_den))

    def _draw_treble_clef(self, p: QPainter, ln: int, instrument: int) -> None:
        p.save()
        g_y = self._staff_line_y(ln, 3, instrument)
        x = self.STAFF_LEFT_MARGIN + 22
        s = self.LINE_SPACING / 16.0
        pen = QPen(QColor(40, 40, 40), 2.2 * s)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

        ls = self.LINE_SPACING
        bot = g_y + 3.0 * ls
        top = g_y - 3.5 * ls
        path = QPainterPath()
        path.moveTo(x + 4 * s, bot)
        path.cubicTo(x - 12 * s, bot - 4 * s, x - 8 * s, bot - 16 * s, x + 2 * s, bot - 14 * s)
        path.cubicTo(x + 10 * s, bot - 12 * s, x + 16 * s, g_y + 2 * ls, x + 14 * s, g_y + 0.5 * ls)
        path.cubicTo(x + 12 * s, g_y - 0.8 * ls, x - 14 * s, g_y - 1.0 * ls, x - 10 * s, g_y - 2.5 * ls)
        path.cubicTo(x - 6 * s, top, x + 10 * s, top, x + 4 * s, g_y - 1.5 * ls)
        path.cubicTo(x, g_y - 0.5 * ls, x - 8 * s, g_y + 0.5 * ls, x - 6 * s, g_y + 1.5 * ls)
        path.cubicTo(x - 4 * s, g_y + 2.2 * ls, x + 2 * s, g_y + 2.5 * ls, x + 4 * s, bot)
        p.drawPath(path)
        p.drawLine(QPointF(x + 4 * s, top + 6 * s), QPointF(x + 4 * s, bot))
        p.setBrush(QBrush(QColor(40, 40, 40)))
        p.drawEllipse(QPointF(x + 4 * s, bot + 2 * s), 3 * s, 3 * s)
        p.restore()

    def _draw_bar_lines(self, p: QPainter, n_lines: int) -> None:
        seq = self._sequence
        if not seq or not self._beat_order:
            return

        beats_per_measure = seq.beats_per_measure
        p.setPen(QPen(QColor(60, 60, 60), 1.4))

        for beat in self._beat_order:
            if beat <= 0 or beat % beats_per_measure != 0:
                continue
            rank = self._beat_rank[beat]
            line = self._line_for_beat_rank(rank)
            if line >= n_lines:
                continue
            idx = self._index_in_line_for_beat_rank(rank)
            x = self._note_x(idx) - self.NOTE_SPACING * 0.5

            for inst in (0, 1):
                top = self._staff_line_y(line, 0, inst)
                bot = self._staff_line_y(line, 4, inst)
                p.drawLine(int(x), int(top), int(x), int(bot))

        # Final double bar on last displayed beat
        last_rank = min(len(self._beat_order) - 1, n_lines * self._beats_per_line() - 1)
        line = self._line_for_beat_rank(last_rank)
        idx = self._index_in_line_for_beat_rank(last_rank)
        x = self._note_x(idx) + self.NOTE_SPACING * 0.45

        for inst in (0, 1):
            top = self._staff_line_y(line, 0, inst)
            bot = self._staff_line_y(line, 4, inst)
            p.setPen(QPen(QColor(50, 50, 50), 1.4))
            p.drawLine(int(x), int(top), int(x), int(bot))
            p.setPen(QPen(QColor(50, 50, 50), 3.5))
            p.drawLine(int(x + 6), int(top), int(x + 6), int(bot))

    # ---- rests ----
    def _draw_rest(self, p: QPainter, gi: int, note: Note, ln: int, idx: int) -> None:
        cx = self._note_x(idx)
        nt = note.get_note_type()
        inst = note.instrument
        mid_y = self._staff_line_y(ln, 2, inst)

        is_hl = gi == self._highlight_index
        is_cur = gi == self._cursor_index
        color = QColor(30, 144, 255) if is_hl else QColor(255, 100, 50) if is_cur else QColor(40, 40, 40)

        p.setFont(QFont("serif", 24, QFont.Weight.Bold))
        p.setPen(color)

        if nt == NoteType.WHOLE:
            ry = self._staff_line_y(ln, 1, inst)
            p.setBrush(QBrush(color))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRect(QRectF(cx - 10, ry, 20, self.LINE_SPACING / 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
        elif nt == NoteType.HALF:
            ry = mid_y - self.LINE_SPACING / 2
            p.setBrush(QBrush(color))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRect(QRectF(cx - 10, ry, 20, self.LINE_SPACING / 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
        elif nt == NoteType.QUARTER:
            p.setPen(QPen(color, 2.5))
            s = self.LINE_SPACING * 0.5
            y0 = self._staff_line_y(ln, 1, inst)
            p.drawLine(int(cx - 4), int(y0), int(cx + 4), int(y0 + s))
            p.drawLine(int(cx + 4), int(y0 + s), int(cx - 4), int(y0 + 2 * s))
            p.drawLine(int(cx - 4), int(y0 + 2 * s), int(cx + 4), int(y0 + 3 * s))
        else:  # eighth
            p.setPen(QPen(color, 2.2))
            y0 = mid_y - self.LINE_SPACING * 0.5
            p.setBrush(QBrush(color))
            p.drawEllipse(QPointF(cx + 3, y0), 3, 3)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawLine(int(cx + 3), int(y0), int(cx - 5), int(y0 + self.LINE_SPACING * 1.5))

        if is_cur and not is_hl:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(255, 100, 50, 150)))
            tri = QPainterPath()
            ty = mid_y + self.LINE_SPACING + 12
            tri.moveTo(cx - 5, ty)
            tri.lineTo(cx + 5, ty)
            tri.lineTo(cx, ty - 6)
            tri.closeSubpath()
            p.drawPath(tri)
            p.setBrush(Qt.BrushStyle.NoBrush)

    # ---- notes ----
    def _draw_note(self, p: QPainter, gi: int, note: Note, ln: int, idx: int) -> None:
        staff_pos = _get_staff_position(note.pitch)
        cx = self._note_x(idx)
        inst = note.instrument
        cy = self._note_y(ln, staff_pos, inst)
        nt = note.get_note_type()

        is_hl = gi == self._highlight_index
        is_cur = gi == self._cursor_index
        color = QColor(30, 144, 255) if is_hl else QColor(255, 100, 50) if is_cur else QColor(30, 30, 30)

        rx, ry = self.NOTE_HEAD_RX, self.NOTE_HEAD_RY

        # ledger lines
        p.setPen(QPen(QColor(80, 80, 80), 1.2))
        if staff_pos <= -6:
            for pos in range(-6, -4, 2):
                if pos >= staff_pos:
                    ly = self._note_y(ln, pos, inst)
                    p.drawLine(int(cx - rx - 6), int(ly), int(cx + rx + 6), int(ly))
        if staff_pos >= 6:
            for pos in range(6, staff_pos + 1, 2):
                ly = self._note_y(ln, pos, inst)
                p.drawLine(int(cx - rx - 6), int(ly), int(cx + rx + 6), int(ly))

        # note head
        filled = nt in (NoteType.QUARTER, NoteType.EIGHTH)
        p.save()
        p.translate(cx, cy)
        p.rotate(-12)
        if filled:
            p.setPen(QPen(color, 1.5))
            p.setBrush(QBrush(color))
        else:
            p.setPen(QPen(color, 2.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
        if nt == NoteType.WHOLE:
            p.drawEllipse(QRectF(-rx * 1.3, -ry, rx * 2.6, ry * 2))
        else:
            p.drawEllipse(QRectF(-rx, -ry, rx * 2, ry * 2))
        p.restore()

        # stem
        if nt != NoteType.WHOLE:
            p.setPen(QPen(color, 1.8))
            if staff_pos < 0:
                sx = cx + rx - 1
                p.drawLine(int(sx), int(cy), int(sx), int(cy - self.STEM_LENGTH))
            else:
                sx = cx - rx + 1
                p.drawLine(int(sx), int(cy), int(sx), int(cy + self.STEM_LENGTH))

        # flag
        if nt == NoteType.EIGHTH:
            p.setPen(QPen(color, 2.0))
            if staff_pos < 0:
                sx = cx + rx - 1
                sy = cy - self.STEM_LENGTH
                path = QPainterPath()
                path.moveTo(sx, sy)
                path.cubicTo(sx + 12, sy + 10, sx + 8, sy + 20, sx + 2, sy + 28)
                p.drawPath(path)
            else:
                sx = cx - rx + 1
                sy = cy + self.STEM_LENGTH
                path = QPainterPath()
                path.moveTo(sx, sy)
                path.cubicTo(sx - 12, sy - 10, sx - 8, sy - 20, sx - 2, sy - 28)
                p.drawPath(path)

        # accidental
        if _is_sharp(note.pitch):
            p.setFont(QFont("serif", 15, QFont.Weight.Bold))
            p.setPen(color)
            p.drawText(int(cx - rx - 20), int(cy + 5), "♯")

        # small visual marker for instrument 2
        if note.instrument == 1:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(100, 180, 100, 180)))
            diamond = QPainterPath()
            dx = cx + rx + 8
            dy = cy
            diamond.moveTo(dx, dy - 4)
            diamond.lineTo(dx + 4, dy)
            diamond.lineTo(dx, dy + 4)
            diamond.lineTo(dx - 4, dy)
            diamond.closeSubpath()
            p.drawPath(diamond)
            p.setBrush(Qt.BrushStyle.NoBrush)

        if is_cur and not is_hl:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(255, 100, 50, 150)))
            tri = QPainterPath()
            ty = cy + ry + 14
            tri.moveTo(cx - 6, ty)
            tri.lineTo(cx + 6, ty)
            tri.lineTo(cx, ty - 7)
            tri.closeSubpath()
            p.drawPath(tri)
            p.setBrush(Qt.BrushStyle.NoBrush)

