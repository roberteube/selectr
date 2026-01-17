import random as rd

from PySide6.QtWidgets import \
    QStyledItemDelegate, \
    QStyleOptionViewItem, \
    QFileIconProvider, \
    QStyle
from PySide6.QtGui import QPainter, QFont, QMouseEvent, QPixmap, QColor
from PySide6.QtCore import Qt, QRect, QSortFilterProxyModel, QSize, QEvent


from TagManager import TagManager
from ModInfo import ModInfo

def generate_color(tag: str, offset = rd.randint(0, 300)):
    return QColor.fromHsv((sum(map(ord, tag)) + offset) % 300 + 30, 200, 128)


class FileItemDelegate(QStyledItemDelegate):
    """Custom delegate that paints file entries with icons and previews.

    It displays file type icons or image previews on the left, and two lines of 
    text (name and size/date) on the right. This keeps the UI lightweight compared 
    to using full widget-based items.
    """

    def __init__(self, parent=None, tag_manager: TagManager = None):
        super().__init__(parent)
        self.icon_provider = QFileIconProvider()
        self.preview_cache = {}  # Cache for image previews
        self.tag_manager = tag_manager

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        model = index.model()
        current_index = index
        
        # Handle nested proxy models: map through all layers to get to the source
        while isinstance(model, QSortFilterProxyModel):
            current_index = model.mapToSource(current_index)
            model = model.sourceModel()
        
        # Now we have the actual file system model
        file_path = model.filePath(current_index)
        file_info = model.fileInfo(current_index)
        mod_info: ModInfo = ModInfo(file_path)
        
        name = mod_info.enabledName()
        size = mod_info.size()
        mtime = mod_info.lastModified().toString()

        painter.save()

        # background for selection
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, QColor(30,30,30))  # light gray
            text_color = option.palette.text().color()
        else:
            text_color = option.palette.text().color()

        # Draw colored circle background (red for disabled, green for enabled)
        margin = 8
        icon_size = 48
        icon_rect = QRect(option.rect.left() + margin, option.rect.top() + (option.rect.height() - icon_size) // 2, icon_size, icon_size)
        
        # button background: red for disabled, green for enabled
        if mod_info.isDisabled():
            btn_color = QColor(139, 35, 35)  # dark red
        else:
            btn_color = QColor(34, 102, 34)  # dark green
        painter.setBrush(btn_color)
        painter.setPen(Qt.NoPen)
        painter.drawRect(icon_rect)
        
        # Draw icon or preview on top of colored circle
        # Try to get preview for images, otherwise use file type icon
        preview_pixmap = None
        if self._is_image(file_path):
            preview_pixmap = self._get_image_preview(file_path, icon_size - 6)  # Slightly smaller to show circle edge
        
        if preview_pixmap:
            # Center the pixmap within the circle
            x_offset = (icon_rect.width() - preview_pixmap.width()) // 2
            y_offset = (icon_rect.height() - preview_pixmap.height()) // 2
            painter.drawPixmap(icon_rect.left() + x_offset, icon_rect.top() + y_offset, preview_pixmap)
        else:
            # Get file type icon from system and paint it smaller in the center
            file_icon = self.icon_provider.icon(file_info)
            # Create a smaller rect for the icon inside the circle
            icon_inner_size = icon_size - 8
            inner_rect = QRect(icon_rect.left() + 4, icon_rect.top() + 4, icon_inner_size, icon_inner_size)
            file_icon.paint(painter, inner_rect, Qt.AlignCenter)

        # text area
        x = icon_rect.right() + margin
        y = option.rect.top() + margin
        w = option.rect.width() - (x - option.rect.left()) - margin
        # Name (bold)
        name_font = QFont(option.font)
        name_font.setBold(True)
        painter.setFont(name_font)
        painter.setPen(QColor(text_color))
        painter.drawText(QRect(x, y, w, 20), Qt.AlignLeft | Qt.AlignVCenter, name)

        # tags (colored pills/badges)
        tags = []
        if self.tag_manager:
            tags = self.tag_manager.get_tags(file_path)
        
        if tags:
            tags_font = QFont(option.font)
            tags_font.setPointSize(max(8, option.font.pointSize() - 3))
            painter.setFont(tags_font)
            
            # Define tag colors (cycle through different colors)
            tag_colors = [
                QColor(100, 150, 200),  # blue
                QColor(150, 100, 200),  # purple
                QColor(100, 200, 150),  # green
                QColor(200, 150, 100),  # orange
                QColor(200, 100, 150),  # pink
            ]
            
            tag_x = x
            tag_y = y + 20
            pill_height = 16
            
            for i, tag in enumerate(tags):
                tag_text = f"#{tag}"
                tag_metrics = painter.fontMetrics()
                text_width = tag_metrics.horizontalAdvance(tag_text)
                pill_width = text_width + 8  # Padding
                
                # Only draw if it fits in the row
                if tag_x + pill_width > x + w:
                    break
                
                # Draw pill background
                tag_color = generate_color(tag)
                painter.setBrush(tag_color)
                painter.setPen(Qt.NoPen)
                pill_rect = QRect(tag_x, tag_y, pill_width, pill_height)
                painter.drawRoundedRect(pill_rect, 4, 4)
                
                # Draw text
                painter.setPen(QColor(255, 255, 255))  # White text
                painter.drawText(pill_rect, Qt.AlignCenter, tag_text)
                
                tag_x += pill_width + 4  # Space between pills
        
        painter.restore()

    def _is_image(self, file_path: str) -> bool:
        """Check if file is an image."""
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.svg', '.webp', '.tiff'}
        return file_path.lower().endswith(tuple(image_extensions))

    def _get_image_preview(self, file_path: str, size: int):
        """Get or create a cached preview pixmap for an image."""
        if file_path in self.preview_cache:
            return self.preview_cache[file_path]
        
        try:
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                # Scale to fit in icon_size while maintaining aspect ratio
                scaled_pixmap = pixmap.scaledToWidth(size, Qt.SmoothTransformation)
                if scaled_pixmap.height() > size:
                    scaled_pixmap = scaled_pixmap.scaledToHeight(size, Qt.SmoothTransformation)
                self.preview_cache[file_path] = scaled_pixmap
                return scaled_pixmap
        except Exception:
            pass
        
        return None

    def sizeHint(self, option, index):
        return QSize(200, 64)

    def editorEvent(self, event: QMouseEvent, model, option, index):
        """Handle mouse events on the item — detect clicks on the icon area.

        When the icon/preview area is clicked, toggle DISABLED_ on the file/folder name.
        Clicks outside the icon allow normal selection.
        """
        if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            # Recompute icon_rect to match paint()
            margin = 8
            icon_size = 48
            icon_rect = QRect(option.rect.left() + margin, option.rect.top() + (option.rect.height() - icon_size) // 2, icon_size, icon_size)
            
            # Check if click is on the icon
            if icon_rect.contains(event.position().toPoint()):
                # Click is on icon — toggle disable/enable
                try:
                    # Handle nested proxy models: map through all layers
                    current_index = index
                    current_model = model
                    while isinstance(current_model, QSortFilterProxyModel):
                        current_index = current_model.mapToSource(current_index)
                        current_model = current_model.sourceModel()
                    
                    path = current_model.filePath(current_index)
                    
                    ModInfo(path).toggle()
                    
                    # Trigger refresh if FileManager reference is available
                    if hasattr(self, 'file_manager'):
                        self.file_manager.refresh()
                except Exception as e:
                    print(f"Error renaming: {e}")
                return True
            else:
                # Click outside icon — ensure item is selected
                return False
        return super().editorEvent(event, model, option, index)