"""Abstract base class for all per-format document converters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from document2markdown.document_model import ConversionResult


class BaseConverter(ABC):
    """All format-specific converters must implement this interface."""

    @abstractmethod
    def convert(self, source_path: Path) -> ConversionResult:
        """Convert *source_path* to an intermediate ConversionResult.

        Parameters
        ----------
        source_path:
            Absolute or relative path to the source document.

        Returns
        -------
        ConversionResult
            Ordered blocks, embedded assets, and any non-fatal warnings
            encountered during conversion.
        """
