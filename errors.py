"""Custom exception types for document2markdown."""

from __future__ import annotations

from pathlib import Path


class UnsupportedFormatError(Exception):
    """Raised when a file's format is not supported or cannot be determined.

    Attributes
    ----------
    file_path:
        Path to the file that triggered the error.
    detected_type:
        The type string that was detected (extension-derived or magic-byte),
        or *None* if the type could not be determined at all.
    """

    def __init__(self, file_path: Path | str, detected_type: str | None = None) -> None:
        self.file_path = Path(file_path)
        self.detected_type = detected_type
        reason = (
            f"unsupported format '{detected_type}'"
            if detected_type
            else "file type could not be determined"
        )
        super().__init__(f"ERROR: {self.file_path}: {reason}")


class MimeExtensionMismatchError(UnsupportedFormatError):
    """Raised when the file extension and magic-byte MIME type disagree.

    This is a subclass of :class:`UnsupportedFormatError` so callers that
    only care about "unsupported" can catch the parent class.

    Attributes
    ----------
    extension_type:
        The MIME type implied by the file extension.
    magic_type:
        The MIME type detected via magic-byte inspection.
    """

    def __init__(
        self,
        file_path: Path | str,
        extension_type: str,
        magic_type: str,
    ) -> None:
        self.file_path = Path(file_path)
        self.extension_type = extension_type
        self.magic_type = magic_type
        # Bypass UnsupportedFormatError.__init__ to set a custom message.
        Exception.__init__(
            self,
            f"ERROR: {self.file_path}: extension implies '{extension_type}' "
            f"but magic bytes indicate '{magic_type}'",
        )
        # Keep detected_type consistent with the parent interface.
        self.detected_type = magic_type


class ParseError(Exception):
    """Raised when a source document cannot be parsed.

    Attributes
    ----------
    file_path:
        Path to the file that could not be parsed.
    reason:
        Human-readable description of why parsing failed.
    """

    def __init__(self, file_path: Path | str, reason: str) -> None:
        self.file_path = Path(file_path)
        self.reason = reason
        super().__init__(f"ERROR: {self.file_path}: {reason}")
