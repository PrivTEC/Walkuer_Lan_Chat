from __future__ import annotations

import hashlib
from pathlib import Path

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QPainter, QPainterPath, QPixmap

try:
    from PIL import Image, ImageDraw
    from PIL.ImageQt import ImageQt
except Exception:  # pragma: no cover - pillow missing
    Image = None
    ImageDraw = None
    ImageQt = None

try:
    import qrcode
except Exception:  # pragma: no cover - qrcode missing
    qrcode = None

from util.paths import avatar_cache_path


NEON_GREEN = QColor(57, 255, 20)


def _seed_color(seed: str) -> QColor:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    hue = int(digest[:6], 16) % 360
    color = QColor()
    color.setHsv(hue, 200, 220)
    return color


def _initials(name: str) -> str:
    name = (name or "?").strip()
    if not name:
        return "?"
    parts = [p for p in name.replace("_", " ").split(" ") if p]
    if len(parts) == 1:
        return parts[0][:1].upper()
    return (parts[0][:1] + parts[1][:1]).upper()


def round_pixmap(pixmap: QPixmap, size: int) -> QPixmap:
    scaled = pixmap.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    result = QPixmap(size, size)
    result.fill(Qt.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.Antialiasing, True)
    path = QPainterPath()
    path.addEllipse(QRectF(0, 0, size, size))
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, scaled)
    painter.end()
    return result


def generate_avatar_pixmap(size: int, name: str, seed: str) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setBrush(QBrush(_seed_color(seed)))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(0, 0, size, size)

    text = _initials(name)
    font = QFont("Bahnschrift", int(size * 0.36))
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(Qt.black)
    painter.drawText(pixmap.rect(), Qt.AlignCenter, text)
    painter.end()
    return pixmap


def load_avatar_pixmap(avatar_path: str, name: str, avatar_sha: str, size: int) -> QPixmap:
    if avatar_path:
        path = Path(avatar_path)
        if path.exists():
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                return round_pixmap(pixmap, size)
    if avatar_sha:
        cached = avatar_cache_path(avatar_sha)
        if cached.exists():
            pixmap = QPixmap(str(cached))
            if not pixmap.isNull():
                return round_pixmap(pixmap, size)
    seed = avatar_sha or name or "walkuer"
    return generate_avatar_pixmap(size, name, seed)


def app_icon(size: int = 256) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    pen_color = QColor(57, 255, 20)
    painter.setPen(pen_color)
    painter.setBrush(Qt.NoBrush)
    pen_width = max(2, int(size * 0.08))
    painter.setPen(pen_color)

    w = size * 0.72
    h = size * 0.62
    x0 = (size - w) / 2
    y0 = (size - h) / 2
    points = [
        (x0, y0),
        (x0 + w * 0.25, y0 + h),
        (x0 + w * 0.5, y0 + h * 0.35),
        (x0 + w * 0.75, y0 + h),
        (x0 + w, y0),
    ]

    painter.setPen(QColor(57, 255, 20))
    painter.setBrush(Qt.NoBrush)
    pen = painter.pen()
    pen.setWidth(pen_width)
    painter.setPen(pen)
    for idx in range(len(points) - 1):
        painter.drawLine(int(points[idx][0]), int(points[idx][1]), int(points[idx + 1][0]), int(points[idx + 1][1]))

    painter.end()
    return QIcon(pixmap)


def write_app_icon(path: str) -> None:
    if Image is None or ImageDraw is None:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    sizes = [16, 32, 48, 64, 128, 256]
    images = []
    for size in sizes:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 255))
        draw = ImageDraw.Draw(img)
        margin = int(size * 0.16)
        x0 = margin
        y0 = margin
        w = size - margin * 2
        h = size - margin * 2
        points = [
            (x0, y0),
            (x0 + w * 0.25, y0 + h),
            (x0 + w * 0.5, y0 + h * 0.35),
            (x0 + w * 0.75, y0 + h),
            (x0 + w, y0),
        ]
        line_width = max(2, int(size * 0.12))
        draw.line(points, fill=(57, 255, 20, 255), width=line_width, joint="curve")
        images.append(img)

    images[0].save(
        str(target),
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:],
    )


def generate_qr_pixmap(data: str, size: int = 120) -> QPixmap | None:
    if not data or qrcode is None or Image is None or ImageQt is None:
        return None
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=4,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    if size:
        img = img.resize((size, size), resample=Image.NEAREST)
    qimage = ImageQt(img)
    return QPixmap.fromImage(qimage)
