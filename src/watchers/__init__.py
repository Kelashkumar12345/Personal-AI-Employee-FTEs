__all__ = ["BaseWatcher", "GmailWatcher", "FilesystemWatcher"]


def __getattr__(name: str):
    if name == "BaseWatcher":
        from .base_watcher import BaseWatcher
        return BaseWatcher
    if name == "GmailWatcher":
        from .gmail_watcher import GmailWatcher
        return GmailWatcher
    if name == "FilesystemWatcher":
        from .filesystem_watcher import FilesystemWatcher
        return FilesystemWatcher
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
