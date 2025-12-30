"""pytrekgen - Python-based code generator for trekker lab checkers."""

__version__ = "0.1"

from .config import LabConfig
from .generator import Generator

__all__ = ["Generator", "LabConfig", "__version__"]
