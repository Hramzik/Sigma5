from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from PySide6.QtCore import QObject, QRunnable, QSize, Qt, Signal, Slot, QThreadPool
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

API_ROOT = "https://api.waifu.im/images"
TAGS_API_ROOT = "https://api.waifu.im/tags"
# The API documentation also requires an X-Api-Key header.
API_KEY = "SeC5lklmjqqGpMre9qlJA8rGxuDVGyvfWQ3CE1I1c"


@dataclass(frozen=True)
class WaifuImage:
    image_id: str
    image_url: str
    preview_url: str


class WaifuError(Exception):
    pass


def _request_json(is_nsfw: bool, tag_slug: str | None = None) -> dict:
    query = [("IsNsfw", "True" if is_nsfw else "False"), ("PageSize", "30")]
    if tag_slug:
        query.append(("IncludedTags", tag_slug))
    params = urllib.parse.urlencode(query)
    request = urllib.request.Request(
        f"{API_ROOT}?{params}",
        headers={
            "Accept": "application/json",
            "X-Api-Key": API_KEY,
            "User-Agent": "SlidingPuzzle/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise WaifuError(f"Waifu.im вернул HTTP {exc.code}.") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise WaifuError(f"Не удалось связаться с Waifu.im: {exc}") from exc


def _request_tags_json() -> dict:
    params = urllib.parse.urlencode({"PageSize": 1000})
    request = urllib.request.Request(
        f"{TAGS_API_ROOT}?{params}",
        headers={"Accept": "application/json", "X-Api-Key": API_KEY, "User-Agent": "SlidingPuzzle/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise WaifuError(f"Waifu.im вернул HTTP {exc.code} при загрузке тегов.") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise WaifuError(f"Не удалось загрузить теги Waifu.im: {exc}") from exc


def parse_tags(data: dict) -> list[tuple[str, str]]:
    return [(str(item.get("name") or item["slug"]), str(item["slug"]))
            for item in data.get("items", []) if item.get("slug")]


def fetch_tags() -> list[tuple[str, str]]:
    return parse_tags(_request_tags_json())


def parse_images(data: dict) -> list[WaifuImage]:
    results = []
    for item in data.get("items", []):
        urls = item.get("的") or item.get("urls") or {}
        image_url = urls.get("full") or urls.get("large") or item.get("url")
        preview_url = urls.get("small") or urls.get("regular") or image_url
        if image_url and preview_url:
            results.append(WaifuImage(str(item.get("id", image_url)), image_url, preview_url))
    return results


def fetch_images(is_nsfw: bool, tag_slug: str | None = None) -> list[WaifuImage]:
    return parse_images(_request_json(is_nsfw, tag_slug))


def fetch_pixmap(url: str) -> QPixmap:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise WaifuError("Некорректная ссылка на изображение.")
    request = urllib.request.Request(url, headers={"User-Agent": "SlidingPuzzle/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            pixmap = QPixmap()
            if not pixmap.loadFromData(response.read()):
                raise WaifuError("Полученный файл не является поддерживаемым изображением.")
            return pixmap
    except urllib.error.HTTPError as exc:
        raise WaifuError(f"Waifu.im вернул HTTP {exc.code} при загрузке файла.") from exc
    except urllib.error.URLError as exc:
        raise WaifuError(f"Не удалось загрузить изображение: {exc}") from exc


class _Signals(QObject):
    done = Signal(object)
    failed = Signal(str)


class _Worker(QRunnable):
    def __init__(self, function) -> None:
        super().__init__()
        self.function = function
        self.signals = _Signals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.done.emit(self.function())
        except Exception as exc:
            self.signals.failed.emit(str(exc))


class WaifuPickerDialog(QDialog):
    image_selected = Signal(object, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Выбор изображения Waifu.im")
        self.resize(720, 580)
        self.threads = QThreadPool.globalInstance()
        self._workers = []
        self._request_version = 0
        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Контент:"))
        self.content_filter = QComboBox()
        self.content_filter.addItems(["SFW", "NSFW"])
        self.content_filter.currentIndexChanged.connect(self.load_images)
        bar.addWidget(self.content_filter)
        bar.addWidget(QLabel("Тег:"))
        self.tag_filter = QComboBox()
        self.tag_filter.setMinimumWidth(280)
        self.tag_filter.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.tag_filter.addItem("Any", "")
        self.tag_filter.currentIndexChanged.connect(self.load_images)
        bar.addWidget(self.tag_filter)
        bar.addStretch(1)
        layout.addLayout(bar)
        self.status = QLabel("Загрузка изображений…")
        layout.addWidget(self.status)
        self.list = QListWidget()
        self.list.setViewMode(QListWidget.ViewMode.IconMode)
        self.list.setIconSize(QSize(144, 120))
        self.list.setGridSize(QSize(170, 160))
        self.list.itemDoubleClicked.connect(self.select_item)
        layout.addWidget(self.list, 1)
        choose = QPushButton("Выбрать")
        choose.clicked.connect(self.select_current)
        layout.addWidget(choose)
        self._start(fetch_tags, self.show_tags)
        self.load_images()

    def _start(self, function, callback) -> None:
        worker = _Worker(function)
        self._workers.append(worker)
        worker.signals.done.connect(lambda result, task=worker: self._finish_worker(task))
        worker.signals.failed.connect(lambda _error, task=worker: self._finish_worker(task))
        worker.signals.done.connect(callback)
        worker.signals.failed.connect(self.show_error)
        self.threads.start(worker)

    def _finish_worker(self, worker) -> None:
        if worker in self._workers:
            self._workers.remove(worker)

    def load_images(self, _index: int = 0) -> None:
        self._request_version += 1
        version = self._request_version
        is_nsfw = self.content_filter.currentIndex() == 1
        tag_slug = self.tag_filter.currentData()
        self.list.clear()
        content_label = "NSFW" if is_nsfw else "SFW"
        tag_label = f" с тегом «{self.tag_filter.currentText()}»" if tag_slug else ""
        self.status.setText(f"Загрузка {content_label}-изображений{tag_label}…")
        self._start(lambda: (version, fetch_images(is_nsfw, tag_slug or None)), self.show_results)
    
    @Slot(object)
    def show_tags(self, tags: list[tuple[str, str]]) -> None:
        current_slug = self.tag_filter.currentData()
        self.tag_filter.blockSignals(True)
        self.tag_filter.clear()
        self.tag_filter.addItem("Any", "")
        for name, slug in tags:
            self.tag_filter.addItem(name, slug)
        self.tag_filter.setCurrentIndex(max(0, self.tag_filter.findData(current_slug)))
        self.tag_filter.blockSignals(False)

    @Slot(object)
    def show_results(self, result) -> None:
        version, images = result
        if version != self._request_version:
            return
        self.list.clear()
        if not images:
            self.status.setText("Изображения не найдены.")
            return
        self.status.setText(f"Найдено: {len(images)} изображений.")
        for image in images:
            item = QListWidgetItem(f"ID: {image.image_id}")
            item.setData(Qt.ItemDataRole.UserRole, image)
            self.list.addItem(item)
            self._load_thumbnail(item, image, version)

    def _load_thumbnail(self, item, image: WaifuImage, version: int) -> None:
        def apply(pixmap) -> None:
            if version != self._request_version or pixmap.isNull():
                return
            for index in range(self.list.count()):
                current = self.list.item(index)
                if current.data(Qt.ItemDataRole.UserRole) == image:
                    current.setIcon(QIcon(pixmap))
                    break

        self._start(lambda: fetch_pixmap(image.preview_url), apply)

    def select_item(self, item) -> None:
        image = item.data(Qt.ItemDataRole.UserRole)
        if image:
            self.status.setText("Загрузка выбранного изображения…")
            self._start(lambda: (fetch_pixmap(image.image_url), image.image_id), self.image_loaded)

    def select_current(self) -> None:
        item = self.list.currentItem()
        if item:
            self.select_item(item)
        else:
            QMessageBox.information(self, "Waifu.im", "Сначала выберите изображение.")

    @Slot(object)
    def image_loaded(self, result) -> None:
        pixmap, image_id = result
        self.image_selected.emit(pixmap, image_id)
        self.accept()

    @Slot(str)
    def show_error(self, message: str) -> None:
        self.status.setText("Не удалось загрузить изображения.")
        QMessageBox.warning(self, "Ошибка Waifu.im", message)
