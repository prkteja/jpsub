"""Where jpsub keeps its downloaded models and dictionary."""
import os
from pathlib import Path


def data_dir():
    """$JPSUB_DATA_DIR, or $XDG_DATA_HOME/jpsub (usually ~/.local/share/jpsub)."""
    override = os.environ.get("JPSUB_DATA_DIR")
    if override:
        return Path(override).expanduser()
    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / "jpsub"


def models_dir():
    return data_dir() / "models"


def dictionary_path():
    return data_dir() / "jmdict.sqlite"
