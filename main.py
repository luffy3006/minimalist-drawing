import os
import sys
import time
import math
import copy
import importlib.util
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Protocol

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QSlider, QLabel, QColorDialog, QFrame, QLineEdit, QButtonGroup,
    QFileDialog, QMessageBox
)
from PyQt6.QtGui import (
    QPainter, QPen, QColor, QPainterPath, QPixmap, QFont, QIcon, QImage,
    QTransform, QPainterPathStroker, QUndoStack, QUndoCommand, QFontMetrics
)
from PyQt6.QtCore import Qt, QPoint, QPointF, QSize, QSizeF, QRectF, QObject, pyqtSignal, QEvent, QSettings

# --- Robust Local Autocorrect Module Loader ---
autocorrect = None
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    local_autocorrect_path = os.path.join(script_dir, "autocorrect.py")
    if os.path.exists(local_autocorrect_path):
        spec = importlib.util.spec_from_file_location("local_autocorrect", local_autocorrect_path)
        if spec and spec.loader:
            autocorrect = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(autocorrect)

    if autocorrect is None or not hasattr(autocorrect, "recognize"):
        import autocorrect as pkg_autocorrect
        if hasattr(pkg_autocorrect, "recognize"):
            autocorrect = pkg_autocorrect
except Exception:
    autocorrect = None

if autocorrect is None or not hasattr(autocorrect, "recognize"):
    class DummyAutocorrect:
        @staticmethod
        def recognize(points):
            return None
    autocorrect = DummyAutocorrect()


# =============================================================================
# 0. Spatial Indexing: QuadTree
# =============================================================================

class QuadTree:
    """Fast 2D QuadTree spatial index for viewport culling and hit-testing."""
    def __init__(self, bounds: QRectF, capacity: int = 16, max_depth: int = 8, depth: int = 0):
        self.bounds = bounds
        self.capacity = capacity
        self.max_depth = max_depth
        self.depth = depth
        self.items: list['Item'] = []
        self.divided = False
        self.northwest: QuadTree | None = None
        self.northeast: QuadTree | None = None
        self.southwest: QuadTree | None = None
        self.southeast: QuadTree | None = None

    def _subdivide(self):
        x, y, w, h = self.bounds.x(), self.bounds.y(), self.bounds.width() / 2.0, self.bounds.height() / 2.0
        self.northwest = QuadTree(QRectF(x, y, w, h), self.capacity, self.max_depth, self.depth + 1)
        self.northeast = QuadTree(QRectF(x + w, y, w, h), self.capacity, self.max_depth, self.depth + 1)
        self.southwest = QuadTree(QRectF(x, y + h, w, h), self.capacity, self.max_depth, self.depth + 1)
        self.southeast = QuadTree(QRectF(x + w, y + h, w, h), self.capacity, self.max_depth, self.depth + 1)
        self.divided = True

    def insert(self, item: 'Item') -> bool:
        if not self.bounds.intersects(item.bounds()):
            return False

        if len(self.items) < self.capacity or self.depth >= self.max_depth:
            self.items.append(item)
            return True

        if not self.divided:
            self._subdivide()

        inserted = (
            self.northwest.insert(item) or
            self.northeast.insert(item) or
            self.southwest.insert(item) or
            self.southeast.insert(item)
        )
        if not inserted:
            self.items.append(item)
            inserted = True
        return inserted

    def query(self, search_rect: QRectF, found: list['Item'] | None = None) -> list['Item']:
        if found is None:
            found = []

        if not self.bounds.intersects(search_rect):
            return found

        for item in self.items:
            if search_rect.intersects(item.bounds()):
                if item not in found:
                    found.append(item)

        if self.divided:
            self.northwest.query(search_rect, found)
            self.northeast.query(search_rect, found)
            self.southwest.query(search_rect, found)
            self.southeast.query(search_rect, found)

        return found

    def clear(self):
        self.items.clear()
        if self.divided:
            if self.northwest: self.northwest.clear()
            if self.northeast: self.northeast.clear()
            if self.southwest: self.southwest.clear()
            if self.southeast: self.southeast.clear()
            self.divided = False


# =============================================================================
# 1. State Modeling
# =============================================================================

class Ink(Enum):
    DEFAULT = auto()


class EraserType(Enum):
    STROKE = auto()  # Removes entire stroke on hit
    PIXEL = auto()   # Erases directly like a brush stroke


@dataclass
class Style:
    color: QColor | Ink = Ink.DEFAULT
    width: float = 5.0
    opacity: float = 1.0


@dataclass
class StrokeItem:
    path: QPainterPath
    style: Style
    points: list[QPointF] = field(default_factory=list)
    raw_path: QPainterPath | None = None
    timestamp: float = field(default_factory=time.time)

    def bounds(self) -> QRectF:
        pad = max(self.style.width / 2.0, 2.0)
        b = self.path.boundingRect()
        if b.width() == 0: b.setWidth(1.0)
        if b.height() == 0: b.setHeight(1.0)
        return b.adjusted(-pad, -pad, pad, pad)

    def apply_transform(self, t: QTransform):
        self.path = t.map(self.path)
        if self.raw_path is not None:
            self.raw_path = t.map(self.raw_path)
        self.points = [t.map(pt) for pt in self.points]

    def clone(self) -> 'StrokeItem':
        return StrokeItem(
            path=QPainterPath(self.path),
            style=copy.deepcopy(self.style),
            points=[QPointF(pt) for pt in self.points],
            raw_path=QPainterPath(self.raw_path) if self.raw_path else None,
            timestamp=time.time()
        )


@dataclass
class EraseMaskItem:
    path: QPainterPath
    width: float
    timestamp: float = field(default_factory=time.time)

    def bounds(self) -> QRectF:
        pad = max(self.width / 2.0, 2.0)
        b = self.path.boundingRect()
        if b.width() == 0: b.setWidth(1.0)
        if b.height() == 0: b.setHeight(1.0)
        return b.adjusted(-pad, -pad, pad, pad)

    def apply_transform(self, t: QTransform):
        self.path = t.map(self.path)

    def clone(self) -> 'EraseMaskItem':
        return EraseMaskItem(
            path=QPainterPath(self.path),
            width=self.width,
            timestamp=time.time()
        )


@dataclass
class TextItem:
    text: str
    pos: QPointF
    font: QFont
    style: Style
    timestamp: float = field(default_factory=time.time)

    def bounds(self) -> QRectF:
        fm = QFontMetrics(self.font)
        w = fm.horizontalAdvance(self.text) + 20
        h = max(30.0, fm.height() * 1.4)
        return QRectF(self.pos.x(), self.pos.y(), w, h)

    def apply_transform(self, t: QTransform):
        self.pos = t.map(self.pos)
        scale = math.hypot(t.m11(), t.m12())
        if abs(scale - 1.0) > 0.01:
            new_size = max(6, int(self.font.pointSize() * scale))
            self.font.setPointSize(new_size)

    def clone(self) -> 'TextItem':
        return TextItem(
            text=self.text,
            pos=QPointF(self.pos),
            font=QFont(self.font),
            style=copy.deepcopy(self.style),
            timestamp=time.time()
        )


@dataclass
class ImageItem:
    image: QPixmap
    pos: QPointF
    size: QSize
    timestamp: float = field(default_factory=time.time)

    def bounds(self) -> QRectF:
        return QRectF(self.pos, QSizeF(self.size))

    def apply_transform(self, t: QTransform):
        self.pos = t.map(self.pos)
        sx = math.hypot(t.m11(), t.m12())
        sy = math.hypot(t.m21(), t.m22())
        new_w = max(5, int(self.size.width() * sx))
        new_h = max(5, int(self.size.height() * sy))
        self.size = QSize(new_w, new_h)

    def clone(self) -> 'ImageItem':
        return ImageItem(
            image=QPixmap(self.image),
            pos=QPointF(self.pos),
            size=QSize(self.size),
            timestamp=time.time()
        )


Item = StrokeItem | EraseMaskItem | TextItem | ImageItem


# =============================================================================
# 2. Document & Undo Commands
# =============================================================================

class AddItemCommand(QUndoCommand):
    def __init__(self, doc: 'Document', item: Item):
        super().__init__("Draw")
        self.doc = doc
        self.item = item

    def redo(self):
        self.doc.items.append(self.item)
        self.doc.rebuild_spatial_index()
        self.doc.invalidated.emit()

    def undo(self):
        if self.doc.items and self.doc.items[-1] is self.item:
            self.doc.items.pop()
        elif self.item in self.doc.items:
            self.doc.items.remove(self.item)
        self.doc.rebuild_spatial_index()
        self.doc.invalidated.emit()


class PasteItemsCommand(QUndoCommand):
    def __init__(self, doc: 'Document', items: list[Item]):
        super().__init__("Paste")
        self.doc = doc
        self.items = items

    def redo(self):
        for item in self.items:
            self.doc.items.append(item)
        self.doc.rebuild_spatial_index()
        self.doc.invalidated.emit()

    def undo(self):
        for item in self.items:
            if item in self.doc.items:
                self.doc.items.remove(item)
        self.doc.rebuild_spatial_index()
        self.doc.invalidated.emit()


class RemoveItemCommand(QUndoCommand):
    def __init__(self, doc: 'Document', item: Item):
        super().__init__("Erase")
        self.doc = doc
        self.item = item
        self.index = doc.items.index(item) if item in doc.items else len(doc.items)

    def redo(self):
        if self.item in self.doc.items:
            self.doc.items.remove(self.item)
            self.doc.rebuild_spatial_index()
            self.doc.invalidated.emit()

    def undo(self):
        idx = min(self.index, len(self.doc.items))
        self.doc.items.insert(idx, self.item)
        self.doc.rebuild_spatial_index()
        self.doc.invalidated.emit()


class TransformItemsCommand(QUndoCommand):
    def __init__(self, doc: 'Document', items: list[Item], forward_tx: QTransform, inverse_tx: QTransform):
        super().__init__("Transform Selection")
        self.doc = doc
        self.items = list(items)
        self.forward_tx = forward_tx
        self.inverse_tx = inverse_tx

    def redo(self):
        for item in self.items:
            item.apply_transform(self.forward_tx)
        self.doc.rebuild_spatial_index()
        self.doc.invalidated.emit()

    def undo(self):
        for item in self.items:
            item.apply_transform(self.inverse_tx)
        self.doc.rebuild_spatial_index()
        self.doc.invalidated.emit()


class ClearCommand(QUndoCommand):
    def __init__(self, doc: 'Document'):
        super().__init__("Clear Canvas")
        self.doc = doc
        self.saved_items = list(doc.items)

    def redo(self):
        self.doc.items.clear()
        self.doc.spatial_index.clear()
        self.doc.invalidated.emit()

    def undo(self):
        self.doc.items = list(self.saved_items)
        self.doc.rebuild_spatial_index()
        self.doc.invalidated.emit()


class AutocorrectStrokeCommand(QUndoCommand):
    def __init__(self, doc: 'Document', item: 'StrokeItem', new_path: QPainterPath):
        super().__init__("Autocorrect Shape")
        self.doc = doc
        self.item = item
        self.old_path = item.path
        self.new_path = new_path

    def redo(self):
        self.item.path = self.new_path
        self.doc.rebuild_spatial_index()
        self.doc.invalidated.emit()

    def undo(self):
        self.item.path = self.old_path
        self.doc.rebuild_spatial_index()
        self.doc.invalidated.emit()


class Document(QObject):
    invalidated = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.items: list[Item] = []
        self.undo_stack = QUndoStack(self)
        self.spatial_index = QuadTree(QRectF(-100000, -100000, 200000, 200000))

    def rebuild_spatial_index(self):
        self.spatial_index.clear()
        for item in list(self.items):
            self.spatial_index.insert(item)

    def add_item(self, item: Item):
        self.undo_stack.push(AddItemCommand(self, item))

    def paste_items(self, items: list[Item]):
        self.undo_stack.push(PasteItemsCommand(self, items))

    def remove_item(self, item: Item):
        self.undo_stack.push(RemoveItemCommand(self, item))

    def transform_items(self, items: list[Item], fwd: QTransform, inv: QTransform):
        self.undo_stack.push(TransformItemsCommand(self, items, fwd, inv))

    def autocorrect_stroke(self, item: 'StrokeItem', new_path: QPainterPath):
        self.undo_stack.push(AutocorrectStrokeCommand(self, item, new_path))

    def clear(self):
        if self.items:
            self.undo_stack.push(ClearCommand(self))


# =============================================================================
# 3. Tool Implementations
# =============================================================================

class Tool(Protocol):
    cursor: Qt.CursorShape
    def press(self, canvas: 'DrawingCanvas', pt: QPointF, event) -> None: ...
    def move(self, canvas: 'DrawingCanvas', pt: QPointF, event) -> None: ...
    def release(self, canvas: 'DrawingCanvas', pt: QPointF, event) -> Item | None: ...
    def paint_preview(self, painter: QPainter, canvas: 'DrawingCanvas') -> None: ...


class PenTool:
    cursor = Qt.CursorShape.CrossCursor

    def __init__(self):
        self.current_path: QPainterPath | None = None
        self.points: list[QPointF] = []
        self.last_point: QPointF | None = None

    def press(self, canvas: 'DrawingCanvas', pt: QPointF, event) -> None:
        self.current_path = QPainterPath()
        self.current_path.moveTo(pt)
        self.points = [pt]
        self.last_point = pt

    def move(self, canvas: 'DrawingCanvas', pt: QPointF, event) -> None:
        if self.current_path is not None and self.last_point is not None:
            mid_point = QPointF(
                (self.last_point.x() + pt.x()) / 2.0,
                (self.last_point.y() + pt.y()) / 2.0
            )
            self.current_path.quadTo(self.last_point, mid_point)
            self.last_point = pt
            self.points.append(pt)

    def release(self, canvas: 'DrawingCanvas', pt: QPointF, event) -> Item | None:
        if self.current_path is not None:
            self.current_path.lineTo(pt)
            self.points.append(pt)

            final_path = QPainterPath(self.current_path)
            try:
                rec_path = autocorrect.recognize(self.points)
                if rec_path is not None and isinstance(rec_path, QPainterPath):
                    final_path = rec_path
            except Exception:
                pass

            style = Style(
                color=canvas.current_color,
                width=canvas.current_width * canvas.stylus_pressure,
                opacity=1.0
            )
            stroke = StrokeItem(
                path=final_path,
                style=style,
                points=list(self.points),
                raw_path=QPainterPath(self.current_path),
                timestamp=time.time()
            )
            self.current_path = None
            self.points = []
            self.last_point = None
            return stroke
        return None

    def paint_preview(self, painter: QPainter, canvas: 'DrawingCanvas') -> None:
        if self.current_path is not None:
            color = canvas.get_display_color(canvas.current_color)
            pen = QPen(
                color, canvas.current_width * canvas.stylus_pressure,
                Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin
            )
            painter.setPen(pen)
            painter.drawPath(self.current_path)


class HighlighterTool:
    cursor = Qt.CursorShape.CrossCursor

    def __init__(self):
        self.current_path: QPainterPath | None = None
        self.points: list[QPointF] = []
        self.last_point: QPointF | None = None

    def press(self, canvas: 'DrawingCanvas', pt: QPointF, event) -> None:
        self.current_path = QPainterPath()
        self.current_path.moveTo(pt)
        self.points = [pt]
        self.last_point = pt

    def move(self, canvas: 'DrawingCanvas', pt: QPointF, event) -> None:
        if self.current_path is not None and self.last_point is not None:
            mid_point = QPointF(
                (self.last_point.x() + pt.x()) / 2.0,
                (self.last_point.y() + pt.y()) / 2.0
            )
            self.current_path.quadTo(self.last_point, mid_point)
            self.last_point = pt
            self.points.append(pt)

    def release(self, canvas: 'DrawingCanvas', pt: QPointF, event) -> Item | None:
        if self.current_path is not None:
            self.current_path.lineTo(pt)
            self.points.append(pt)

            final_path = QPainterPath(self.current_path)
            try:
                rec_path = autocorrect.recognize(self.points)
                if rec_path is not None and isinstance(rec_path, QPainterPath):
                    final_path = rec_path
            except Exception:
                pass

            style = Style(
                color=canvas.current_color if canvas.current_color != Ink.DEFAULT else QColor("#FFEB3B"),
                width=max(20.0, canvas.current_width * 3.5),
                opacity=0.35
            )
            stroke = StrokeItem(
                path=final_path,
                style=style,
                points=list(self.points),
                raw_path=QPainterPath(self.current_path),
                timestamp=time.time()
            )
            self.current_path = None
            self.points = []
            self.last_point = None
            return stroke
        return None

    def paint_preview(self, painter: QPainter, canvas: 'DrawingCanvas') -> None:
        if self.current_path is not None:
            color = canvas.get_display_color(canvas.current_color if canvas.current_color != Ink.DEFAULT else QColor("#FFEB3B"))
            color = QColor(color)
            color.setAlphaF(0.35)
            pen = QPen(
                color, max(20.0, canvas.current_width * 3.5),
                Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap, Qt.PenJoinStyle.RoundJoin
            )
            painter.setPen(pen)
            painter.drawPath(self.current_path)


class EraserTool:
    cursor = Qt.CursorShape.CrossCursor

    def __init__(self):
        self.current_pos: QPointF | None = None
        self.current_path: QPainterPath | None = None
        self.last_point: QPointF | None = None

    def _erase_at(self, canvas: 'DrawingCanvas', pt: QPointF) -> None:
        radius = max(8.0, canvas.current_width * 1.8)
        eraser_rect = QRectF(pt.x() - radius, pt.y() - radius, radius * 2, radius * 2)
        stroker = QPainterPathStroker()

        candidates = canvas.doc.spatial_index.query(eraser_rect)

        for item in list(candidates):
            if isinstance(item, StrokeItem):
                stroker.setWidth(max(item.style.width, 10.0))
                stroke_outline = stroker.createStroke(item.path)
                if stroke_outline.intersects(eraser_rect):
                    canvas.doc.remove_item(item)
            elif isinstance(item, (TextItem, ImageItem)):
                if item.bounds().intersects(eraser_rect):
                    canvas.doc.remove_item(item)

    def press(self, canvas: 'DrawingCanvas', pt: QPointF, event) -> None:
        self.current_pos = pt
        if canvas.eraser_type == EraserType.STROKE:
            self._erase_at(canvas, pt)
        else:
            self.current_path = QPainterPath()
            self.current_path.moveTo(pt)
            self.last_point = pt

    def move(self, canvas: 'DrawingCanvas', pt: QPointF, event) -> None:
        self.current_pos = pt
        if canvas.eraser_type == EraserType.STROKE:
            self._erase_at(canvas, pt)
        elif self.current_path is not None and self.last_point is not None:
            mid_point = QPointF(
                (self.last_point.x() + pt.x()) / 2.0,
                (self.last_point.y() + pt.y()) / 2.0
            )
            self.current_path.quadTo(self.last_point, mid_point)
            self.last_point = pt

    def release(self, canvas: 'DrawingCanvas', pt: QPointF, event) -> Item | None:
        self.current_pos = None
        if canvas.eraser_type == EraserType.PIXEL and self.current_path is not None:
            self.current_path.lineTo(pt)
            mask_item = EraseMaskItem(
                path=QPainterPath(self.current_path),
                width=max(8.0, canvas.current_width * 1.8) * 2.0 * canvas.stylus_pressure,
                timestamp=time.time()
            )
            self.current_path = None
            self.last_point = None
            return mask_item

        self.current_path = None
        self.last_point = None
        return None

    def paint_preview(self, painter: QPainter, canvas: 'DrawingCanvas') -> None:
        radius = max(8.0, canvas.current_width * 1.8)
        if canvas.eraser_type == EraserType.PIXEL and self.current_path is not None:
            pen = QPen(
                QColor(255, 100, 100, 160),
                radius * 2.0 * canvas.stylus_pressure,
                Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin
            )
            painter.setPen(pen)
            painter.drawPath(self.current_path)

        if self.current_pos is not None:
            painter.setPen(QPen(QColor(180, 180, 180, 180), 1.5, Qt.PenStyle.DashLine))
            painter.setBrush(QColor(240, 240, 240, 60))
            painter.drawEllipse(self.current_pos, radius, radius)


class LassoTool:
    cursor = Qt.CursorShape.ArrowCursor
    HANDLE_SIZE = 8.0

    def __init__(self):
        self.selected_items: list[Item] = []
        self.lasso_path: QPainterPath | None = None
        self.mode: str = "none"
        self.active_handle: str | None = None
        self.press_pt = QPointF(0, 0)
        self.initial_bounds = QRectF()
        self.total_transform = QTransform()

    def get_selection_bounds(self) -> QRectF:
        if not self.selected_items:
            return QRectF()
        b = QRectF()
        for item in self.selected_items:
            b = item.bounds() if b.isNull() else b.united(item.bounds())
        return b

    def _get_handles(self, rect: QRectF) -> dict[str, QRectF]:
        s = self.HANDLE_SIZE
        hs = s / 2.0
        return {
            "top_left": QRectF(rect.left() - hs, rect.top() - hs, s, s),
            "top": QRectF(rect.center().x() - hs, rect.top() - hs, s, s),
            "top_right": QRectF(rect.right() - hs, rect.top() - hs, s, s),
            "right": QRectF(rect.right() - hs, rect.center().y() - hs, s, s),
            "bottom_right": QRectF(rect.right() - hs, rect.bottom() - hs, s, s),
            "bottom": QRectF(rect.center().x() - hs, rect.bottom() - hs, s, s),
            "bottom_left": QRectF(rect.left() - hs, rect.bottom() - hs, s, s),
            "left": QRectF(rect.left() - hs, rect.center().y() - hs, s, s),
        }

    def hit_test_handles(self, pt: QPointF) -> str | None:
        if not self.selected_items:
            return None
        rect = self.get_selection_bounds()
        handles = self._get_handles(rect)
        for h_name, h_rect in handles.items():
            if h_rect.adjusted(-3, -3, 3, 3).contains(pt):
                return h_name
        return None

    def hover_move(self, canvas: 'DrawingCanvas', pt: QPointF) -> None:
        if self.selected_items:
            h = self.hit_test_handles(pt)
            if h in ("top_left", "bottom_right"):
                canvas.setCursor(Qt.CursorShape.SizeFDiagCursor)
                return
            elif h in ("top_right", "bottom_left"):
                canvas.setCursor(Qt.CursorShape.SizeBDiagCursor)
                return
            elif h in ("top", "bottom"):
                canvas.setCursor(Qt.CursorShape.SizeVerCursor)
                return
            elif h in ("left", "right"):
                canvas.setCursor(Qt.CursorShape.SizeHorCursor)
                return
            elif self.get_selection_bounds().contains(pt):
                canvas.setCursor(Qt.CursorShape.SizeAllCursor)
                return
        canvas.setCursor(Qt.CursorShape.ArrowCursor)

    def press(self, canvas: 'DrawingCanvas', pt: QPointF, event) -> None:
        self.press_pt = pt
        self.total_transform = QTransform()

        if self.selected_items:
            h = self.hit_test_handles(pt)
            if h:
                self.mode = "resize"
                self.active_handle = h
                self.initial_bounds = self.get_selection_bounds()
                return

            box = self.get_selection_bounds()
            if box.contains(pt):
                self.mode = "move"
                self.initial_bounds = box
                return

        self.selected_items.clear()
        self.mode = "drawing_lasso"
        self.lasso_path = QPainterPath()
        self.lasso_path.moveTo(pt)

    def move(self, canvas: 'DrawingCanvas', pt: QPointF, event) -> None:
        if self.mode == "drawing_lasso":
            if self.lasso_path is not None:
                self.lasso_path.lineTo(pt)
                canvas.update()

        elif self.mode == "move":
            dx = pt.x() - self.press_pt.x()
            dy = pt.y() - self.press_pt.y()
            step_tx = QTransform.fromTranslate(dx, dy)
            for item in self.selected_items:
                item.apply_transform(step_tx)
            self.total_transform = self.total_transform * step_tx
            self.press_pt = pt
            canvas.update()

        elif self.mode == "resize" and self.active_handle:
            rect = QRectF(self.initial_bounds)
            left, top, right, bottom = rect.left(), rect.top(), rect.right(), rect.bottom()

            if "left" in self.active_handle:
                left = min(pt.x(), right - 10)
            if "right" in self.active_handle:
                right = max(pt.x(), left + 10)
            if "top" in self.active_handle:
                top = min(pt.y(), bottom - 10)
            if "bottom" in self.active_handle:
                bottom = max(pt.y(), top + 10)

            cur_b = self.get_selection_bounds()
            if cur_b.width() > 0 and cur_b.height() > 0:
                new_w = right - left
                new_h = bottom - top
                sx = new_w / cur_b.width()
                sy = new_h / cur_b.height()

                step_tx = QTransform()
                step_tx.translate(cur_b.left(), cur_b.top())
                step_tx.scale(sx, sy)
                step_tx.translate(-cur_b.left(), -cur_b.top())
                step_tx.translate(left - cur_b.left(), top - cur_b.top())

                for item in self.selected_items:
                    item.apply_transform(step_tx)
                self.total_transform = self.total_transform * step_tx
                canvas.update()

    def release(self, canvas: 'DrawingCanvas', pt: QPointF, event) -> Item | None:
        if self.mode == "drawing_lasso":
            if self.lasso_path is not None:
                self.lasso_path.closeSubpath()
                stroker = QPainterPathStroker()

                candidates = canvas.doc.spatial_index.query(self.lasso_path.boundingRect())

                for item in candidates:
                    if isinstance(item, StrokeItem):
                        stroker.setWidth(max(item.style.width, 10.0))
                        if self.lasso_path.intersects(item.path) or self.lasso_path.contains(item.bounds()):
                            self.selected_items.append(item)
                    elif isinstance(item, (TextItem, ImageItem)):
                        if self.lasso_path.intersects(item.bounds()) or self.lasso_path.contains(item.bounds()):
                            self.selected_items.append(item)

                self.lasso_path = None

        elif self.mode in ("move", "resize") and self.selected_items:
            if not self.total_transform.isIdentity():
                inv, ok = self.total_transform.inverted()
                if ok:
                    canvas.doc.transform_items(self.selected_items, self.total_transform, inv)

        self.mode = "none"
        self.active_handle = None
        self.total_transform = QTransform()
        canvas.update()
        return None

    def paint_preview(self, painter: QPainter, canvas: 'DrawingCanvas') -> None:
        if self.lasso_path is not None:
            pen = QPen(QColor("#4c8dff"), 1.4 / canvas.zoom, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(QColor(76, 141, 255, 30))
            painter.drawPath(self.lasso_path)

        if self.selected_items:
            rect = self.get_selection_bounds()
            pen = QPen(QColor("#4c8dff"), 1.2 / canvas.zoom, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)

            painter.setPen(QPen(QColor("#ffffff"), 1.0 / canvas.zoom))
            painter.setBrush(QColor("#4c8dff"))
            s = self.HANDLE_SIZE / canvas.zoom
            for h_rect in self._get_handles(rect).values():
                adj_rect = QRectF(h_rect.center().x() - s / 2, h_rect.center().y() - s / 2, s, s)
                painter.drawRect(adj_rect)


# =============================================================================
# 4. Icon Helper
# =============================================================================

def make_icon(kind: str, size: int = 18, color: QColor | None = None) -> QIcon:
    color = color or QColor("#e4e4e7")
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(color, max(1.4, size * 0.1), Qt.PenStyle.SolidLine,
               Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    m = size * 0.2

    if kind == "lasso":
        pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen)
        loop = QPainterPath()
        loop.addEllipse(QRectF(size * 0.18, size * 0.18, size * 0.64, size * 0.55))
        p.drawPath(loop)
        pen.setStyle(Qt.PenStyle.SolidLine)
        p.setPen(pen)
        p.drawLine(QPointF(size * 0.65, size * 0.68), QPointF(size * 0.85, size * 0.88))

    elif kind == "pen":
        p.drawLine(QPointF(m, size - m), QPointF(size - m * 1.1, m * 1.1))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        nib = QPainterPath()
        nib.moveTo(size - m * 1.6, m * 1.6)
        nib.lineTo(size - m * 0.5, m * 0.4)
        nib.lineTo(size - m * 0.3, m * 1.1)
        nib.closeSubpath()
        p.drawPath(nib)

    elif kind == "highlighter":
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.save()
        p.translate(size / 2, size / 2)
        p.rotate(-45)
        p.drawRoundedRect(QRectF(-size * 0.34, -size * 0.15, size * 0.68, size * 0.30), 3, 3)
        p.restore()

    elif kind == "eraser":
        body = QRectF(size * 0.24, size * 0.36, size * 0.52, size * 0.4)
        p.setBrush(color)
        p.setPen(QPen(color, 1))
        p.drawRoundedRect(body, 4, 4)
        p.setPen(QPen(QColor(0, 0, 0, 90), 1.2))
        p.drawLine(QPointF(size * 0.24, size * 0.5), QPointF(size * 0.76, size * 0.5))

    elif kind == "sun":
        r = size * 0.16
        cx, cy = size / 2, size / 2
        p.setBrush(color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), r, r)
        p.setPen(pen)
        for ang in range(0, 360, 45):
            rad = math.radians(ang)
            x1, y1 = cx + math.cos(rad) * r * 1.7, cy + math.sin(rad) * r * 1.7
            x2, y2 = cx + math.cos(rad) * r * 2.6, cy + math.sin(rad) * r * 2.6
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    elif kind == "moon":
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        full = QPainterPath()
        full.addEllipse(QRectF(m * 0.7, m * 0.5, size - 1.3 * m, size - 1.3 * m))
        cut = QPainterPath()
        cut.addEllipse(QRectF(m * 1.6, m * 0.1, size - 1.3 * m, size - 1.3 * m))
        p.drawPath(full.subtracted(cut))

    elif kind == "trash":
        p.drawLine(QPointF(m * 0.8, size * 0.3), QPointF(size - m * 0.8, size * 0.3))
        p.drawLine(QPointF(size * 0.38, size * 0.3), QPointF(size * 0.4, m * 0.6))
        p.drawLine(QPointF(size * 0.62, size * 0.3), QPointF(size * 0.6, m * 0.6))
        p.drawLine(QPointF(size * 0.4, m * 0.6), QPointF(size * 0.6, m * 0.6))
        p.drawRoundedRect(QRectF(size * 0.28, size * 0.3, size * 0.44, size * 0.54), 2, 2)
        p.drawLine(QPointF(size * 0.4, size * 0.42), QPointF(size * 0.4, size * 0.74))
        p.drawLine(QPointF(size * 0.6, size * 0.42), QPointF(size * 0.6, size * 0.74))

    elif kind == "open":
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        tab = QRectF(m * 0.6, size * 0.22, size * 0.34, size * 0.14)
        p.drawRoundedRect(tab, 1, 1)
        body = QRectF(m * 0.6, size * 0.34, size - 1.2 * m, size * 0.46)
        p.drawRoundedRect(body, 2, 2)

    elif kind == "save":
        outer = QRectF(m * 0.55, m * 0.5, size - 1.1 * m, size - 1.0 * m)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawRoundedRect(outer, 2, 2)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        notch = QRectF(outer.right() - size * 0.24, outer.top(), size * 0.24, size * 0.24)
        p.drawRect(notch)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        label = QRectF(outer.left() + size * 0.14, outer.bottom() - size * 0.32,
                        outer.width() - size * 0.28, size * 0.22)
        p.setBrush(QColor(0, 0, 0, 130))
        p.drawRoundedRect(label, 1, 1)

    p.end()
    return QIcon(pm)


# =============================================================================
# 5. Adaptive Left Menu & Toolbar Controls
# =============================================================================

class ColorSwatch(QPushButton):
    ACCENT = QColor("#4c8dff")

    def __init__(self, color: QColor | None, tooltip: str, parent=None, is_auto: bool = False):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(24, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tooltip)
        self.setStyleSheet("background: transparent; border: none;")
        self._color = color
        self.is_auto = is_auto

    def set_color(self, color: QColor | None):
        self._color = color
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(3, 3, self.width() - 6, self.height() - 6)

        if self.is_auto:
            p.setPen(QPen(QColor("#5a5a62"), 1))
            p.setBrush(QColor("#f5f5f5"))
            p.drawEllipse(rect)
            half = QPainterPath()
            half.moveTo(rect.center().x(), rect.top())
            half.arcTo(rect, 90, 180)
            half.closeSubpath()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#1c1c1e"))
            p.drawPath(half)
        elif self._color is None:
            p.setPen(QPen(QColor("#8a8a92"), 1.4, Qt.PenStyle.DashLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(rect)
            cx, cy = rect.center().x(), rect.center().y()
            p.setPen(QPen(QColor("#c8c8cf"), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(cx - 4, cy), QPointF(cx + 4, cy))
            p.drawLine(QPointF(cx, cy - 4), QPointF(cx, cy + 4))
        else:
            p.setPen(QPen(QColor(0, 0, 0, 70), 1))
            p.setBrush(self._color)
            p.drawEllipse(rect)

        if self.isChecked():
            p.setPen(QPen(self.ACCENT, 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(rect.adjusted(-3, -3, 3, 3))

        p.end()


def make_divider(parent=None) -> QFrame:
    line = QFrame(parent)
    line.setFrameShape(QFrame.Shape.VLine)
    line.setFixedWidth(1)
    line.setFixedHeight(22)
    line.setStyleSheet("background-color: rgba(255, 255, 255, 32); border: none;")
    return line


class AdaptiveLeftMenu(QFrame):
    def __init__(self, parent, canvas: 'DrawingCanvas'):
        super().__init__(parent)
        self.canvas = canvas
        self.settings = QSettings("MinimalistDrawing", "AdaptiveMenu")
        self.usage_counts = {
            "open": int(self.settings.value("usage_open", 0)),
            "save": int(self.settings.value("usage_save", 0)),
            "clear": int(self.settings.value("usage_clear", 0)),
            "theme": int(self.settings.value("usage_theme", 0)),
        }

        self.setObjectName("AdaptiveLeftMenu")
        self.setStyleSheet("""
            QFrame#AdaptiveLeftMenu {
                background-color: rgba(26, 26, 30, 240);
                border: 1px solid rgba(255, 255, 255, 35);
                border-radius: 14px;
            }
            QPushButton {
                border: none;
                border-radius: 8px;
                padding: 6px;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 22);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 38);
            }
        """)

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(6, 6, 6, 6)
        self.layout.setSpacing(4)

        icon_color = QColor("#e4e4e7")

        self.buttons = {
            "open": QPushButton(self),
            "save": QPushButton(self),
            "clear": QPushButton(self),
            "theme": QPushButton(self),
        }

        self.buttons["open"].setIcon(make_icon("open", color=icon_color))
        self.buttons["open"].setToolTip("Open Image (Ctrl+O)")
        self.buttons["open"].setFixedSize(30, 30)
        self.buttons["open"].clicked.connect(lambda: self._execute_action("open", self.canvas.open_image_dialog))

        self.buttons["save"].setIcon(make_icon("save", color=icon_color))
        self.buttons["save"].setToolTip("Save Canvas as PNG (Ctrl+S)")
        self.buttons["save"].setFixedSize(30, 30)
        self.buttons["save"].clicked.connect(lambda: self._execute_action("save", self.canvas.save_as_png_dialog))

        self.buttons["clear"].setIcon(make_icon("trash", color=QColor("#d4d4d8")))
        self.buttons["clear"].setToolTip("Clear Screen (C)")
        self.buttons["clear"].setFixedSize(30, 30)
        self.buttons["clear"].clicked.connect(lambda: self._execute_action("clear", self.canvas.clear_canvas))

        self.buttons["theme"].setFixedSize(30, 30)
        self.buttons["theme"].clicked.connect(lambda: self._execute_action("theme", self.canvas.toggle_dark_mode))

        self.reorganize_menu()

    def _execute_action(self, key: str, func):
        self.usage_counts[key] += 1
        self.settings.setValue(f"usage_{key}", self.usage_counts[key])
        func()
        self.reorganize_menu()

    def reorganize_menu(self):
        sorted_keys = sorted(self.usage_counts.keys(), key=lambda k: self.usage_counts[k], reverse=True)

        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        for key in sorted_keys:
            self.layout.addWidget(self.buttons[key])

        self.adjustSize()

    def update_dark_mode_label(self, dark_mode: bool):
        icon_color = QColor("#e4e4e7")
        if dark_mode:
            self.buttons["theme"].setIcon(make_icon("sun", color=icon_color))
            self.buttons["theme"].setToolTip("Switch to Light Mode (D)")
        else:
            self.buttons["theme"].setIcon(make_icon("moon", color=icon_color))
            self.buttons["theme"].setToolTip("Switch to Dark Mode (D)")


class FloatingPalette(QFrame):
    def __init__(self, parent, canvas: 'DrawingCanvas'):
        super().__init__(parent)
        self.canvas = canvas
        self.drag_position = QPoint()
        self.is_dragging = False

        self.setObjectName("Palette")
        self.setStyleSheet("""
            QFrame#Palette {
                background-color: rgba(26, 26, 30, 240);
                border: 1px solid rgba(255, 255, 255, 35);
                border-radius: 14px;
            }
            QPushButton#toolBtn, QPushButton#modeBtn {
                border: none;
                border-radius: 8px;
                padding: 6px 10px;
                font-size: 11.5px;
                font-weight: 600;
                color: #d4d4d8;
                background-color: transparent;
            }
            QPushButton#toolBtn:hover, QPushButton#modeBtn:hover {
                background-color: rgba(255, 255, 255, 22);
            }
            QPushButton#toolBtn:pressed, QPushButton#modeBtn:pressed {
                background-color: rgba(255, 255, 255, 38);
            }
            QPushButton#toolBtn:checked, QPushButton#modeBtn:checked {
                background-color: #4c8dff;
                color: #ffffff;
            }
            QLabel#sizeLabel {
                font-size: 11px;
                font-weight: 600;
                color: #b8b8be;
                min-width: 30px;
            }
            QSlider::groove:horizontal {
                background: rgba(255, 255, 255, 40);
                height: 4px;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #4c8dff;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                width: 13px;
                height: 13px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 6px;
            }
        """)

        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(8, 6, 8, 6)
        self.main_layout.setSpacing(6)

        self.drag_handle = QLabel("⋮⋮", self)
        self.drag_handle.setStyleSheet("color: #78787f; font-weight: bold; font-size: 13px; margin-right: 2px;")
        self.drag_handle.setCursor(Qt.CursorShape.SizeAllCursor)
        self.main_layout.addWidget(self.drag_handle)

        self.content_widget = QWidget(self)
        self.content_layout = QHBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(10)
        self.main_layout.addWidget(self.content_widget)

        icon_color = QColor("#e4e4e7")

        # Tool buttons
        self.btn_lasso = QPushButton(" Lasso", self)
        self.btn_lasso.setIcon(make_icon("lasso", color=icon_color))
        self.btn_lasso.setObjectName("toolBtn")
        self.btn_lasso.setCheckable(True)
        self.btn_lasso.setToolTip("Lasso Select / Resize (L)")
        self.btn_lasso.clicked.connect(lambda: self.canvas.set_tool("lasso"))

        self.btn_pen = QPushButton(" Pen", self)
        self.btn_pen.setIcon(make_icon("pen", color=icon_color))
        self.btn_pen.setObjectName("toolBtn")
        self.btn_pen.setCheckable(True)
        self.btn_pen.setChecked(True)
        self.btn_pen.setToolTip("Pen (P)")
        self.btn_pen.clicked.connect(lambda: self.canvas.set_tool("pen"))

        self.btn_highlighter = QPushButton(" Highlight", self)
        self.btn_highlighter.setIcon(make_icon("highlighter", color=icon_color))
        self.btn_highlighter.setObjectName("toolBtn")
        self.btn_highlighter.setCheckable(True)
        self.btn_highlighter.setToolTip("Highlighter (H)")
        self.btn_highlighter.clicked.connect(lambda: self.canvas.set_tool("highlighter"))

        self.btn_eraser = QPushButton(" Erase", self)
        self.btn_eraser.setIcon(make_icon("eraser", color=icon_color))
        self.btn_eraser.setObjectName("toolBtn")
        self.btn_eraser.setCheckable(True)
        self.btn_eraser.setToolTip("Eraser (E)")
        self.btn_eraser.clicked.connect(lambda: self.canvas.set_tool("eraser"))

        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True)
        for btn in (self.btn_lasso, self.btn_pen, self.btn_highlighter, self.btn_eraser):
            self.tool_group.addButton(btn)
            self.content_layout.addWidget(btn)

        self._tool_buttons = {
            "lasso": self.btn_lasso,
            "pen": self.btn_pen,
            "highlighter": self.btn_highlighter,
            "eraser": self.btn_eraser,
        }

        # --- Contextual Eraser Modes (Stroke Eraser vs Pixel Eraser) ---
        self.eraser_container = QWidget(self)
        self.eraser_layout = QHBoxLayout(self.eraser_container)
        self.eraser_layout.setContentsMargins(0, 0, 0, 0)
        self.eraser_layout.setSpacing(6)

        self.eraser_divider = make_divider(self)
        self.eraser_layout.addWidget(self.eraser_divider)

        self.btn_erase_stroke = QPushButton("Stroke Eraser", self)
        self.btn_erase_stroke.setObjectName("modeBtn")
        self.btn_erase_stroke.setCheckable(True)
        self.btn_erase_stroke.setChecked(True)
        self.btn_erase_stroke.setToolTip("Erase Entire Strokes on Touch")
        self.btn_erase_stroke.clicked.connect(lambda: self.canvas.set_eraser_type(EraserType.STROKE))

        self.btn_erase_pixel = QPushButton("Pixel Eraser", self)
        self.btn_erase_pixel.setObjectName("modeBtn")
        self.btn_erase_pixel.setCheckable(True)
        self.btn_erase_pixel.setToolTip("Erase like a Brush")
        self.btn_erase_pixel.clicked.connect(lambda: self.canvas.set_eraser_type(EraserType.PIXEL))

        self.erase_mode_group = QButtonGroup(self)
        self.erase_mode_group.setExclusive(True)
        self.erase_mode_group.addButton(self.btn_erase_stroke)
        self.erase_mode_group.addButton(self.btn_erase_pixel)

        self.eraser_layout.addWidget(self.btn_erase_stroke)
        self.eraser_layout.addWidget(self.btn_erase_pixel)

        self.content_layout.addWidget(self.eraser_container)
        self.eraser_container.setVisible(False)

        # --- Color Swatches Container ---
        self.color_container = QWidget(self)
        self.color_layout = QHBoxLayout(self.color_container)
        self.color_layout.setContentsMargins(0, 0, 0, 0)
        self.color_layout.setSpacing(6)

        self.color_divider = make_divider(self)
        self.color_layout.addWidget(self.color_divider)

        self.swatch_ink = ColorSwatch(None, "Automatic (matches theme)", self, is_auto=True)
        self.swatch_ink.setChecked(True)
        self.swatch_ink.clicked.connect(lambda: self.canvas.set_pen_color(Ink.DEFAULT))

        self.swatch_red = ColorSwatch(QColor(Qt.GlobalColor.red), "Red", self)
        self.swatch_red.clicked.connect(lambda: self.canvas.set_pen_color(QColor(Qt.GlobalColor.red)))

        self.swatch_blue = ColorSwatch(QColor(Qt.GlobalColor.blue), "Blue", self)
        self.swatch_blue.clicked.connect(lambda: self.canvas.set_pen_color(QColor(Qt.GlobalColor.blue)))

        self.swatch_custom = ColorSwatch(None, "Custom color…", self)
        self.swatch_custom.clicked.connect(self.choose_custom_color)

        self.color_group = QButtonGroup(self)
        self.color_group.setExclusive(True)
        for sw in (self.swatch_ink, self.swatch_red, self.swatch_blue, self.swatch_custom):
            self.color_group.addButton(sw)
            self.color_layout.addWidget(sw)

        self._preset_colors = {
            "red": QColor(Qt.GlobalColor.red),
            "blue": QColor(Qt.GlobalColor.blue),
        }

        self.content_layout.addWidget(self.color_container)

        self.content_layout.addWidget(make_divider(self))

        # --- Size Controls ---
        self.lbl_thickness = QLabel("5px", self)
        self.lbl_thickness.setObjectName("sizeLabel")
        self.content_layout.addWidget(self.lbl_thickness)

        self.slider = QSlider(Qt.Orientation.Horizontal, self)
        self.slider.setRange(1, 100)
        self.slider.setValue(5)
        self.slider.setFixedWidth(80)
        self.slider.setToolTip("Stroke / Eraser width ([ / ])")
        self.slider.valueChanged.connect(self.canvas.set_pen_width)
        self.content_layout.addWidget(self.slider)

        self.content_layout.addWidget(make_divider(self))

        # --- Clear Screen Button ---
        self.btn_clear = QPushButton(" Clear", self)
        self.btn_clear.setIcon(make_icon("trash", color=QColor("#f87171")))
        self.btn_clear.setObjectName("toolBtn")
        self.btn_clear.setToolTip("Clear Screen (C)")
        self.btn_clear.clicked.connect(self.canvas.clear_canvas)
        self.content_layout.addWidget(self.btn_clear)

        self.adjustSize()

    def update_contextual_controls(self, tool_name: str):
        if tool_name == "eraser":
            self.color_container.setVisible(False)
            self.eraser_container.setVisible(True)
        else:
            self.eraser_container.setVisible(False)
            self.color_container.setVisible(True)
        self.adjustSize()

        parent = self.parentWidget()
        if parent is not None and hasattr(parent, "reposition_overlays"):
            parent.reposition_overlays()

    def choose_custom_color(self):
        curr = self.canvas.get_display_color(self.canvas.current_color)
        color = QColorDialog.getColor(curr, self, "Choose Pen Color")
        if color.isValid():
            self.swatch_custom.set_color(color)
            self.canvas.set_pen_color(color)
        else:
            self.sync_color_buttons(self.canvas.current_color)

    def update_thickness_label(self, width: int):
        self.lbl_thickness.setText(f"{width}px")
        if self.slider.value() != width:
            self.slider.blockSignals(True)
            self.slider.setValue(width)
            self.slider.blockSignals(False)

    def sync_tool_buttons(self, name: str):
        btn = self._tool_buttons.get(name)
        if btn is not None and not btn.isChecked():
            btn.setChecked(True)
        self.update_contextual_controls(name)

    def sync_color_buttons(self, color: QColor | Ink):
        if color == Ink.DEFAULT:
            self.swatch_ink.setChecked(True)
            return
        qcolor = QColor(color)
        for key, sw in (("red", self.swatch_red), ("blue", self.swatch_blue)):
            if qcolor == self._preset_colors[key]:
                sw.setChecked(True)
                return
        self.swatch_custom.set_color(qcolor)
        self.swatch_custom.setChecked(True)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.drag_handle.geometry().contains(event.position().toPoint()):
                self.is_dragging = True
                self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_dragging and (event.buttons() & Qt.MouseButton.LeftButton):
            parent_widget = self.parentWidget()
            new_pos = event.globalPosition().toPoint() - self.drag_position
            if parent_widget:
                max_x = max(0, parent_widget.width() - self.width())
                max_y = max(0, parent_widget.height() - self.height())
                clamped_x = max(0, min(max_x, new_pos.x()))
                clamped_y = max(0, min(max_y, new_pos.y()))
                self.move(clamped_x, clamped_y)
            else:
                self.move(new_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.is_dragging = False
        super().mouseReleaseEvent(event)


class CanvasLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrame(False)
        self.hide()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.clear()
            self.hide()
            event.accept()
            return
        super().keyPressEvent(event)


# =============================================================================
# 6. Infinite Drawing Canvas Widget
# =============================================================================

class DrawingCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)

        self.doc = Document()
        self.doc.invalidated.connect(self.update)

        self.dark_mode = True
        self.bg_color = QColor("#121212") if self.dark_mode else QColor("#FFFFFF")

        self.pan_x = 0.0
        self.pan_y = 0.0
        self.zoom = 1.0
        self.is_panning = False
        self.is_space_pressed = False
        self.last_pan_pos = QPointF(0, 0)

        self.current_color: QColor | Ink = Ink.DEFAULT
        self.current_width: float = 5.0
        self.eraser_type: EraserType = EraserType.STROKE
        self.stylus_pressure: float = 1.0

        self.tools = {
            "lasso": LassoTool(),
            "pen": PenTool(),
            "highlighter": HighlighterTool(),
            "eraser": EraserTool(),
        }
        self.active_tool_name: str = "pen"
        self.active_tool: Tool = self.tools["pen"]
        self.setCursor(self.active_tool.cursor)

        self.text_input = CanvasLineEdit(self)
        self.text_input.returnPressed.connect(self.commit_text)
        self.text_canvas_pos = QPointF(0, 0)

        self.palette: FloatingPalette | None = None
        self.left_menu: AdaptiveLeftMenu | None = None
        self.clipboard_items: list[Item] = []

        self.settings = QSettings("MinimalistDrawing", "MinimalistDrawing")
        home_dir = os.path.expanduser("~")
        self.last_save_dir = self.settings.value("last_save_dir", home_dir, type=str)
        self.last_open_dir = self.settings.value("last_open_dir", home_dir, type=str)

    def set_palette(self, palette: FloatingPalette):
        self.palette = palette
        self.palette.sync_tool_buttons(self.active_tool_name)
        self.palette.sync_color_buttons(self.current_color)

    def set_left_menu(self, left_menu: AdaptiveLeftMenu):
        self.left_menu = left_menu
        self.left_menu.update_dark_mode_label(self.dark_mode)

    def set_tool(self, name: str):
        if name in self.tools:
            if self.active_tool_name == "lasso" and name != "lasso":
                self.tools["lasso"].selected_items.clear()
            self.active_tool = self.tools[name]
            self.active_tool_name = name
            self.setCursor(self.active_tool.cursor)
            if self.palette:
                self.palette.sync_tool_buttons(name)
            self.update()

    def set_eraser_type(self, mode: EraserType):
        self.eraser_type = mode
        self.set_tool("eraser")

    def set_pen_color(self, color: QColor | Ink):
        self.current_color = color
        if self.palette:
            self.palette.sync_color_buttons(color)

    def set_pen_width(self, width: float):
        self.current_width = max(1.0, min(100.0, float(width)))
        if self.palette:
            self.palette.update_thickness_label(int(self.current_width))

    def view_transform(self) -> QTransform:
        t = QTransform()
        t.translate(self.pan_x, self.pan_y)
        t.scale(self.zoom, self.zoom)
        return t

    def map_to_canvas(self, pos: QPointF | QPoint) -> QPointF:
        inv, ok = self.view_transform().inverted()
        if ok:
            return inv.map(QPointF(pos))
        return QPointF(pos)

    def get_display_color(self, color: QColor | Ink) -> QColor:
        if color == Ink.DEFAULT:
            return QColor("#FFFFFF") if self.dark_mode else QColor("#000000")
        return QColor(color)

    def toggle_dark_mode(self):
        self.dark_mode = not self.dark_mode
        self.bg_color = QColor("#121212") if self.dark_mode else QColor("#FFFFFF")
        if self.left_menu:
            self.left_menu.update_dark_mode_label(self.dark_mode)
        self.update()

    def clear_canvas(self):
        lasso = self.tools.get("lasso")
        if lasso and hasattr(lasso, "selected_items"):
            lasso.selected_items.clear()
        self.doc.clear()
        if self.text_input.isVisible():
            self.text_input.clear()
            self.text_input.hide()
        self.update()

    def copy_selection(self):
        lasso: LassoTool = self.tools["lasso"]
        if lasso.selected_items:
            self.clipboard_items = [item.clone() for item in lasso.selected_items]

    def delete_selection(self):
        lasso: LassoTool = self.tools["lasso"]
        if self.active_tool_name != "lasso" or not lasso.selected_items:
            return

        items = list(lasso.selected_items)
        if len(items) > 1:
            self.doc.undo_stack.beginMacro("Delete Selection")
        for item in items:
            self.doc.remove_item(item)
        if len(items) > 1:
            self.doc.undo_stack.endMacro()

        lasso.selected_items.clear()
        self.update()

    def paste_selection(self):
        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData() if clipboard else None

        if mime is not None and mime.hasImage():
            image = clipboard.image()
            if not image.isNull():
                pixmap = QPixmap.fromImage(image)
                center = self.map_to_canvas(QPointF(self.width() / 2.0, self.height() / 2.0))
                item = self.insert_image(pixmap, center=center)
                if item is not None:
                    self.set_tool("lasso")
                    lasso: LassoTool = self.tools["lasso"]
                    lasso.selected_items = [item]
                    self.update()
                return

        if not self.clipboard_items:
            return

        new_items = [item.clone() for item in self.clipboard_items]
        offset_tx = QTransform.fromTranslate(30, 30)
        for item in new_items:
            item.apply_transform(offset_tx)

        for item in self.clipboard_items:
            item.apply_transform(offset_tx)

        self.doc.paste_items(new_items)

        self.set_tool("lasso")
        lasso: LassoTool = self.tools["lasso"]
        lasso.selected_items = list(new_items)
        self.update()

    def get_content_bounds(self) -> QRectF:
        bounds = QRectF()
        for item in self.doc.items:
            bounds = item.bounds() if bounds.isNull() else bounds.united(item.bounds())
        if bounds.isNull():
            bounds = QRectF(0, 0, 800, 600)
        return bounds

    def export_png(self, file_path: str, margin: float = 40.0) -> bool:
        bounds = self.get_content_bounds().adjusted(-margin, -margin, margin, margin)
        if bounds.width() <= 0 or bounds.height() <= 0:
            bounds = QRectF(0, 0, 800, 600)

        image = QImage(max(1, int(bounds.width())), max(1, int(bounds.height())), QImage.Format.Format_ARGB32)
        image.fill(self.bg_color)

        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.translate(-bounds.topLeft())
        for item in self.doc.items:
            self._paint_item(painter, item)
        painter.end()

        return image.save(file_path, "PNG")

    def save_as_png_dialog(self):
        default_name = f"minimalist_drawing_{time.strftime('%Y%m%d_%H%M%S')}.png"
        default_path = os.path.join(self.last_save_dir, default_name)
        file_path, _ = QFileDialog.getSaveFileName(self, "Save as PNG", default_path, "PNG Image (*.png)")
        if not file_path:
            return
        if not file_path.lower().endswith(".png"):
            file_path += ".png"

        if self.export_png(file_path):
            self.last_save_dir = os.path.dirname(file_path) or self.last_save_dir
            self.settings.setValue("last_save_dir", self.last_save_dir)
            QMessageBox.information(self, "Saved", f"Canvas saved to:\n{file_path}")
        else:
            QMessageBox.warning(self, "Save Failed", f"Could not save the canvas to:\n{file_path}")

    def insert_image(self, pixmap: QPixmap, center: QPointF | None = None) -> 'ImageItem | None':
        max_dim = 900.0
        w, h = float(pixmap.width()), float(pixmap.height())
        if w <= 0 or h <= 0:
            return None
        scale = min(1.0, max_dim / max(w, h))
        disp_w, disp_h = w * scale, h * scale

        if center is None:
            center = self.map_to_canvas(QPointF(self.width() / 2.0, self.height() / 2.0))
        pos = QPointF(center.x() - disp_w / 2.0, center.y() - disp_h / 2.0)

        item = ImageItem(image=pixmap, pos=pos, size=QSize(max(1, int(disp_w)), max(1, int(disp_h))))
        self.doc.add_item(item)
        return item

    def open_image_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Image", self.last_open_dir, "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if not file_path:
            return
        pixmap = QPixmap(file_path)
        if pixmap.isNull():
            QMessageBox.warning(self, "Open Failed", f"Could not load image:\n{file_path}")
            return
        self.last_open_dir = os.path.dirname(file_path) or self.last_open_dir
        self.settings.setValue("last_open_dir", self.last_open_dir)
        self.insert_image(pixmap)

    def undo_stroke(self):
        self.doc.undo_stack.undo()

    def redo_stroke(self):
        self.doc.undo_stack.redo()

    def zoom_at(self, screen_pt: QPointF, factor: float):
        before = self.map_to_canvas(screen_pt)
        new_zoom = max(0.05, min(20.0, self.zoom * factor))
        if new_zoom == self.zoom:
            return
        self.zoom = new_zoom
        after = self.map_to_canvas(screen_pt)
        d = after - before
        self.pan_x += d.x() * self.zoom
        self.pan_y += d.y() * self.zoom
        self.update()

    def _paint_item(self, painter: QPainter, item: Item):
        if isinstance(item, TextItem):
            painter.setFont(item.font)
            color = self.get_display_color(item.style.color)
            painter.setPen(color)
            fm = QFontMetrics(item.font)
            baseline_y = item.pos.y() + (max(30.0, fm.height() * 1.4) - fm.height()) / 2.0 + fm.ascent()
            painter.drawText(QPointF(item.pos.x()), item.text)

        elif isinstance(item, ImageItem):
            target = QRectF(item.pos, QSizeF(item.size))
            painter.drawPixmap(target, item.image, QRectF(item.image.rect()))

        elif isinstance(item, StrokeItem):
            color = self.get_display_color(item.style.color)
            if item.style.opacity < 1.0:
                color = QColor(color)
                color.setAlphaF(item.style.opacity)
            pen = QPen(
                color, item.style.width,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.FlatCap if item.style.opacity < 1.0 else Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin
            )
            painter.setPen(pen)
            painter.drawPath(item.path)

        elif isinstance(item, EraseMaskItem):
            painter.save()
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
            pen = QPen(
                QColor(0, 0, 0, 255), item.width,
                Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin
            )
            painter.setPen(pen)
            painter.drawPath(item.path)
            painter.restore()

    def commit_text(self):
        text = self.text_input.text().strip()
        if text:
            style = Style(color=self.current_color, width=self.current_width)
            item = TextItem(
                text=text,
                pos=self.text_canvas_pos,
                font=self.text_input.font(),
                style=style,
                timestamp=time.time()
            )
            self.doc.add_item(item)
        self.text_input.hide()
        self.text_input.clear()

    # --- Mouse & Tablet Event Handlers ---
    def tabletEvent(self, event):
        event.accept()
        pos = self.map_to_canvas(event.position())
        pressure = event.pressure()
        if pressure > 0:
            self.stylus_pressure = max(0.4, min(1.8, pressure * 1.5))

        if event.type() == QEvent.Type.TabletPress:
            self.active_tool.press(self, pos, event)
        elif event.type() == QEvent.Type.TabletMove:
            self.active_tool.move(self, pos, event)
        elif event.type() == QEvent.Type.TabletRelease:
            item = self.active_tool.release(self, pos, event)
            if item is not None:
                self.doc.add_item(item)
            self.stylus_pressure = 1.0
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton or (event.button() == Qt.MouseButton.LeftButton and self.is_space_pressed):
            self.is_panning = True
            self.last_pan_pos = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            if self.text_input.isVisible() or self.text_input.text():
                self.commit_text()

            pos = self.map_to_canvas(event.position())
            self.active_tool.press(self, pos, event)
            self.update()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.is_panning:
            delta = event.position() - self.last_pan_pos
            self.pan_x += delta.x()
            self.pan_y += delta.y()
            self.last_pan_pos = event.position()
            self.update()
            event.accept()
            return

        pos = self.map_to_canvas(event.position())

        if event.buttons() & Qt.MouseButton.LeftButton:
            self.active_tool.move(self, pos, event)
            self.update()
            event.accept()
        else:
            if hasattr(self.active_tool, "hover_move"):
                self.active_tool.hover_move(self, pos)
            else:
                self.setCursor(self.active_tool.cursor)

    def mouseReleaseEvent(self, event):
        if self.is_panning:
            self.is_panning = False
            self.setCursor(Qt.CursorShape.OpenHandCursor if self.is_space_pressed else self.active_tool.cursor)
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            pos = self.map_to_canvas(event.position())
            item = self.active_tool.release(self, pos, event)
            if item is not None:
                self.doc.add_item(item)
            self.update()
            event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.active_tool_name != "lasso":
            pos = self.map_to_canvas(event.position())
            if self.doc.items:
                last_item = self.doc.items[-1]
                if isinstance(last_item, StrokeItem):
                    now = time.time()
                    if (now - last_item.timestamp < 0.45) and last_item.points:
                        p0 = last_item.points[0]
                        if math.hypot(p0.x() - pos.x(), p0.y() - pos.y()) < 35.0:
                            self.doc.items.pop()
                            self.doc.rebuild_spatial_index()
                            self.update()

            if self.text_input.isVisible():
                self.commit_text()

            click_pos = event.position().toPoint()
            self.text_canvas_pos = pos

            font_size = max(12, int(self.current_width * 2.5))
            font = self.text_input.font()
            font.setPointSize(font_size)
            self.text_input.setFont(font)

            display_color = self.get_display_color(self.current_color)
            self.text_input.setStyleSheet(f"""
                QLineEdit {{
                    background: transparent;
                    border: none;
                    outline: none;
                    padding: 0px;
                    color: {display_color.name()};
                    selection-background-color: #3399ff;
                }}
            """)

            self.text_input.setText("")
            self.text_input.move(click_pos)
            fm = QFontMetrics(font)
            input_height = max(30, int(fm.height() * 1.4))
            self.text_input.resize(400, input_height)
            self.text_input.show()
            self.text_input.setFocus()
            event.accept()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            angle = event.angleDelta().y()
            if angle != 0:
                factor = 1.0015 ** angle
                self.zoom_at(event.position(), factor)
            event.accept()
            return

        pixel_delta = event.pixelDelta()
        if not pixel_delta.isNull():
            dx = float(pixel_delta.x())
            dy = float(pixel_delta.y())
        else:
            angle_delta = event.angleDelta()
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                dx = angle_delta.y() / 4.0
                dy = 0.0
            else:
                dx = angle_delta.x() / 4.0
                dy = angle_delta.y() / 4.0

        self.pan_x += dx
        self.pan_y += dy
        self.update()
        event.accept()

    def _draw_infinite_grid(self, painter: QPainter):
        grid_size = 50.0 * self.zoom
        while grid_size < 30.0:
            grid_size *= 2.0
        while grid_size > 120.0:
            grid_size /= 2.0

        ox = self.pan_x % grid_size
        oy = self.pan_y % grid_size

        painter.save()
        grid_color = QColor(255, 255, 255, 22) if self.dark_mode else QColor(0, 0, 0, 18)
        painter.setPen(QPen(grid_color, 1.5))

        x = ox
        while x < self.width():
            y = oy
            while y < self.height():
                painter.drawPoint(QPointF(x, y))
                y += grid_size
            x += grid_size
        painter.restore()

    def paintEvent(self, event):
        w = max(1, self.width())
        h = max(1, self.height())
        buffer_img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        buffer_img.fill(Qt.GlobalColor.transparent)

        painter = QPainter(buffer_img)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        inv, ok = self.view_transform().inverted()
        visible_canvas_rect = inv.mapRect(QRectF(self.rect())) if ok else QRectF()

        painter.save()
        painter.setTransform(self.view_transform())

        visible_items = list(self.doc.spatial_index.query(visible_canvas_rect))

        for item in visible_items:
            self._paint_item(painter, item)

        if self.active_tool:
            self.active_tool.paint_preview(painter, self)

        painter.restore()
        painter.end()

        final_painter = QPainter(self)
        final_painter.fillRect(self.rect(), self.bg_color)
        self._draw_infinite_grid(final_painter)
        final_painter.drawImage(0, 0, buffer_img)
        final_painter.end()


# =============================================================================
# 7. Main Application Window
# =============================================================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Minimalist Drawing")
        self.resize(1100, 800)

        self.canvas = DrawingCanvas(self)
        self.setCentralWidget(self.canvas)

        self.palette = FloatingPalette(self, self.canvas)
        self.left_menu = AdaptiveLeftMenu(self, self.canvas)

        self.canvas.set_palette(self.palette)
        self.canvas.set_left_menu(self.left_menu)

        self.reposition_overlays()

    def reposition_overlays(self):
        if hasattr(self, 'palette') and self.palette is not None:
            palette_width = self.palette.width()
            window_width = self.width()
            x = (window_width - palette_width) // 2
            self.palette.move(max(10, x), 15)

        if hasattr(self, 'left_menu') and self.left_menu is not None:
            self.left_menu.move(15, 15)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.reposition_overlays()

    def keyPressEvent(self, event):
        if self.canvas.text_input.hasFocus():
            super().keyPressEvent(event)
            return

        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self.canvas.is_space_pressed = True
            self.canvas.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return

        if (event.modifiers() == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier) and event.key() == Qt.Key.Key_Z) or \
           (event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_Y):
            self.canvas.redo_stroke()
            event.accept()
            return

        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_Z:
            self.canvas.undo_stroke()
            event.accept()
            return

        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_C:
            self.canvas.copy_selection()
            event.accept()
            return

        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_V:
            self.canvas.paste_selection()
            event.accept()
            return

        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.canvas.delete_selection()
            event.accept()
            return

        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_S:
            self.canvas.save_as_png_dialog()
            event.accept()
            return

        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_O:
            self.canvas.open_image_dialog()
            event.accept()
            return

        elif event.key() == Qt.Key.Key_D:
            self.canvas.toggle_dark_mode()
            event.accept()
            return

        elif event.key() == Qt.Key.Key_C:
            self.canvas.clear_canvas()
            event.accept()
            return

        elif event.key() == Qt.Key.Key_BracketLeft:
            self.canvas.set_pen_width(self.canvas.current_width - 1.0)
            event.accept()
            return
        elif event.key() == Qt.Key.Key_BracketRight:
            self.canvas.set_pen_width(self.canvas.current_width + 1.0)
            event.accept()
            return

        elif event.key() == Qt.Key.Key_L:
            self.canvas.set_tool("lasso")
            event.accept()
            return
        elif event.key() == Qt.Key.Key_P:
            self.canvas.set_tool("pen")
            event.accept()
            return
        elif event.key() == Qt.Key.Key_H:
            self.canvas.set_tool("highlighter")
            event.accept()
            return
        elif event.key() == Qt.Key.Key_E:
            self.canvas.set_tool("eraser")
            event.accept()
            return

        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self.canvas.is_space_pressed = False
            self.canvas.setCursor(self.canvas.active_tool.cursor)
            event.accept()
            return
        super().keyReleaseEvent(event)


def main():
    if sys.platform == "win32":
        try:
            import ctypes
            myappid = "luffy3006.minimalistdrawing.app.1.0.0"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("Minimalist Drawing")
    app.setDesktopFileName("minimalist-drawing")

    icon = QIcon.fromTheme("minimalist-drawing")
    if icon.isNull():
        candidates = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "packaging", "minimalist-drawing.ico"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "packaging", "minimalist-drawing.png"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "packaging", "minimalist-drawing.svg"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "minimalist_drawing", "assets", "minimalist-drawing.ico"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "minimalist_drawing", "assets", "minimalist-drawing.png"),
            "/usr/share/icons/hicolor/scalable/apps/minimalist-drawing.svg",
            "/usr/share/icons/hicolor/256x256/apps/minimalist-drawing.png",
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                icon = QIcon(candidate)
                break

    if not icon.isNull():
        app.setWindowIcon(icon)

    window = MainWindow()
    if not icon.isNull():
        window.setWindowIcon(icon)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
