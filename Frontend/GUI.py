# ─────────────────────────────────────────────────────────────
#  GUI.py  —  Jarvis Frontend
#  FIX: PermissionError on Status.data / all .data files
#  FIX: Safe file read/write with retry
# ─────────────────────────────────────────────────────────────

from PyQt5.QtWidgets import (QApplication, QMainWindow, QTextEdit, QStackedWidget,
                             QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QFrame, QLabel, QSizePolicy, QGraphicsOpacityEffect)
from PyQt5.QtGui import (QIcon, QPainter, QColor, QTextCharFormat, QFont,
                         QPixmap, QTextBlockFormat, QMovie, QPen, QBrush,
                         QLinearGradient, QRadialGradient, QPainterPath, QConicalGradient)
from PyQt5.QtCore import Qt, QSize, QTimer, QRect, QPointF, QRectF, pyqtSignal
from dotenv import dotenv_values
import sys
import os
import math
import random
import time

env_vars      = dotenv_values(".env")
Assistantname = env_vars.get("AssistantName", env_vars.get("Assistantname", "Jarvis"))
current_dir   = os.getcwd()
old_chat_message = ""

TempDirPath     = os.path.join(current_dir, "Frontend", "Files")
GraphicsDirPath = os.path.join(current_dir, "Frontend", "Graphics")

# Ensure directories exist
os.makedirs(TempDirPath, exist_ok=True)
os.makedirs(GraphicsDirPath, exist_ok=True)


# ── Safe File Helpers (PermissionError fix) ───────────────────
def _safe_read(filepath: str, retries: int = 5, delay: float = 0.2) -> str:
    for _ in range(retries):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        except PermissionError:
            time.sleep(delay)
        except FileNotFoundError:
            return ""
        except Exception:
            return ""
    return ""


def _safe_write(filepath: str, content: str, retries: int = 5, delay: float = 0.2) -> bool:
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    for _ in range(retries):
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except PermissionError:
            time.sleep(delay)
        except Exception:
            return False
    return False


# ── Helpers ────────────────────────────────────────────────────
def AnswerModifier(Answer: str) -> str:
    lines = Answer.split('\n')
    non_empty_lines = [line for line in lines if line.strip()]
    return '\n'.join(non_empty_lines)


def QueryModifier(Query: str) -> str:
    new_query   = Query.lower().strip()
    query_words = new_query.split()
    if not query_words:
        return Query
    question_words = ["how", "what", "who", "where", "when", "why", "which",
                      "whose", "whom", "can you", "what's", "where's", "how's"]
    if any(word + " " in new_query for word in question_words):
        if query_words[-1][-1] in ['_', '?', '!']:
            new_query = new_query[:-1] + "?"
        else:
            new_query += "?"
    else:
        if query_words[-1][-1] in ['_', '?', '!']:
            new_query = new_query[:-1] + "."
        else:
            new_query += "."
    return new_query.capitalize()


def SetMicrophoneStatus(Command: str) -> None:
    _safe_write(os.path.join(TempDirPath, "Mic.data"), Command)


def GetMicrophoneStatus() -> str:
    return _safe_read(os.path.join(TempDirPath, "Mic.data"))


def SetAssistantStatus(Status: str) -> None:
    _safe_write(os.path.join(TempDirPath, "Status.data"), Status)


def GetAssistantStatus() -> str:
    return _safe_read(os.path.join(TempDirPath, "Status.data"))


def MicButtonInitialed() -> None:
    SetMicrophoneStatus("False")


def MicButtonClosed() -> None:
    SetMicrophoneStatus("True")


def GraphicsDirectoryPath(Filename: str) -> str:
    return os.path.join(GraphicsDirPath, Filename)


def TempDirectoryPath(Filename: str) -> str:
    return os.path.join(TempDirPath, Filename)


def ShowTextToScreen(Text: str) -> None:
    _safe_write(os.path.join(TempDirPath, "Responses.data"), Text)


# ── Initialize data files if missing ──────────────────────────
for _fname in ["Mic.data", "Status.data", "Responses.data", "Database.data", "ImageGeneration.data"]:
    _fpath = os.path.join(TempDirPath, _fname)
    if not os.path.exists(_fpath):
        _safe_write(_fpath, "")


# ─────────────────────────────────────────────
#  JARVIS ORB
# ─────────────────────────────────────────────
class JarvisOrb(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setStyleSheet("background-color: black;")
        self.t   = 0.0
        self.rot = 0.0

        self.particles = []
        for _ in range(220):
            th = random.uniform(0, math.pi * 2)
            ph = math.acos(2 * random.random() - 1)
            self.particles.append({
                'th':  th, 'ph':  ph,
                'r_f': 0.3 + random.random() * 0.65,
                'spd': 0.00015 + random.random() * 0.0003,
                'pt':  random.uniform(0, math.pi * 2),
                'pp':  random.uniform(0, math.pi * 2),
                'amp': 0.05 + random.random() * 0.08,
                'sz':  0.5  + random.random() * 1.0,
                'op':  0.2  + random.random() * 0.5,
            })

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(16)

    def _tick(self):
        self.t   += 0.010
        self.rot += 0.004
        self.update()

    def _pen(self, painter, r, g, b, alpha_f, lw):
        pen = QPen(QColor(r, g, b, max(0, min(255, int(alpha_f * 255)))))
        pen.setWidthF(lw)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

    def _circle(self, painter, cx, cy, r, r_, g_, b_, alpha_f, lw):
        self._pen(painter, r_, g_, b_, alpha_f, lw)
        painter.drawEllipse(QPointF(cx, cy), r, r)

    def _arc_segments(self, painter, cx, cy, r, n, gap, alpha_f, lw, offset, cyan):
        seg = (math.pi * 2 / n) * (1 - gap)
        rc, gc, bc = (0, 210, 255) if cyan else (255, 255, 255)
        self._pen(painter, rc, gc, bc, alpha_f, lw)
        for i in range(n):
            start = offset + (math.pi * 2 / n) * i
            rect  = QRectF(cx - r, cy - r, r * 2, r * 2)
            painter.drawArc(rect,
                            int(-math.degrees(start) * 16),
                            int(-math.degrees(seg)   * 16))

    def _tick_marks(self, painter, cx, cy, r, n, length, alpha_f, offset, cyan):
        rc, gc, bc = (0, 210, 255) if cyan else (255, 255, 255)
        self._pen(painter, rc, gc, bc, alpha_f, 0.8)
        for i in range(n):
            a  = offset + (math.pi * 2 / n) * i
            x1 = cx + math.cos(a) * r
            y1 = cy + math.sin(a) * r
            x2 = cx + math.cos(a) * (r + length)
            y2 = cy + math.sin(a) * (r + length)
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    def _hex_ring(self, painter, cx, cy, r, sides, offset, alpha_f, lw):
        self._pen(painter, 255, 255, 255, alpha_f, lw)
        pts = []
        for i in range(sides + 1):
            a = offset + (i / sides) * math.pi * 2
            pts.append(QPointF(cx + math.cos(a) * r, cy + math.sin(a) * r))
        for i in range(len(pts) - 1):
            painter.drawLine(pts[i], pts[i + 1])

    def _draw_particles(self, painter, cx, cy, R):
        painter.setPen(Qt.NoPen)
        t   = self.t
        rot = self.rot
        for p in self.particles:
            r_val = R * p['r_f']
            theta = (p['th'] + t * p['spd'] * 60
                     + math.sin(t * 0.35 + p['pt']) * p['amp'])
            phi   = p['ph'] + math.cos(t * 0.25 + p['pp']) * p['amp'] * 0.6
            x3 = r_val * math.sin(phi) * math.cos(theta + rot * 0.2)
            y3 = r_val * math.sin(phi) * math.sin(theta + rot * 0.2)
            z3 = r_val * math.cos(phi)
            sc = (z3 / R) * 0.3 + 0.7
            px = cx + x3 * sc
            py = cy + y3 * sc
            al = max(0, min(255, int(
                p['op'] * sc * (0.6 + 0.4 * math.sin(t * 0.8 + p['pt'])) * 255
            )))
            painter.setBrush(QBrush(QColor(255, 255, 255, al)))
            rad = p['sz'] * sc
            painter.drawEllipse(QPointF(px, py), rad, rad)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h   = self.width(), self.height()
        cx, cy = w / 2, h / 2
        R      = min(w, h) * 0.19
        t      = self.t
        rot    = self.rot
        pulse   = math.sin(t * 0.7) * 0.5 + 0.5
        breathe = math.sin(t * 0.5) * 2.5

        painter.fillRect(self.rect(), QColor(0, 0, 0))

        for i in range(12):
            frac  = i / 11
            rad_g = R * (1.05 + frac * 0.55)
            alpha = int((0.13 - frac * 0.11) * (0.7 + pulse * 0.3) * 255)
            alpha = max(0, min(255, alpha))
            self._pen(painter, 0, 200, 255, alpha / 255, 2.5 - frac * 1.8)
            painter.drawEllipse(QPointF(cx, cy), rad_g, rad_g)

        self._circle(painter, cx, cy, R * 1.07 + breathe * 0.3,
                     0, 230, 255, 0.55 + pulse * 0.20, 1.8)
        self._circle(painter, cx, cy, R * 1.10 + breathe * 0.3,
                     0, 200, 255, 0.25 + pulse * 0.12, 1.0)
        self._circle(painter, cx, cy, R * 1.14 + breathe * 0.25,
                     0, 180, 255, 0.12 + pulse * 0.07, 0.6)
        self._circle(painter, cx, cy, R * 1.20 + breathe * 0.2,
                     0, 160, 255, 0.06 + pulse * 0.04, 0.4)
        self._circle(painter, cx, cy, R * 1.28 + breathe * 0.3,
                     0, 210, 255, 0.10, 0.5)

        self._arc_segments(painter, cx, cy,
                           R * 1.18 + breathe * 0.4,
                           8, 0.18, 0.35 + pulse * 0.15, 1.4, rot * 0.3, True)

        self._tick_marks(painter, cx, cy, R * 1.22, 64, 4,  0.20, rot * 0.3,  True)
        self._tick_marks(painter, cx, cy, R * 1.22, 16, 8,  0.40, rot * 0.3,  True)

        self._circle(painter, cx, cy,
                     R * 1.05 + breathe * 0.5,
                     0, 220, 255, 0.60 + pulse * 0.18, 1.3)

        self._arc_segments(painter, cx, cy, R * 0.95,
                           12, 0.22, 0.18 + pulse * 0.08, 0.8, -rot * 0.5, False)

        self._tick_marks(painter, cx, cy, R * 0.98, 48, 3, 0.14, -rot * 0.4, False)

        self._hex_ring(painter, cx, cy, R * 0.82, 6,  rot * 0.15, 0.12, 0.6)
        self._hex_ring(painter, cx, cy, R * 0.70, 6, -rot * 0.20, 0.08, 0.4)

        for k in range(4):
            a = rot * 0.4 + (k / 4) * math.pi
            self._pen(painter, 255, 255, 255, 0.12 + pulse * 0.06, 0.6)
            painter.drawLine(
                QPointF(cx + math.cos(a) * R * 0.15, cy + math.sin(a) * R * 0.15),
                QPointF(cx + math.cos(a) * R * 0.62, cy + math.sin(a) * R * 0.62),
            )

        self._circle(painter, cx, cy, R * 0.55,
                     255, 255, 255, 0.35 + pulse * 0.12, 0.8)

        self._draw_particles(painter, cx, cy, R)

        cg = QRadialGradient(cx, cy, R * 0.38)
        cg.setFocalPoint(QPointF(cx, cy))
        cg.setColorAt(0,   QColor(200, 240, 255, int((0.15 + pulse * 0.10) * 255)))
        cg.setColorAt(0.5, QColor(180, 230, 255, int((0.04 + pulse * 0.02) * 255)))
        cg.setColorAt(1,   QColor(0,   0,   0,   0))
        cg.setRadius(R * 0.38)
        painter.setBrush(QBrush(cg))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), R * 0.38, R * 0.38)

        dot_r = 2.5 + pulse * 1.0
        painter.setBrush(QBrush(QColor(200, 240, 255,
                                       int((0.8 + pulse * 0.2) * 255))))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), dot_r, dot_r)

        painter.end()


# ─────────────────────────────────────────────
#  HUD BOX
# ─────────────────────────────────────────────
class HudBox(QWidget):
    def __init__(self, parent, title, value, sub, fill_f):
        super().__init__(parent)
        self._title  = title
        self._value  = value
        self._sub    = sub
        self._fill_f = fill_f
        self._t      = 0.0
        timer = QTimer(self)
        timer.timeout.connect(self._tick)
        timer.start(50)
        self.setFixedSize(128, 70)

    def _tick(self):
        self._t += 0.04
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h    = self.width(), self.height()
        pulse   = math.sin(self._t * 0.7) * 0.5 + 0.5
        box_a   = int((0.38 + pulse * 0.14) * 255)

        bp = QPen(QColor(0, 191, 255, box_a))
        bp.setWidthF(0.8)
        painter.setPen(bp)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(QRectF(0, 0, w, h), 4, 4)

        painter.setFont(QFont("Courier New", 7))
        painter.setPen(QColor(0, 191, 255, box_a))
        painter.drawText(QPointF(10, 17), self._title)

        fv = QFont("Courier New", 13)
        fv.setBold(True)
        painter.setFont(fv)
        painter.setPen(QColor(0, 225, 255, box_a))
        painter.drawText(QPointF(10, 35), self._value)

        painter.setFont(QFont("Courier New", 7))
        painter.setPen(QColor(0, 191, 255, max(0, box_a - 60)))
        painter.drawText(QPointF(10, 50), self._sub)

        bar_w = int((w - 20) * self._fill_f)
        painter.setPen(QPen(QColor(0, 191, 255, 50), 0.4))
        painter.drawLine(10, 58, w - 10, 58)
        painter.setPen(QPen(QColor(0, 220, 255, box_a), 1.8))
        painter.drawLine(10, 58, 10 + bar_w, 58)

        painter.end()


# ─────────────────────────────────────────────
#  INITIAL SCREEN
# ─────────────────────────────────────────────
class InitialScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        desktop  = QApplication.desktop()
        self._sw = desktop.screenGeometry().width()
        self._sh = desktop.screenGeometry().height()

        self.setFixedSize(self._sw, self._sh)
        self.setStyleSheet("background-color: #000005;")

        self._amb_t = 0.0
        self._amb_timer = QTimer(self)
        self._amb_timer.timeout.connect(self._amb_tick)
        self._amb_timer.start(50)

        orb_h = int(self._sw * 9 / 16)
        self.orb = JarvisOrb(self)
        self.orb.setFixedSize(self._sw, orb_h)
        orb_top = int(self._sh * 0.02)
        self.orb.move(0, orb_top)
        orb_centre_y = orb_top + orb_h // 2

        self.label = QLabel("", self)
        self.label.setStyleSheet("""
            color: #00cfff;
            font-size: 15px;
            font-family: 'Courier New', monospace;
            background-color: #020d1a;
            border: 1px solid #00bfff;
            border-radius: 14px;
            padding: 5px 22px;
        """)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setFixedWidth(300)
        label_h   = 36
        label_top = orb_centre_y + int(orb_h * 0.28)
        self.label.move((self._sw - 300) // 2, label_top)

        self.icon_label = QLabel(self)
        self.icon_label.setFixedSize(70, 70)
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet("""
            background-color: #0055bb;
            border-radius: 35px;
            border: 2px solid #00bfff;
        """)
        mic_top = label_top + label_h + 14
        self.icon_label.move((self._sw - 70) // 2, mic_top)

        self.hud_tl = HudBox(self, "CORE TEMP",  "98.6°", "STATUS: NOMINAL", 0.62)
        self.hud_tr = HudBox(self, "NEURAL NET", "99.2%", "SYNC:  ACTIVE",   0.56)
        self.hud_tl.move(20, 46)
        self.hud_tr.move(self._sw - 148, 46)

        self.hud_bl = HudBox(self, "UPTIME",  "14:22", "MODE: ACTIVE", 0.45)
        self.hud_br = HudBox(self, "MEMORY",  "87%",   "RAM: 14.2 GB", 0.87)
        bottom_y = self._sh - 90
        self.hud_bl.move(20, bottom_y)
        self.hud_br.move(self._sw - 148, bottom_y)

        self.toggled = True
        self.toggle_icon()
        self.icon_label.mousePressEvent = self.toggle_icon

        self.orb.raise_()
        self.label.raise_()
        self.icon_label.raise_()
        self.hud_tl.raise_()
        self.hud_tr.raise_()
        self.hud_bl.raise_()
        self.hud_br.raise_()

        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self.SpeechRecogText)
        self._status_timer.start(5)

    def _amb_tick(self):
        self._amb_t += 0.04
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h  = self.width(), self.height()
        t     = self._amb_t
        pulse = math.sin(t * 0.7) * 0.5 + 0.5

        painter.fillRect(self.rect(), QColor(0, 0, 5))

        blen = 40
        ba   = int((0.50 + pulse * 0.18) * 255)
        pen  = QPen(QColor(0, 191, 255, ba))
        pen.setWidthF(1.5)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        for (cx2, cy2), (dx, dy) in [
            ((20, 20),     ( 1,  1)),
            ((w-20, 20),   (-1,  1)),
            ((20, h-20),   ( 1, -1)),
            ((w-20, h-20), (-1, -1)),
        ]:
            painter.drawLine(cx2, cy2, cx2 + dx*blen, cy2)
            painter.drawLine(cx2, cy2, cx2,           cy2 + dy*blen)

        la   = int((0.25 + pulse * 0.12) * 255)
        pen2 = QPen(QColor(0, 210, 255, la))
        pen2.setWidthF(0.8)
        painter.setPen(pen2)
        mid_y = h // 2
        for off, ln in [(-80,90),(-55,62),(-30,78),(0,105),(30,70),(55,84),(80,56)]:
            y = mid_y + off
            painter.drawLine(22,   y, 22+ln,   y)
            painter.drawLine(w-22, y, w-22-ln, y)

        painter.setPen(Qt.NoPen)
        for dpx, dpy in [
            (50, h//2-100),(74, h//2-76),(46, h//2+84),(86, h//2+104),
            (w-50,h//2-100),(w-74,h//2-76),(w-46,h//2+84),(w-86,h//2+104),
        ]:
            a2 = int((0.55 + 0.30 * math.sin(t + dpx * 0.05)) * 255)
            painter.setBrush(QBrush(QColor(0, 191, 255, a2)))
            painter.drawEllipse(QPointF(float(dpx), float(dpy)), 2.2, 2.2)

        ta   = int((0.35 + pulse * 0.14) * 255)
        pen3 = QPen(QColor(0, 210, 255, ta))
        pen3.setWidthF(0.6)
        painter.setPen(pen3)
        painter.drawLine(w//2 - 150, 34, w//2 + 150, 34)
        painter.setFont(QFont("Courier New", 8))
        painter.setPen(QColor(0, 210, 255, ta))
        painter.drawText(QPointF(float(w//2 - 42), 29.0), "SYSTEM ONLINE")

        painter.setPen(pen3)
        painter.drawLine(w//2 - 120, h-34, w//2 + 120, h-34)
        painter.setFont(QFont("Courier New", 8))
        painter.setPen(QColor(0, 210, 255, ta))
        painter.drawText(
            QPointF(float(w//2 - 90), float(h - 20)),
            "◈  JARVIS NEURAL CORE v4.1  ◈"
        )

        painter.end()

    def SpeechRecogText(self):
        messages = _safe_read(TempDirectoryPath('Status.data'))
        self.label.setText(messages)

    def load_icon(self, path, width=40, height=40):
        if not os.path.exists(path):
            # Create a placeholder colored circle if icon missing
            self.icon_label.setText("🎤")
            return
        pixmap     = QPixmap(path)
        new_pixmap = pixmap.scaled(width, height,
                                   Qt.KeepAspectRatio,
                                   Qt.SmoothTransformation)
        self.icon_label.setPixmap(new_pixmap)

    def toggle_icon(self, event=None):
        if self.toggled:
            self.load_icon(GraphicsDirectoryPath('Mic_on.png'),  40, 40)
            MicButtonInitialed()
        else:
            self.load_icon(GraphicsDirectoryPath('Mic_off.png'), 40, 40)
            MicButtonClosed()
        self.toggled = not self.toggled


# ─────────────────────────────────────────────
#  CHAT SECTION
# ─────────────────────────────────────────────
class ChatSection(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(-10, 40, 40, 100)
        layout.setSpacing(-100)

        self.chat_text_edit = QTextEdit()
        self.chat_text_edit.setReadOnly(True)
        self.chat_text_edit.setTextInteractionFlags(Qt.NoTextInteraction)
        self.chat_text_edit.setFrameStyle(QFrame.NoFrame)
        layout.addWidget(self.chat_text_edit)
        self.setStyleSheet("background-color: black;")
        layout.setSizeConstraint(QVBoxLayout.SetDefaultConstraint)
        layout.setStretch(1, 1)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))

        text_color = QColor(Qt.blue)
        text_color_text = QTextCharFormat()
        text_color_text.setForeground(text_color)
        self.chat_text_edit.setCurrentCharFormat(text_color_text)

        # GIF — only load if file exists
        self.gif_label = QLabel()
        self.gif_label.setStyleSheet("border: none;")
        gif_path = GraphicsDirectoryPath('Jarvis.gif')
        if os.path.exists(gif_path):
            movie = QMovie(gif_path)
            movie.setScaledSize(QSize(480, 270))
            self.gif_label.setAlignment(Qt.AlignRight | Qt.AlignBottom)
            self.gif_label.setMovie(movie)
            movie.start()
        else:
            self.gif_label.setText("")
        layout.addWidget(self.gif_label)

        self.label = QLabel("")
        self.label.setStyleSheet(
            "color: white; font-size:16px; margin-right: 195px;"
            "border: none; margin-top: -30px;")
        self.label.setAlignment(Qt.AlignRight)
        layout.addWidget(self.label)
        layout.setSpacing(-10)
        layout.addWidget(self.gif_label)

        font = QFont()
        font.setPointSize(13)
        self.chat_text_edit.setFont(font)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.loadMessages)
        self.timer.timeout.connect(self.SpeechRecogText)
        self.timer.start(5)

        self.chat_text_edit.viewport().installEventFilter(self)
        self.setStyleSheet("""
QScrollBar:vertical {
border: none; background: black; width: 10px; margin: 0px;
}
QScrollBar::handle:vertical {
background: white; min-height: 20px;
}
QScrollBar::add-line:vertical {
background: black; subcontrol-position: bottom;
subcontrol-origin: margin; height: 10px;
}
QScrollBar::sub-line:vertical {
background: black; subcontrol-position: top;
subcontrol-origin: margin; height: 10px;
}
QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {
border: none; background: none; color: none;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
background: none;
}
""")

    def loadMessages(self):
        global old_chat_message
        messages = _safe_read(TempDirectoryPath('Responses.data'))
        if not messages or len(messages) <= 1:
            return
        if str(old_chat_message) == str(messages):
            return
        self.addMessage(message=messages, color='White')
        old_chat_message = messages

    def SpeechRecogText(self):
        messages = _safe_read(TempDirectoryPath('Status.data'))
        self.label.setText(messages)

    def addMessage(self, message, color):
        cursor  = self.chat_text_edit.textCursor()
        format  = QTextCharFormat()
        formatm = QTextBlockFormat()
        formatm.setTopMargin(10)
        formatm.setLeftMargin(10)
        format.setForeground(QColor(color))
        cursor.setCharFormat(format)
        cursor.setBlockFormat(formatm)
        cursor.insertText(message + "\n")
        self.chat_text_edit.setTextCursor(cursor)


# ─────────────────────────────────────────────
#  MESSAGE SCREEN
# ─────────────────────────────────────────────
class MessageScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        desktop       = QApplication.desktop()
        screen_width  = desktop.screenGeometry().width()
        screen_height = desktop.screenGeometry().height()
        layout = QVBoxLayout()
        label  = QLabel("")
        layout.addWidget(label)
        chat_section = ChatSection()
        layout.addWidget(chat_section)
        self.setLayout(layout)
        self.setStyleSheet("background-color: black;")
        self.setFixedHeight(screen_height)
        self.setFixedWidth(screen_width)


# ─────────────────────────────────────────────
#  CUSTOM TOP BAR
# ─────────────────────────────────────────────
class CustomTopBar(QWidget):
    def __init__(self, parent, stacked_widget):
        super().__init__(parent)
        self.stacked_widget = stacked_widget
        self.current_screen = None
        self._drag_offset   = None
        self._fade_timer    = None
        self._fade_alpha    = 1.0
        self._fade_target   = 0
        self.initUI()

    def initUI(self):
        self.setFixedHeight(52)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(0)

        title_label = QLabel(f"  {str(Assistantname).upper()}  AI")
        title_label.setStyleSheet("""
            color: #00d4ff;
            font-size: 15px;
            font-family: 'Courier New', monospace;
            font-weight: bold;
            letter-spacing: 3px;
            background: transparent;
        """)

        def nav_btn(icon_path, text):
            btn = QPushButton(f"  {text}")
            icon_full = GraphicsDirectoryPath(icon_path)
            if os.path.exists(icon_full):
                btn.setIcon(QIcon(icon_full))
                btn.setIconSize(QSize(18, 18))
            btn.setFixedHeight(34)
            btn.setStyleSheet("""
                QPushButton {
                    color: #aaddff;
                    background: transparent;
                    border: 1px solid #1a3a5c;
                    border-radius: 6px;
                    font-family: 'Courier New', monospace;
                    font-size: 12px;
                    padding: 0 14px;
                    letter-spacing: 1px;
                }
                QPushButton:hover {
                    background: #0a2040;
                    border: 1px solid #00bfff;
                    color: #00d4ff;
                }
                QPushButton:pressed {
                    background: #001830;
                }
            """)
            return btn

        home_btn = nav_btn("Home.png",  "HOME")
        chat_btn = nav_btn("Chats.png", "CHAT")
        home_btn.clicked.connect(lambda: self._animated_switch(0))
        chat_btn.clicked.connect(lambda: self._animated_switch(1))

        def separator():
            f = QFrame()
            f.setFrameShape(QFrame.VLine)
            f.setFixedWidth(1)
            f.setStyleSheet("background: #1a3a5c; border: none;")
            return f

        def ctrl_btn(icon_path, hover_color="#0a2040"):
            btn = QPushButton()
            icon_full = GraphicsDirectoryPath(icon_path)
            if os.path.exists(icon_full):
                btn.setIcon(QIcon(icon_full))
                btn.setIconSize(QSize(16, 16))
            btn.setFixedSize(36, 36)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: 1px solid #1a3a5c;
                    border-radius: 6px;
                }}
                QPushButton:hover {{
                    background: {hover_color};
                    border: 1px solid #00bfff;
                }}
            """)
            return btn

        min_btn      = ctrl_btn("Minimize2.png")
        self.max_btn = ctrl_btn("Maximize.png")
        cls_btn      = ctrl_btn("Close.png", hover_color="#3a0000")

        self.max_icon = QIcon(GraphicsDirectoryPath('Maximize.png'))
        self.rst_icon = QIcon(GraphicsDirectoryPath('Minimize.png'))

        min_btn.clicked.connect(self.minimizeWindow)
        self.max_btn.clicked.connect(self.maximizeWindow)
        cls_btn.clicked.connect(self.closeWindow)

        layout.addWidget(title_label)
        layout.addSpacing(8)
        dot = QLabel("◈")
        dot.setStyleSheet("color: #00bfff; font-size: 10px; background: transparent;")
        layout.addWidget(dot)
        layout.addStretch(1)
        layout.addWidget(home_btn)
        layout.addSpacing(6)
        layout.addWidget(chat_btn)
        layout.addStretch(1)
        layout.addWidget(separator())
        layout.addSpacing(6)
        layout.addWidget(min_btn)
        layout.addSpacing(4)
        layout.addWidget(self.max_btn)
        layout.addSpacing(4)
        layout.addWidget(cls_btn)

        self.draggable = True

    def _animated_switch(self, target_index):
        if self.stacked_widget.currentIndex() == target_index:
            return
        if self._fade_timer and self._fade_timer.isActive():
            self._fade_timer.stop()
        self._fade_target = target_index
        self._fade_alpha  = 1.0
        cw = self.stacked_widget.currentWidget()
        self._out_eff = QGraphicsOpacityEffect()
        cw.setGraphicsEffect(self._out_eff)
        self._out_eff.setOpacity(1.0)
        self._fade_timer = QTimer(self)
        self._fade_timer.timeout.connect(self._do_fade_out)
        self._fade_timer.start(16)

    def _do_fade_out(self):
        self._fade_alpha -= 0.10
        if self._fade_alpha <= 0.0:
            self._fade_timer.stop()
            self.stacked_widget.currentWidget().setGraphicsEffect(None)
            self.stacked_widget.setCurrentIndex(self._fade_target)
            self._start_fade_in()
        else:
            self._out_eff.setOpacity(max(0.0, self._fade_alpha))

    def _start_fade_in(self):
        nw = self.stacked_widget.currentWidget()
        self._in_eff = QGraphicsOpacityEffect()
        nw.setGraphicsEffect(self._in_eff)
        self._in_eff.setOpacity(0.0)
        self._fade_alpha = 0.0
        self._fade_timer = QTimer(self)
        self._fade_timer.timeout.connect(self._do_fade_in)
        self._fade_timer.start(16)

    def _do_fade_in(self):
        self._fade_alpha += 0.10
        if self._fade_alpha >= 1.0:
            self._fade_timer.stop()
            self.stacked_widget.currentWidget().setGraphicsEffect(None)
        else:
            self._in_eff.setOpacity(min(1.0, self._fade_alpha))

    def paintEvent(self, event):
        painter = QPainter(self)
        grad = QLinearGradient(0, 0, self.width(), 0)
        grad.setColorAt(0,   QColor(2,  8, 18))
        grad.setColorAt(0.5, QColor(4, 14, 28))
        grad.setColorAt(1,   QColor(2,  8, 18))
        painter.fillRect(self.rect(), grad)
        painter.setPen(QPen(QColor(0, 180, 255, 80), 1))
        painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        super().paintEvent(event)

    def minimizeWindow(self):
        self.parent().showMinimized()

    def maximizeWindow(self):
        if self.parent().isMaximized():
            self.parent().showNormal()
            self.max_btn.setIcon(self.max_icon)
        else:
            self.parent().showMaximized()
            self.max_btn.setIcon(self.rst_icon)

    def closeWindow(self):
        self.parent().close()

    def mousePressEvent(self, event):
        if self.draggable:
            self._drag_offset = event.pos()

    def mouseMoveEvent(self, event):
        if self.draggable and self._drag_offset:
            self.parent().move(event.globalPos() - self._drag_offset)


# ─────────────────────────────────────────────
#  MAIN WINDOW
# ─────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.initUI()

    def initUI(self):
        desktop        = QApplication.desktop()
        screen_width   = desktop.screenGeometry().width()
        screen_height  = desktop.screenGeometry().height()
        stacked_widget = QStackedWidget(self)
        initial_screen = InitialScreen()
        message_screen = MessageScreen()
        stacked_widget.addWidget(initial_screen)
        stacked_widget.addWidget(message_screen)
        self.setGeometry(0, 0, screen_width, screen_height)
        self.setStyleSheet("background-color: black;")
        top_bar = CustomTopBar(self, stacked_widget)
        self.setMenuWidget(top_bar)
        self.setCentralWidget(stacked_widget)


def GraphicalUserInterface():
    app    = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    GraphicalUserInterface()
