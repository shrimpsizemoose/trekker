"""pytrekgen - Python-based code generator for trekker lab checkers."""

__version__ = "8.1"

from .config import LabConfig
from .generator import Generator

__all__ = ["Generator", "LabConfig", "__version__"]
