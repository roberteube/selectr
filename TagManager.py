import os
import json

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