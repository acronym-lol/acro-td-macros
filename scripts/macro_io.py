"""
macro_io.py

Handles file and folder I/O operations for macros.
"""

import os
import shutil
import traceback
from json import loads, dumps
from typing import Optional, Dict

# Runtime-only keys: kept in memory for the UI but never written to data.json,
# so firing a macro doesn't dirty the file in git.
TRANSIENT_KEYS = ('log', 'errors')


def load_macro_data(file_path: str) -> Optional[Dict]:
    """Load and parse macro JSON data from a file."""
    try:
        with open(file_path, 'r') as f:
            return loads(f.read())
    except Exception:
        print(f"Error loading macro data from {file_path}: {traceback.format_exc()}")
        return None


def write_macro_data(file_path: str, data: Dict) -> None:
    """Write macro JSON data to a file, ensuring the directory exists."""
    directory = os.path.dirname(file_path)
    os.makedirs(directory, exist_ok=True)
    data = {k: v for k, v in data.items() if k not in TRANSIENT_KEYS}
    try:
        with open(file_path, 'w') as f:
            f.write(dumps(data, indent=4))
    except Exception:
        print(f"Error writing macro data to {file_path}: {traceback.format_exc()}")


def create_macro_folder_and_data(folder_path: str, macro_data: Dict) -> None:
    """
    Create a folder for the macro (if it doesn't exist) and write its data.json file.
    """
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    file_path = os.path.join(folder_path, 'data.json')
    write_macro_data(file_path, macro_data)


def delete_folder(folder_path: str) -> None:
    """
    Delete a folder and all its contents.
    """
    if os.path.exists(folder_path):
        try:
            shutil.rmtree(folder_path)
        except Exception:
            print(f"Error deleting folder {folder_path}: {traceback.format_exc()}")
