from __future__ import annotations

import sys
from typing import Optional

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from puzzle import Puzzle
from imgur_client import ImagePickerDialog
from machine_art import MachineArtDialog
from waifu_client import WaifuPickerDialog


class BoardWidget(QWidget):
    def __init__(self, window: "MainWindow") -> None:
        super().__init__()
        self.window = window
        self.dragging = False
        self.setMinimumSize(420, 420)
        self.setMouseTracking(True)

    def tile_at(self, point: QPoint) -> int:
        side = min(self.width(), self.height())
        gap = self.window.cell_gap
        cell = (side - gap * (self.window.game.size - 1)) / self.window.game.size
        if cell <= 0:
            return -1
        board_size = cell * self.window.game.size + gap * (self.window.game.size - 1)
        left = (self.width() - board_size) / 2
        top = (self.height() - board_size) / 2
        x, y = point.x() - left, point.y() - top
        if x < 0 or y < 0 or x >= board_size or y >= board_size:
            return -1
        col = int(x / (cell + gap))
        row = int(y / (cell + gap))
        if col >= self.window.game.size or row >= self.window.game.size:
            return -1
        if x - col * (cell + gap) >= cell or y - row * (cell + gap) >= cell:
            return -1
        return row * self.window.game.size + col

    def paintEvent(self, event) -> None:
        from PySide6.QtGui import QPainter, QFont

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        game = self.window.game
        side = min(self.width(), self.height())
        gap = self.window.cell_gap
        cell = (side - gap * (game.size - 1)) / game.size
        board_size = cell * game.size + gap * (game.size - 1)
        left = (self.width() - board_size) / 2
        top = (self.height() - board_size) / 2
        for index, value in enumerate(game.tiles):
            row, col = divmod(index, game.size)
            rect = (left + col * (cell + gap), top + row * (cell + gap), cell, cell)
            if value == 0:
                continue
            if self.window.image_mode and self.window.source_image is not None:
                source = self.window.source_image
                source_cell_w = source.width() / game.size
                source_cell_h = source.height() / game.size
                original_index = value - 1
                sr, sc = divmod(original_index, game.size)
                # Calculate each edge independently so rounding cannot leave
                # gaps between source crops when dimensions are not divisible by the grid size.
                source_x0 = round(sc * source_cell_w)
                source_y0 = round(sr * source_cell_h)
                source_x1 = round((sc + 1) * source_cell_w)
                source_y1 = round((sr + 1) * source_cell_h)
                crop = source.copy(source_x0, source_y0,
                                   max(1, source_x1 - source_x0),
                                   max(1, source_y1 - source_y0))
                # Use shared rounded board edges instead of truncating each cell's
                # position and width independently; this prevents subpixel seams.
                x0 = round(left + col * (cell + gap))
                y0 = round(top + row * (cell + gap))
                x1 = round(left + col * (cell + gap) + cell)
                y1 = round(top + row * (cell + gap) + cell)
                inset = min(2, gap / 2)
                draw_x = round(x0 + inset)
                draw_y = round(y0 + inset)
                draw_size = max(1, round(min(x1 - x0, y1 - y0) - inset * 2))
                # Overlap by one pixel only when there is no configured gap,
                # covering antialiasing/rasterization seams between image tiles.
                overlap = 1 if gap == 0 else 0
                painter.drawPixmap(draw_x, draw_y, draw_size + overlap * 2,
                                   draw_size + overlap * 2, crop)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
            else:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor("#4b78c2"))
                inset = min(2, gap / 2)
                tile_size = max(1, int(cell - inset * 2))
                painter.drawRoundedRect(int(rect[0] + inset), int(rect[1] + inset), tile_size, tile_size, 8, 8)
                painter.setPen(Qt.GlobalColor.white)
                painter.setFont(QFont("Arial", max(12, int(cell / 3)), QFont.Weight.Bold))
                painter.drawText(int(rect[0]), int(rect[1]), int(cell), int(cell), Qt.AlignmentFlag.AlignCenter, str(value))
        painter.end()

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        index = self.tile_at(event.position().toPoint())
        if index == self.window.game.empty:
            self.dragging = True
            self.grabMouse()
        elif self.window.game.move(index):
            self.window.on_move()

    def mouseMoveEvent(self, event) -> None:
        if not self.dragging:
            return
        index = self.tile_at(event.position().toPoint())
        if index >= 0 and self.window.game.move(index):
            self.window.on_move()

    def mouseReleaseEvent(self, event) -> None:
        if self.dragging:
            self.dragging = False
            self.releaseMouse()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Пятнашки by VladZ")
        self.game = Puzzle(4)
        self.image_mode = False
        self.moves_made = False
        self.source_image: Optional[QPixmap] = None

        self.cell_gap = 0
        root = QWidget()
        layout = QVBoxLayout(root)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Размер:"))
        self.size_box = QSpinBox()
        self.size_box.setRange(2, 8)
        self.size_box.setValue(4)
        self.size_box.valueChanged.connect(self.change_size)
        controls.addWidget(self.size_box)
        controls.addWidget(QLabel("Интервал между клетками:"))
        self.gap_box = QSpinBox()
        self.gap_box.setRange(0, 30)
        self.gap_box.setSuffix(" px")
        self.gap_box.setValue(self.cell_gap)
        self.gap_box.valueChanged.connect(self.change_gap)
        controls.addWidget(self.gap_box)
        controls.addWidget(QLabel("Режим:"))
        self.mode_box = QComboBox()
        self.mode_box.addItems(["Числа", "Изображение", "Machine Art", "Waifu.im"])
        self.mode_box.currentIndexChanged.connect(self.change_mode)
        controls.addWidget(self.mode_box)
        self.image_button = QPushButton("Найти изображение Openverse…")
        self.image_button.clicked.connect(self.choose_image)
        self.image_button.setEnabled(False)
        controls.addWidget(self.image_button)
        self.shuffle_button = QPushButton("Перемешать")
        self.shuffle_button.clicked.connect(self.shuffle)
        controls.addWidget(self.shuffle_button)
        layout.addLayout(controls)
        self.board = BoardWidget(self)
        layout.addWidget(self.board, 1)
        self.status = QLabel("Кликните по соседней плитке или зажмите пустую клетку и ведите курсор.")
        layout.addWidget(self.status)
        self.setCentralWidget(root)
        self.resize(760, 820)
        self.shuffle()

    def refresh(self) -> None:
        self.board.update()
        if self.game.is_solved() and self.moves_made:
            self.moves_made = False
            self.status.setText("Победа! Поле собрано.")
            QMessageBox.information(self, "Message from Xi Pinpin", "Партия гордится вами!")
        elif not self.game.is_solved():
            self.status.setText("Игра продолжается.")

    def on_move(self) -> None:
        self.moves_made = True
        self.refresh()

    def change_size(self, size: int) -> None:
        self.game.set_size(size)
        self.shuffle()

    def change_gap(self, gap: int) -> None:
        self.cell_gap = gap
        self.board.update()

    def change_mode(self, index: int) -> None:
        if index == 2:
            self.image_mode = True
            self.image_button.setEnabled(False)
            self.open_machine_art()
            self.board.update()
            return
        if index == 3:
            self.image_mode = True
            self.image_button.setEnabled(False)
            self.open_waifu_picker()
            self.board.update()
            return
        self.image_mode = index == 1
        self.image_button.setEnabled(self.image_mode)
        self.board.update()

    def choose_image(self) -> None:
        dialog = ImagePickerDialog(self)
        dialog.image_selected.connect(self.set_image)
        dialog.exec()

    def open_waifu_picker(self) -> None:
        dialog = WaifuPickerDialog(self)
        dialog.image_selected.connect(self.set_image)
        if dialog.exec() != dialog.DialogCode.Accepted and self.mode_box.currentIndex() == 3:
            self.mode_box.blockSignals(True)
            self.mode_box.setCurrentIndex(0)
            self.mode_box.blockSignals(False)
            self.image_mode = False
            self.image_button.setEnabled(False)
            self.board.update()

    def open_machine_art(self) -> None:
        dialog = MachineArtDialog(self.game.size, self)
        if dialog.exec() == dialog.DialogCode.Accepted and dialog.result_image is not None:
            self.source_image = QPixmap.fromImage(dialog.result_image).scaled(
                800, 800, Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            self.image_mode = True
            self.status.setText("Создано изображение Machine Art.")
            self.shuffle()
        elif self.mode_box.currentIndex() == 2:
            self.mode_box.blockSignals(True)
            self.mode_box.setCurrentIndex(0)
            self.mode_box.blockSignals(False)
            self.image_mode = False
            self.image_button.setEnabled(False)
            self.board.update()

    def set_image(self, pixmap: QPixmap, image_id: str) -> None:
        if pixmap.isNull():
            QMessageBox.warning(self, "Ошибка", "Не удалось открыть изображение.")
            return
        self.source_image = pixmap.scaled(800, 800, Qt.AspectRatioMode.IgnoreAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation)
        self.status.setText(f"Изображение «{image_id}» загружено.")
        self.shuffle()

    def shuffle(self) -> None:
        self.moves_made = False
        self.game.shuffle()
        self.refresh()


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
