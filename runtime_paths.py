"""Shared resource and writable-data paths for source and packaged runs."""
import os
from pathlib import Path
import sys


def resource_root():
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def data_root():
    if getattr(sys, 'frozen', False):
        base = Path(os.environ.get('LOCALAPPDATA', Path.home()))
        return base / 'LittleP'
    return resource_root() / 'output'
