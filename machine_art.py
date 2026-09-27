from __future__ import annotations

import math
import random
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

IMAGE_SIZE = 640
PREVIEW_SIZE = 480


@dataclass(frozen=True)
class Algorithm:
    key: str
    label: str


ALGORITHMS = (
    Algorithm("color_fields", "Цветовые поля"),
    Algorithm("waves", "Градиентные волны"),
    Algorithm("mosaic", "Геометрическая мозаика"),
    Algorithm("cells", "Клеточный узор"),
)


def _palette(rng: random.Random, count: int = 7) -> list[QColor]:
    hue = rng.randrange(360)
    return [QColor.fromHsv((hue + i * rng.randint(25, 65)) % 360,
                           rng.randint(130, 245), rng.randint(150, 255)) for i in range(count)]


def generate_art(algorithm: str, size: int = IMAGE_SIZE, seed: int | None = None) -> QImage:
    """Create a deterministic procedural artwork for a given algorithm and seed."""
    rng = random.Random(seed)
    image = QImage(size, size, QImage.Format.Format_RGB32)
    image.fill(QColor("#101522"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    colors = _palette(rng)

    if algorithm == "color_fields":
        painter.fillRect(0, 0, size, size, colors[0])
        for _ in range(18):
            color = rng.choice(colors)
            painter.setBrush(color)
            painter.setPen(QPen(color.lighter(125), rng.randint(2, 8)))
            x, y = rng.uniform(-size * .2, size * .8), rng.uniform(-size * .2, size * .8)
            w, h = rng.uniform(size * .12, size * .55), rng.uniform(size * .12, size * .55)
            painter.drawRoundedRect(QRectF(x, y, w, h), rng.uniform(10, 90), rng.uniform(10, 90))
    elif algorithm == "waves":
        for y in range(size):
            phase = y / size * math.tau * rng.uniform(1.5, 3.0)
            for x in range(size):
                value = (math.sin(x / size * math.tau * 2 + phase) +
                         math.sin(y / size * math.tau * 3 - x / size * 4) + 2) / 4
                color = colors[min(len(colors) - 1, int(value * len(colors)))]
                image.setPixelColor(x, y, color)
        painter.setPen(QPen(QColor(255, 255, 255, 90), max(1, size // 160)))
        for band in range(7):
            path = QPainterPath()
            for x in range(size + 1):
                y = size * (band + .5) / 7 + math.sin(x / size * math.tau * 2 + band) * size * .06
                path.lineTo(QPointF(x, y)) if x else path.moveTo(QPointF(x, y))
            painter.drawPath(path)
    elif algorithm == "mosaic":
        painter.fillRect(0, 0, size, size, colors[0])
        for _ in range(100):
            x, y = rng.randrange(size), rng.randrange(size)
            radius = rng.randint(size // 25, size // 7)
            color = rng.choice(colors)
            painter.setBrush(color)
            painter.setPen(QPen(color.lighter(135), max(1, size // 180)))
            shape = rng.randrange(3)
            if shape == 0:
                painter.drawEllipse(QPointF(x, y), radius, radius)
            elif shape == 1:
                painter.drawRect(QRectF(x - radius, y - radius, radius * 2, radius * 2))
            else:
                points = [QPointF(x + math.cos(i * math.tau / 6) * radius,
                                  y + math.sin(i * math.tau / 6) * radius) for i in range(6)]
                painter.drawPolygon(points)
    elif algorithm == "cells":
        phases = [(rng.uniform(0, size), rng.uniform(0, size), rng.uniform(size * .08, size * .3)) for _ in range(12)]
        for y in range(size):
            for x in range(size):
                field = sum(math.sin(math.hypot(x - cx, y - cy) / radius * 5) for cx, cy, radius in phases)
                color = colors[min(len(colors) - 1, max(0, int((field + 12) / 24 * len(colors))))]
                image.setPixelColor(x, y, color)
        painter.setPen(QPen(QColor(15, 20, 32, 110), max(1, size // 140)))
        for cx, cy, radius in phases:
            painter.drawEllipse(QPointF(cx, cy), radius * .55, radius * .55)
    else:
        painter.end()
        raise ValueError(f"Неизвестный алгоритм: {algorithm}")

    painter.end()
    return image


class MachineArtDialog(QDialog):
    def __init__(self, grid_size: int, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Machine Art — искусственное изображение")
        self.setModal(True)
        self.grid_size = grid_size
        self.result_image: QImage | None = None
        self.preview = QLabel("Создайте изображение")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(PREVIEW_SIZE, PREVIEW_SIZE)
        self.algorithm_box = QComboBox()
        for algorithm in ALGORITHMS:
            self.algorithm_box.addItem(algorithm.label, algorithm.key)
        self.algorithm_box.currentIndexChanged.connect(self.generate)
        self.status = QLabel("Выберите алгоритм и сгенерируйте искусственное изображение.")
        self.generate_button = QPushButton("Перегенерировать")
        self.generate_button.clicked.connect(self.generate)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel)
        self.apply_button = buttons.button(QDialogButtonBox.StandardButton.Apply)
        self.apply_button.setText("Применить")
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Алгоритм:"))
        controls.addWidget(self.algorithm_box, 1)
        layout.addLayout(controls)
        layout.addWidget(self.preview, 1)
        layout.addWidget(self.status)
        layout.addWidget(self.generate_button)
        layout.addWidget(buttons)
        self.resize(620, 720)
        self.generate()

    def generate(self) -> None:
        self.generate_button.setEnabled(False)
        self.apply_button.setEnabled(False)
        try:
            self.result_image = generate_art(self.algorithm_box.currentData())
            pixmap = QPixmap.fromImage(self.result_image).scaled(
                PREVIEW_SIZE, PREVIEW_SIZE, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            self.preview.setPixmap(pixmap)
            self.status.setText("Изображение создано.")
            self.apply_button.setEnabled(True)
        except Exception as exc:
            self.result_image = None
            self.preview.setText("Не удалось создать изображение")
            self.status.setText(f"Ошибка генерации: {exc}")
        finally:
            self.generate_button.setEnabled(True)

    def accept(self) -> None:
        if self.result_image is not None:
            super().accept()
