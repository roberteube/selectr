import os

from PySide6.QtCore import QSortFilterProxyModel

from ModInfo import ModInfo
from TagManager import TagManager


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