from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from PySide6.QtCore import QObject, QRunnable, Signal, Slot
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QLineEdit,
)

API_ROOT = "https://api.openverse.org/v1/images/"


@dataclass(frozen=True)
class ImageResult:
    image_id: str
    title: str
    thumbnail_url: str
    image_url: str


class OpenverseError(Exception):
    pass


def _request_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "SlidingPuzzle/1.0",
    })
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise OpenverseError(f"Openverse вернул HTTP {exc.code}.") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise OpenverseError(f"Не удалось связаться с Openverse: {exc}") from exc


def _image_items(data) -> list[ImageResult]:
    results: list[ImageResult] = []
    for item in data or []:
        image_url = item.get("url")
        thumbnail_url = item.get("thumbnail") or image_url
        if not image_url or not thumbnail_url:
            continue
        identifier = str(item.get("id") or image_url)
        title = (item.get("title") or "Изображение")
        results.append(ImageResult(identifier, title, thumbnail_url, image_url))
    return results


def fetch_image(image_url: str) -> QPixmap:
    parsed = urllib.parse.urlparse(image_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise OpenverseError("Некорректная ссылка на изображение.")
    try:
        request = urllib.request.Request(image_url, headers={"User-Agent": "SlidingPuzzle/1.0"})
        with urllib.request.urlopen(request, timeout=20) as response:
            pixmap = QPixmap()
            if not pixmap.loadFromData(response.read()):
                raise OpenverseError("Полученный файл не является поддерживаемым изображением.")
            return pixmap
    except urllib.error.HTTPError as exc:
        raise OpenverseError(f"Источник изображения вернул HTTP {exc.code}.") from exc
    except urllib.error.URLError as exc:
        raise OpenverseError(f"Не удалось загрузить изображение: {exc}") from exc


def search_images(term: str) -> list[ImageResult]:
    params = urllib.parse.urlencode({"q": term.strip(), "page_size": 20})
    payload = _request_json(f"{API_ROOT}?{params}")
    return _image_items(payload.get("results"))


def random_images(count: int = 9) -> list[ImageResult]:
    # Openverse search has no random endpoint; use a broad common query instead.
    results = search_images("nature")
    return results[:count]


class WorkerSignals(QObject):
    done = Signal(object)
    failed = Signal(str)


class Worker(QRunnable):
    def __init__(self, function) -> None:
        super().__init__()
        self.function = function
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.done.emit(self.function())
        except Exception as exc:
            self.signals.failed.emit(str(exc))


class ImagePickerDialog(QDialog):
    image_selected = Signal(object, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Поиск изображений Openverse")
        self.resize(720, 580)
        self.threads = __import__("PySide6.QtCore", fromlist=["QThreadPool"]).QThreadPool.globalInstance()
        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.query = QLineEdit()
        self.query.setPlaceholderText("Поиск по словам")
        self.query.returnPressed.connect(self.search)
        bar.addWidget(self.query, 1)
        search_button = QPushButton("Искать")
        search_button.clicked.connect(self.search)
        bar.addWidget(search_button)
        self.random_button = QPushButton("9 изображений")
        self.random_button.clicked.connect(self.load_random)
        bar.addWidget(self.random_button)
        layout.addLayout(bar)
        self.status = QLabel("Загружаю изображения…")
        layout.addWidget(self.status)
        self.list = QListWidget()
        self.list.setViewMode(QListWidget.ViewMode.IconMode)
        self.list.setIconSize(__import__("PySide6.QtCore", fromlist=["QSize"]).QSize(144, 120))
        self.list.setGridSize(__import__("PySide6.QtCore", fromlist=["QSize"]).QSize(170, 160))
        self.list.itemDoubleClicked.connect(self.select_item)
        layout.addWidget(self.list, 1)
        bottom = QHBoxLayout()
        choose_button = QPushButton("Выбрать")
        choose_button.clicked.connect(self.select_current)
        bottom.addWidget(choose_button)
        layout.addLayout(bottom)
        self.load_random()

    def _start(self, function, callback) -> None:
        self.status.setText("Загрузка…")
        worker = Worker(function)
        worker.signals.done.connect(callback)
        worker.signals.failed.connect(self.show_error)
        self.threads.start(worker)

    def load_random(self) -> None:
        self._start(random_images, self.show_results)

    def search(self) -> None:
        term = self.query.text().strip()
        if not term:
            self.status.setText("Введите слова для поиска.")
            return
        self._start(lambda: search_images(term), self.show_results)

    @Slot(object)
    def show_results(self, results) -> None:
        self.list.clear()
        if not results:
            self.status.setText("Изображения не найдены.")
            return
        self.status.setText(f"Найдено: {len(results)}. Дважды щёлкните по изображению.")
        for result in results:
            item = QListWidgetItem(result.title[:48])
            item.setData(256, result)
            self.list.addItem(item)
            self._load_thumbnail(item, result)

    def _load_thumbnail(self, item, result) -> None:
        item_key = result.image_id

        def download():
            request = urllib.request.Request(result.thumbnail_url, headers={"User-Agent": "SlidingPuzzle/1.0"})
            with urllib.request.urlopen(request, timeout=15) as response:
                pixmap = QPixmap()
                pixmap.loadFromData(response.read())
                return pixmap

        def apply_thumbnail(pixmap):
            # A result callback can arrive after the dialog is closed or results change.
            try:
                for index in range(self.list.count()):
                    current = self.list.item(index)
                    current_result = current.data(256)
                    if current_result and current_result.image_id == item_key:
                        current.setIcon(__import__("PySide6.QtGui", fromlist=["QIcon"]).QIcon(pixmap))
                        break
            except RuntimeError:
                # The dialog's Qt objects were destroyed before the queued callback ran.
                return

        worker = Worker(download)
        worker.signals.done.connect(apply_thumbnail)
        # Keep the runnable wrapper alive until its queued callbacks are delivered.
        self._thumbnail_workers = getattr(self, "_thumbnail_workers", [])
        self._thumbnail_workers.append(worker)
        worker.signals.done.connect(lambda _pixmap, task=worker: self._discard_thumbnail_worker(task))
        worker.signals.failed.connect(lambda _error, task=worker: self._discard_thumbnail_worker(task))
        self.threads.start(worker)

    def _discard_thumbnail_worker(self, worker) -> None:
        workers = getattr(self, "_thumbnail_workers", [])
        if worker in workers:
            workers.remove(worker)

    def select_item(self, item) -> None:
        result = item.data(256)
        if result:
            self._start(lambda: (fetch_image(result.image_url), result.title), self.image_loaded)

    def select_current(self) -> None:
        item = self.list.currentItem()
        if item:
            self.select_item(item)
        else:
            QMessageBox.information(self, "Openverse", "Сначала выберите изображение.")

    @Slot(object)
    def image_loaded(self, result) -> None:
        pixmap, title = result
        self.image_selected.emit(pixmap, title)
        self.accept()

    @Slot(str)
    def show_error(self, message: str) -> None:
        self.status.setText("Не удалось выполнить запрос.")
        QMessageBox.warning(self, "Ошибка Openverse", message)
