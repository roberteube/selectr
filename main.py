"""Simple PySide6 file manager.

This module provides a minimal file manager UI using PySide6. It includes a
directory tree and a list view with a custom-drawn item delegate that shows an
icon, filename, and tags for each entry.

Run as a script to launch the GUI.
"""

import sys
import os
import json
import random as rd

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTreeView,
    QListView,
    QFileSystemModel,
    QToolBar,
    QStyle,
    QLineEdit,
    QSplitter,
    QMessageBox,
    QInputDialog,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QFileIconProvider,
    QMenu,
)
from PySide6.QtCore import QDir, Qt, QUrl, QSize, QRect, QFileInfo, QEvent
from PySide6.QtGui import QDesktopServices, QAction, QPainter, QFont, QColor, QMouseEvent, QPixmap
from PySide6.QtCore import QSortFilterProxyModel

from ModInfo import ModInfo


def generate_color(tag: str, offset = rd.randint(0, 300)):
    return QColor.fromHsv((sum(map(ord, tag)) + offset) % 300 + 30, 200, 128)

class TagManager:
    """Manages tags stored in a JSON file."""
    
    TAGS_FILE = ".tags.json"
    
    def __init__(self, base_dir: str = None):
        self.base_dir = base_dir or os.path.expanduser("~")
        self.tags_path = os.path.join(self.base_dir, self.TAGS_FILE)
        self.tags = self._load_tags()
    
    def _load_tags(self) -> dict:
        """Load tags from JSON file."""
        if os.path.exists(self.tags_path):
            try:
                with open(self.tags_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading tags: {e}")
        return {}
    
    def _save_tags(self):
        """Save tags to JSON file."""
        try:
            with open(self.tags_path, 'w', encoding='utf-8') as f:
                json.dump(self.tags, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving tags: {e}")
    
    def get_tags(self, file_path: str) -> list:
        """Get tags for a file/folder."""
        normalized_path = os.path.normpath(file_path)
        return self.tags.get(normalized_path, [])
    
    def add_tag(self, file_path: str, tag: str):
        """Add a tag to a file/folder."""
        normalized_path = os.path.normpath(file_path)
        if normalized_path not in self.tags:
            self.tags[normalized_path] = []
        if tag not in self.tags[normalized_path]:
            self.tags[normalized_path].append(tag)
            self._save_tags()
    
    def remove_tag(self, file_path: str, tag: str):
        """Remove a tag from a file/folder."""
        normalized_path = os.path.normpath(file_path)
        if normalized_path in self.tags and tag in self.tags[normalized_path]:
            self.tags[normalized_path].remove(tag)
            if not self.tags[normalized_path]:  # Remove entry if no tags left
                del self.tags[normalized_path]
            self._save_tags()
    
    def set_tags(self, file_path: str, tags: list):
        """Set all tags for a file/folder."""
        normalized_path = os.path.normpath(file_path)
        if tags:
            self.tags[normalized_path] = tags
        elif normalized_path in self.tags:
            del self.tags[normalized_path]
        self._save_tags()


class ModInfoSortProxyModel(QSortFilterProxyModel):
    """Custom sort proxy that sorts by ModInfo.enabledName()."""
    
    def lessThan(self, left, right):
        left_path = self.sourceModel().filePath(left)
        right_path = self.sourceModel().filePath(right)
        
        left_info = ModInfo(left_path)
        right_info = ModInfo(right_path)
        
        left_name = left_info.enabledName()
        right_name = right_info.enabledName()
        
        return left_name.lower() < right_name.lower()


class SearchFilterProxyModel(QSortFilterProxyModel):
    """Custom filter proxy that filters by name or tag."""
    
    def __init__(self, tag_manager: TagManager = None):
        super().__init__()
        self.tag_manager = tag_manager
        self.search_text = ""
        self.root_path = ""
    
    def set_search_text(self, text: str):
        """Set the search text and trigger filter update."""
        self.search_text = text.lower()
        # Invalidate filter to re-evaluate all rows
        try:
            self.invalidateFilter()
        except AttributeError:
            # Fallback for newer Qt versions
            self.beginFilterChange()
            self.endFilterChange()
    
    def set_root_path(self, path: str):
        """Set the root path for filtering."""
        self.root_path = os.path.normpath(path)
        print(f"DEBUG: SearchFilterProxyModel.set_root_path called with path={path}, normalized={self.root_path}")
        # Invalidate filter to re-evaluate rows with new root path
        try:
            self.invalidateFilter()
        except AttributeError:
            # Fallback for newer Qt versions
            self.beginFilterChange()
            self.endFilterChange()
    
    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        """Check if row should be visible based on search text."""
        # If no search text, show all rows
        if not self.search_text:
            return True
        
        # Get the direct source model (ModInfoSortProxyModel)
        sort_proxy = self.sourceModel()
        
        # Create index in sort proxy space
        sort_proxy_index = sort_proxy.index(source_row, 0, source_parent)
        if not sort_proxy_index.isValid():
            return True
        
        # Map through sort proxy to reach the actual QFileSystemModel
        file_model_index = sort_proxy.mapToSource(sort_proxy_index)
        if not file_model_index.isValid():
            return True
        
        # Get the actual file system model
        file_system_model = sort_proxy.sourceModel()
        
        # Get file path from QFileSystemModel
        if not hasattr(file_system_model, 'filePath'):
            print(f"DEBUG: Model {file_system_model} doesn't have filePath method")
            return True
        
       
        file_path = file_system_model.filePath(file_model_index)
        print(f"DEBUG: Checking file_path={file_path}, search_text={self.search_text}")
        
        if not file_path:
            return True
        
        # Check if filename contains search text
        file_name = os.path.basename(file_path).lower()
        search_lower = self.search_text.lower()
        
        if search_lower in file_name:
            print(f"DEBUG: Name match! {file_name} contains {search_lower}")
            return True
        
        # Check if any tag contains search text
        if self.tag_manager:
            tags = self.tag_manager.get_tags(file_path)
            for tag in tags:
                if search_lower in tag.lower():
                    print(f"DEBUG: Tag match! {tag} contains {search_lower}")
                    return True
        
        return False


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


class FileManager(QMainWindow):
    """Main application window.

    - Left: `QTreeView` with directories
    - Right: `QListView` displaying files using `QFileSystemModel` and the
        `FileItemDelegate` for custom rendering.
    """
    def __init__(self, root_path: str):
        super().__init__()
        self.setWindowTitle("Simple PySide6 File Manager")
        self.resize(900, 600)
        
        # Initialize tag manager
        self.tag_manager = TagManager(root_path)

        # Models
        self.dir_model = QFileSystemModel()
        self.dir_model.setFilter(QDir.AllDirs | QDir.NoDotAndDotDot)
        self.dir_model.setRootPath(QDir.rootPath())

        self.file_model = QFileSystemModel()
        self.file_model.setFilter(QDir.AllEntries | QDir.NoDotAndDotDot)
        self.file_model.setRootPath(QDir.rootPath())

        # Views
        self.tree = QTreeView()
        self.tree.setModel(self.dir_model)
        self.tree.setRootIndex(self.dir_model.index(root_path))
        self.tree.setHeaderHidden(True)
        for i in range(1, 4):
            self.tree.hideColumn(i)

        self.list = QListView()
        self.list.setModel(self.file_model)
        self.list.setRootIndex(self.file_model.index(root_path))
        self.list.setViewMode(QListView.ListMode)
        
        # Apply custom sort proxy to sort by ModInfo.enabledName()
        self.proxy_model = ModInfoSortProxyModel()
        self.proxy_model.setSourceModel(self.file_model)
        self.proxy_model.setDynamicSortFilter(True)
        self.proxy_model.sort(0, Qt.AscendingOrder)
        
        # Apply search filter proxy on top of sort proxy
        self.search_proxy_model = SearchFilterProxyModel(self.tag_manager)
        self.search_proxy_model.setSourceModel(self.proxy_model)
        self.search_proxy_model.setDynamicSortFilter(True)
        
        self.list.setModel(self.search_proxy_model)
        self.list.setRootIndex(self.search_proxy_model.mapFromSource(self.proxy_model.mapFromSource(self.file_model.index(root_path))))
        
        # Use custom delegate to render each entry
        delegate = FileItemDelegate(self.list, self.tag_manager)
        delegate.file_manager = self  # Pass reference to FileManager for refresh
        self.list.setItemDelegate(delegate)
        self.list.setIconSize(QSize(48, 48))
        try:
            # spacing exists on QListView
            self.list.setSpacing(6)
        except Exception:
            pass

    
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.tree)
        splitter.addWidget(self.list)
        
        # Toolbar
        
        toolbar = QToolBar()
        # self.addToolBar(toolbar)


        back_action = QAction("Back", self)
        back_action.triggered.connect(self.go_up)
        toolbar.addAction(back_action)

        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(self.refresh)
        toolbar.addAction(refresh_action)

        new_folder_action = QAction("New Folder", self)
        new_folder_action.triggered.connect(self.create_folder)
        toolbar.addAction(new_folder_action)

        open_action = QAction("Open", self)
        open_action.triggered.connect(self.open_selected)
        toolbar.addAction(open_action)

        
        toolbar.addSeparator()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search by name or tag...")
        self.search_edit.setMaximumWidth(200)
        self.search_edit.textChanged.connect(self.on_search_text_changed)
        toolbar.addWidget(self.search_edit)


        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Path")
        self.path_edit.returnPressed.connect(self.goto_path)

        left_container = QSplitter(Qt.Vertical)
        left_container.addWidget(toolbar)
        left_container.addWidget(self.path_edit)
        left_container.addWidget(splitter)

        
        # Second independent file explorer on the right
        
        # Right view toolbar
        right_toolbar = QToolBar()
        right_back_action = QAction("Back", self)
        right_back_action.triggered.connect(self.right_go_up)
        right_toolbar.addAction(right_back_action)
        
        right_refresh_action = QAction("Refresh", self)
        right_refresh_action.triggered.connect(self.right_refresh)
        right_toolbar.addAction(right_refresh_action)
        
        right_new_folder_action = QAction("New Folder", self)
        right_new_folder_action.triggered.connect(self.create_folder)
        right_toolbar.addAction(right_new_folder_action)
        
        right_open_action = QAction("Open", self)
        right_open_action.triggered.connect(self.open_selected)
        right_toolbar.addAction(right_open_action)
        
        right_toolbar.addSeparator()
        self.right_path_edit = QLineEdit()
        self.right_path_edit.returnPressed.connect(self.right_goto_path)
        
        # Right view list
        self.right_file_model = QFileSystemModel()
        self.right_file_model.setFilter(QDir.AllEntries | QDir.NoDotAndDotDot)
        self.right_file_model.setRootPath(QDir.rootPath())
        
        self.right_list = QListView()
        self.right_list.setModel(self.right_file_model)
        
        # Apply custom sort proxy to right list
        self.right_proxy_model = ModInfoSortProxyModel()
        self.right_proxy_model.setSourceModel(self.right_file_model)
        self.right_proxy_model.setDynamicSortFilter(True)
        self.right_proxy_model.sort(0, Qt.AscendingOrder)
        
        self.right_list.setModel(self.right_proxy_model)
        
        # Right list delegate
        right_delegate = FileItemDelegate(self.right_list, self.tag_manager)
        right_delegate.file_manager = self
        self.right_list.setItemDelegate(right_delegate)
        self.right_list.setIconSize(QSize(48, 48))
        try:
            self.right_list.setSpacing(6)
        except Exception:
            pass
        
        # Right view history
        self.right_history = []
        self.right_history_index = -1
        
        # Right view connections
        self.right_list.doubleClicked.connect(self.right_on_list_double_clicked)
        
        # Track focus: ensure clicked list gets focused
        self.list.clicked.connect(lambda idx: self.set_focused_list(self.list))
        self.right_list.clicked.connect(lambda idx: self.set_focused_list(self.right_list))
        
        # Context menu for tagging
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self.show_context_menu)
        
        self.right_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.right_list.customContextMenuRequested.connect(self.show_context_menu)
        
        # Create right side container with toolbar and list
        right_container = QSplitter(Qt.Vertical)
        right_container.addWidget(right_toolbar)
        right_container.addWidget(self.right_path_edit)
        right_container.addWidget(self.right_list)
        # right_container.setSizes([30, 570])

        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.addWidget(left_container)
        main_splitter.addWidget(right_container)
        # main_splitter.setStretchFactor(1, 1)
        # main_splitter.setStretchFactor(2, 1)
        self.setCentralWidget(main_splitter)
        
        # Set right view initial path
        self.right_set_path(os.path.sep.join((root_path,".wip/.unzipzone")))

        # Navigation history
        self.history = []  # list of paths
        self.history_index = -1

        # Clipboard for cut/copy/paste
        self.clipboard_path = None
        self.clipboard_mode = None  # "cut" or "copy"
        self.focused_list = self.list  # Track which list is focused
        
        # Status bar for clipboard display
        self.status_bar = self.statusBar()
        self.clipboard_label = QLineEdit()
        self.clipboard_label.setReadOnly(True)
        self.clipboard_label.setText("Clipboard: empty")
        self.status_bar.addWidget(self.clipboard_label)

        # install event filter to catch mouse back/forward buttons
        self.list.viewport().installEventFilter(self)
        self.tree.viewport().installEventFilter(self)

        

        # Connections
        self.tree.selectionModel().currentChanged.connect(self.on_tree_selection_changed)
        self.list.doubleClicked.connect(self.on_list_double_clicked)
        
        # Track focus for cut/copy/paste
        self.list.focusWidget = lambda: setattr(self, 'focused_list', self.list) or self.list

        # Set initial path text
        self.set_path(root_path)

    def set_path(self, path: str, add_history: bool = True):
        """Set current path in views. If add_history is True, record in navigation history."""
        self.path_edit.setText(path)
        
        # Clear search when navigating to a new directory
        self.search_edit.blockSignals(True)
        self.search_edit.clear()
        self.search_edit.blockSignals(False)
        self.search_proxy_model.set_search_text("")
        
        # Update search proxy root path
        self.search_proxy_model.set_root_path(path)
        
        dir_index = self.file_model.index(path)
        tree_index = self.dir_model.index(path)
        if dir_index.isValid():
            # Map source index through both proxy models for the list
            sort_proxy_index = self.proxy_model.mapFromSource(dir_index)
            search_proxy_index = self.search_proxy_model.mapFromSource(sort_proxy_index)
            self.list.setRootIndex(search_proxy_index)
        if tree_index.isValid():
            self.tree.setCurrentIndex(tree_index)
        # update history
        if add_history:
            # if not at end, drop forward history
            if self.history_index < len(self.history) - 1:
                self.history = self.history[: self.history_index + 1]
            # avoid duplicate consecutive entries
            if not self.history or self.history[-1] != path:
                self.history.append(path)
                self.history_index = len(self.history) - 1

    def on_tree_selection_changed(self, current, previous):
        path = self.dir_model.filePath(current)
        if path:
            self.set_path(path, add_history=True)

    def on_list_double_clicked(self, index):
        # Map through both proxy models to get to source
        # index comes from search_proxy_model
        sort_proxy_index = self.search_proxy_model.mapToSource(index)
        source_index = self.proxy_model.mapToSource(sort_proxy_index)
        path = self.file_model.filePath(source_index)
        info = QFileInfo(path)
        if info.exists():
            # navigate into directories
            if info.isDir():
                self.set_path(path, add_history=True)
                return
        # try to open files with default app
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def goto_path(self):
        path = self.path_edit.text().strip()
        if not QDir(path).exists():
            QMessageBox.warning(self, "Not found", f"Path not found: {path}")
            return
        self.set_path(path)

    def go_up(self):
        current = self.path_edit.text()
        parent = QDir(current).absolutePath()
        qdir = QDir(parent)
        if qdir.cdUp():
            self.set_path(qdir.absolutePath(), add_history=True)

    def navigate_back(self):
        if self.history_index > 0:
            self.history_index -= 1
            path = self.history[self.history_index]
            self.set_path(path, add_history=False)

    def navigate_forward(self):
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            path = self.history[self.history_index]
            self.set_path(path, add_history=False)

    def eventFilter(self, watched, event):
        # catch XButton1/XButton2 on list/tree viewports
        if event.type() == QEvent.MouseButtonRelease:
            btn = event.button()
            if btn == Qt.XButton1:
                # Back button acts like "Back" toolbar button (cd ..)
                self.go_up()
                return True
            if btn == Qt.XButton2:
                # Forward button still uses navigation history
                self.navigate_forward()
                return True
        return super().eventFilter(watched, event)

    def refresh(self):
        # Refresh models by resetting root paths
        cur = self.path_edit.text()
        self.file_model.setRootPath("")
        self.dir_model.setRootPath("")
        self.file_model.setRootPath(cur)
        self.dir_model.setRootPath(cur)

    def create_folder(self):
        """Create a new folder in the focused panel's current directory."""
        # Determine which panel is focused
        if self.list.hasFocus() or self.focused_list == self.list:
            path = self.path_edit.text()
        elif self.right_list.hasFocus():
            path = self.right_path_edit.text()
        else:
            path = self.path_edit.text()
        
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if not ok or not name:
            return
        new_path = QDir(path).filePath(name)
        qdir = QDir()
        if not qdir.mkdir(new_path):
            QMessageBox.warning(self, "Error", f"Could not create folder: {new_path}")
        else:
            self.refresh()
            self.right_refresh()

    def delete_selected(self):
        """Delete selected file/folder from focused view."""
        # Determine which list is focused
        if self.list.hasFocus() or self.focused_list == self.list:
            index = self.list.currentIndex()
            # Map through nested proxy models for central view
            current_index = index
            current_model = self.search_proxy_model
            while isinstance(current_model, QSortFilterProxyModel):
                current_index = current_model.mapToSource(current_index)
                current_model = current_model.sourceModel()
            path = current_model.filePath(current_index)
        elif self.right_list.hasFocus():
            index = self.right_list.currentIndex()
            current_index = index
            current_model = self.right_proxy_model
            while isinstance(current_model, QSortFilterProxyModel):
                current_index = current_model.mapToSource(current_index)
                current_model = current_model.sourceModel()
            path = current_model.filePath(current_index)
        else:
            return
        
        if not index.isValid():
            return
        
        if not path or path == QDir.rootPath():
            return
        
        ok = QMessageBox.question(self, "Delete", f"Delete {path}?", QMessageBox.Yes | QMessageBox.No)
        if ok == QMessageBox.Yes:
            info = QFileInfo(path)
            if info.isDir():
                qdir = QDir()
                if not qdir.rmdir(path):
                    QMessageBox.warning(self, "Error", "Could not remove directory (must be empty)")
            else:
                import os

                try:
                    os.remove(path)
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Could not remove file: {e}")
            self.refresh()
            self.right_refresh()

    def open_selected(self):
        """Open selected file/folder from focused view."""
        # Determine which list is focused
        if self.list.hasFocus() or self.focused_list == self.list:
            index = self.list.currentIndex()
            # Map through nested proxy models for central view
            current_index = index
            current_model = self.search_proxy_model
            while isinstance(current_model, QSortFilterProxyModel):
                current_index = current_model.mapToSource(current_index)
                current_model = current_model.sourceModel()
            path = current_model.filePath(current_index)
        elif self.right_list.hasFocus():
            index = self.right_list.currentIndex()
            current_index = index
            current_model = self.right_proxy_model
            while isinstance(current_model, QSortFilterProxyModel):
                current_index = current_model.mapToSource(current_index)
                current_model = current_model.sourceModel()
            path = current_model.filePath(current_index)
        else:
            return
        
        if not index.isValid():
            return
        
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def cut_selected(self):
        """Cut selected file/folder from focused view."""
        # Determine which list is focused
        if self.list.hasFocus() or self.focused_list == self.list:
            index = self.list.currentIndex()
            # Map through nested proxy models for central view
            current_index = index
            current_model = self.search_proxy_model
            while isinstance(current_model, QSortFilterProxyModel):
                current_index = current_model.mapToSource(current_index)
                current_model = current_model.sourceModel()
            path = current_model.filePath(current_index)
        elif self.right_list.hasFocus():
            index = self.right_list.currentIndex()
            current_index = index
            current_model = self.right_proxy_model
            while isinstance(current_model, QSortFilterProxyModel):
                current_index = current_model.mapToSource(current_index)
                current_model = current_model.sourceModel()
            path = current_model.filePath(current_index)
        else:
            return
        
        if not index.isValid():
            return
        
        # Verify we got a file/folder, not a directory root
        if not path or path == QDir.rootPath():
            return
        
        self.clipboard_path = path
        self.clipboard_mode = "cut"
        file_name = QFileInfo(path).fileName()
        self.update_clipboard_display()

    def copy_selected(self):
        """Copy selected file/folder from focused view."""
        # Determine which list is focused
        if self.list.hasFocus() or self.focused_list == self.list:
            index = self.list.currentIndex()
            # Map through nested proxy models for central view
            current_index = index
            current_model = self.search_proxy_model
            while isinstance(current_model, QSortFilterProxyModel):
                current_index = current_model.mapToSource(current_index)
                current_model = current_model.sourceModel()
            path = current_model.filePath(current_index)
        elif self.right_list.hasFocus():
            index = self.right_list.currentIndex()
            current_index = index
            current_model = self.right_proxy_model
            while isinstance(current_model, QSortFilterProxyModel):
                current_index = current_model.mapToSource(current_index)
                current_model = current_model.sourceModel()
            path = current_model.filePath(current_index)
        else:
            return
        
        if not index.isValid():
            return
        
        # Verify we got a file/folder, not a directory root
        if not path or path == QDir.rootPath():
            return
        
        self.clipboard_path = path
        self.clipboard_mode = "copy"
        file_name = QFileInfo(path).fileName()
        self.update_clipboard_display()

    def paste_selected(self):
        """Paste (move or copy) file/folder to focused panel's current directory."""
        if not self.clipboard_path or not self.clipboard_mode:
            QMessageBox.warning(self, "Paste", "Nothing in clipboard")
            return
        
        # Determine which list is focused for destination
        if self.list.hasFocus() or self.focused_list == self.list:
            current_path = self.path_edit.text().strip()
        elif self.right_list.hasFocus():
            current_path = self.right_path_edit.text().strip()
        else:
            QMessageBox.information(self, "Paste", "No panel focused")
            return
        
        file_info = QFileInfo(self.clipboard_path)
        
        if not file_info.exists():
            QMessageBox.warning(self, "Paste", f"Source no longer exists: {self.clipboard_path}")
            self.clipboard_path = None
            self.update_clipboard_display()
            return
        
        dest_path = QDir(current_path).filePath(file_info.fileName())
        
        # Avoid pasting to same location
        if os.path.normpath(self.clipboard_path) == os.path.normpath(dest_path):
            QMessageBox.warning(self, "Paste", "Source and destination are the same")
            return
        
        try:
            if self.clipboard_mode == "cut":
                os.rename(self.clipboard_path, dest_path)
                print(f"Moved: {self.clipboard_path} -> {dest_path}")
                self.clipboard_path = None  # Clear clipboard after cut
                self.clipboard_mode = None
            else:  # copy
                import shutil
                if file_info.isDir():
                    shutil.copytree(self.clipboard_path, dest_path)
                else:
                    shutil.copy2(self.clipboard_path, dest_path)
                print(f"Copied: {self.clipboard_path} -> {dest_path}")
            self.refresh()
            self.right_refresh()
            self.update_clipboard_display()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Paste failed: {e}")

    def update_clipboard_display(self):
        """Update the clipboard status bar display."""
        if not self.clipboard_path:
            self.clipboard_label.setText("Clipboard: empty")
        else:
            file_name = QFileInfo(self.clipboard_path).fileName()
            mode = self.clipboard_mode.upper()
            self.clipboard_label.setText(f"Clipboard: [{mode}] {file_name}")

    def set_focused_list(self, list_view):
        """Track which list view is focused."""
        self.focused_list = list_view

    # Right view methods (independent explorer)
    def right_set_path(self, path: str, add_history: bool = True):
        """Set path for right view."""
        self.right_path_edit.setText(path)
        dir_index = self.right_file_model.index(path)
        if dir_index.isValid():
            proxy_index = self.right_proxy_model.mapFromSource(dir_index)
            self.right_list.setRootIndex(proxy_index)
        # update history
        if add_history:
            if self.right_history_index < len(self.right_history) - 1:
                self.right_history = self.right_history[: self.right_history_index + 1]
            if not self.right_history or self.right_history[-1] != path:
                self.right_history.append(path)
                self.right_history_index = len(self.right_history) - 1

    def right_on_list_double_clicked(self, index):
        """Handle double-click in right view."""
        source_index = self.right_proxy_model.mapToSource(index)
        path = self.right_file_model.filePath(source_index)
        info = QFileInfo(path)
        if info.exists():
            if info.isDir():
                self.right_set_path(path, add_history=True)
                return
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def right_goto_path(self):
        """Handle path entry in right view."""
        path = self.right_path_edit.text().strip()
        if not QDir(path).exists():
            QMessageBox.warning(self, "Not found", f"Path not found: {path}")
            return
        self.right_set_path(path, add_history=True)

    def right_go_up(self):
        """Go up one directory in right view."""
        current = self.right_path_edit.text()
        parent = QDir(current).absolutePath()
        qdir = QDir(parent)
        if qdir.cdUp():
            self.right_set_path(qdir.absolutePath(), add_history=True)

    def right_refresh(self):
        """Refresh right view."""
        cur = self.right_path_edit.text()
        self.right_file_model.setRootPath("")
        self.right_file_model.setRootPath(cur)

    def on_search_text_changed(self, text: str):
        """Handle search text changes."""
        self.search_proxy_model.set_search_text(text)

    def show_context_menu(self, position):
        """Show context menu for tag management and file operations."""
        # Determine which list triggered the menu
        sender = self.sender()
        if sender == self.list:
            index = self.list.indexAt(position)
            model = self.search_proxy_model
            source_model = self.file_model
        elif sender == self.right_list:
            index = self.right_list.indexAt(position)
            model = self.right_proxy_model
            source_model = self.right_file_model
        else:
            return
        
        if not index.isValid():
            return
        
        # Map from search proxy -> sort proxy -> file model
        if sender == self.list:
            sort_proxy_index = self.search_proxy_model.mapToSource(index)
            source_index = self.proxy_model.mapToSource(sort_proxy_index)
        else:
            source_index = model.mapToSource(index)
        
        file_path = source_model.filePath(source_index)
        
        menu = QMenu(self)
        
        # File operations
        cut_action = menu.addAction("Cut")
        cut_action.triggered.connect(self.cut_selected)
        
        copy_action = menu.addAction("Copy")
        copy_action.triggered.connect(self.copy_selected)
        
        paste_action = menu.addAction("Paste")
        paste_action.triggered.connect(self.paste_selected)
        
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(self.delete_selected)
        
        menu.addSeparator()
        
        # Tag management
        add_tag_action = menu.addAction("Add Tag")
        add_tag_action.triggered.connect(lambda: self.add_tag_dialog(file_path))
        
        # Show existing tags with remove option
        tags = self.tag_manager.get_tags(file_path)
        if tags:
            menu.addSeparator()
            for tag in tags:
                remove_action = menu.addAction(f"Remove: {tag}")
                remove_action.triggered.connect(lambda checked=False, t=tag: self.tag_manager.remove_tag(file_path, t))
            
            # Add "Remove all tags" option
            remove_all_action = menu.addAction("Remove all tags")
            remove_all_action.triggered.connect(lambda: self.remove_all_tags_from_file(file_path))
        
        menu.exec(sender.mapToGlobal(position))
        self.refresh()
        self.right_refresh()

    def remove_all_tags_from_file(self, file_path: str):
        """Remove all tags from a file/folder."""
        self.tag_manager.set_tags(file_path, [])
        self.refresh()
        self.right_refresh()

    def add_tag_dialog(self, file_path: str):
        """Show dialog to add a tag."""
        tag, ok = QInputDialog.getText(self, "Add Tag", "Enter tag name:")
        if ok and tag:
            self.tag_manager.add_tag(file_path, tag)
            self.refresh()
            self.right_refresh()


def main():
    app = QApplication(sys.argv)
    win = FileManager("C:/Users/Gnathon/XXMI Launcher/ZZMI/Mods")
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__": main()
