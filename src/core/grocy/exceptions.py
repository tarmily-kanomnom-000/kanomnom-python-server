from __future__ import annotations


class MetadataNotFoundError(FileNotFoundError):
    """Raised when a metadata.yaml file for an instance is missing."""


class ManifestNotFoundError(FileNotFoundError):
    """Raised when the universal manifest directory cannot be located."""
