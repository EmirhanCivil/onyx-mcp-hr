"""In-memory dataframe registry used to avoid sending raw Excel data to the LLM."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from app.core.exceptions import FileNotRegisteredError


@dataclass
class RegisteredFile:
    file_id: str
    path: str
    name: str
    rows: int
    columns: list[str]
    dtypes: dict[str, str]
    file_hash: str
    loaded_at: str
    tags: dict[str, str] = field(default_factory=dict)


class FileRegistry:
    """Keeps loaded DataFrames inside the MCP process and exposes only file IDs."""

    def __init__(self) -> None:
        self._frames: dict[str, pd.DataFrame] = {}
        self._meta: dict[str, RegisteredFile] = {}
        self._path_index: dict[str, str] = {}
        self._hash_index: dict[str, str] = {}
        self._variant_index: dict[str, str] = {}

    def register(
        self,
        path: str,
        df: pd.DataFrame,
        tags: dict[str, str] | None = None,
        replace: bool = False,
        variant: str | None = None,
    ) -> RegisteredFile:
        resolved_path = str(Path(path).resolve())
        base_hash = self._hash_path(path)
        variant_key = (variant or "").strip()
        variant_index_key = f"{resolved_path}||{variant_key}" if variant_key else ""
        file_hash = base_hash if not variant_key else hashlib.sha256(f"{base_hash}|{variant_key}".encode("utf-8")).hexdigest()

        existing_id = None
        if variant_key:
            existing_id = self._variant_index.get(variant_index_key) or self._hash_index.get(file_hash)
        else:
            existing_id = self._path_index.get(resolved_path) or self._hash_index.get(file_hash)

        # If the same path is re-registered but the content hash changed, replace automatically.
        if existing_id and not replace:
            existing = self._meta.get(existing_id)
            if existing and existing.path == resolved_path and existing.file_hash != file_hash:
                replace = True
            else:
                if tags and existing:
                    existing.tags.update(tags)
                return existing  # type: ignore[return-value]

        file_id = existing_id or str(uuid.uuid4())
        meta = RegisteredFile(
            file_id=file_id,
            path=resolved_path,
            name=Path(path).name,
            rows=int(len(df)),
            columns=[str(c) for c in df.columns],
            dtypes={str(k): str(v) for k, v in df.dtypes.items()},
            file_hash=file_hash,
            loaded_at=datetime.now(timezone.utc).isoformat(),
            tags=tags or {},
        )
        self._frames[file_id] = df
        self._meta[file_id] = meta
        if variant_key:
            self._variant_index[variant_index_key] = file_id
        else:
            self._path_index[resolved_path] = file_id
        self._hash_index[file_hash] = file_id
        return meta

    def get_frame(self, file_id: str) -> pd.DataFrame:
        if file_id not in self._frames:
            raise FileNotRegisteredError(f"Yüklü dosya bulunamadı: {file_id}")
        return self._frames[file_id]

    def get_meta(self, file_id: str) -> RegisteredFile:
        if file_id not in self._meta:
            raise FileNotRegisteredError(f"Yüklü dosya bulunamadı: {file_id}")
        return self._meta[file_id]

    def list_files(self) -> list[RegisteredFile]:
        return list(self._meta.values())

    def clear(self, file_id: str | None = None) -> int:
        if file_id:
            existed = file_id in self._frames
            meta = self._meta.get(file_id)
            self._frames.pop(file_id, None)
            self._meta.pop(file_id, None)
            if meta:
                # path_index is only for base variants; variants are stored in _variant_index.
                self._path_index.pop(meta.path, None)
                # purge possible variant index entries
                for key, value in list(self._variant_index.items()):
                    if value == file_id:
                        self._variant_index.pop(key, None)
                self._hash_index.pop(meta.file_hash, None)
            return 1 if existed else 0
        count = len(self._frames)
        self._frames.clear()
        self._meta.clear()
        self._path_index.clear()
        self._hash_index.clear()
        self._variant_index.clear()
        return count

    def prune_missing(self, valid_paths: set[str], roots: list[str]) -> int:
        """Remove registered files under managed roots when they no longer exist on disk."""

        valid = {str(Path(path).resolve()) for path in valid_paths}
        resolved_roots = [Path(root).resolve() for root in roots]
        removed = 0
        for file_id, meta in list(self._meta.items()):
            path = Path(meta.path).resolve()
            managed = any(path == root or root in path.parents for root in resolved_roots)
            if managed and str(path) not in valid:
                self.clear(file_id)
                removed += 1
        return removed

    @staticmethod
    def _hash_path(path: str) -> str:
        if not Path(path).exists():
            return hashlib.sha256(path.encode("utf-8")).hexdigest()
        h = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()


file_registry = FileRegistry()
