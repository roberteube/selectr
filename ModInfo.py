import os

from PySide6.QtCore import QFileInfo, QDir

class ModInfo(QFileInfo):

    def isDisabled(self):
        return self.fileName().lower().startswith("disabled")
    
    def toggle(self):
        old_path = self.filePath()
        old_name = self.fileName()
        new_name = old_name[8:].strip("_") if self.isDisabled() else f"DISABLED_{old_name}"
        new_path = QDir(self.absolutePath()).filePath(new_name)

        try:
            os.rename(old_path, new_path)
        except:
            print("couldn't rename, idk why")

    def enabledName(self):
        return self.fileName()[8 if self.isDisabled() else 0:].strip("_")