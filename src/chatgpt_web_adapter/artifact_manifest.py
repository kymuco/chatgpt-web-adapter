from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

ARTIFACT_MANIFEST_SCHEMA = 1
SNAPSHOT_ARTIFACT_KIND = "conversation_snapshot"
EXPORT_ARTIFACT_KIND = "conversation_export"
SNAPSHOT_CONTRACT = "curated_current_branch_context_v1"
EXPORT_CONTRACT = "normalized_current_branch_export_v1"


@dataclass(frozen=True)
class ArtifactFileEntry:
    role: str
    path: str
    media_type: str
    bytes: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "path": self.path,
            "media_type": self.media_type,
            "bytes": self.bytes,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class StableArtifactManifest:
    artifact_kind: str
    contract: str
    conversation_id: str
    index: int
    files: tuple[ArtifactFileEntry, ...]
    format: str | None = None
    schema: int = ARTIFACT_MANIFEST_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "artifact_kind": self.artifact_kind,
            "contract": self.contract,
            "conversation_id": self.conversation_id,
            "index": self.index,
            "format": self.format,
            "files": [entry.to_dict() for entry in self.files],
        }


def artifact_file_entry(
    path: str | Path,
    *,
    role: str,
    media_type: str,
) -> ArtifactFileEntry:
    artifact_path = Path(path)
    payload = artifact_path.read_bytes()
    return ArtifactFileEntry(
        role=role,
        path=artifact_path.name,
        media_type=media_type,
        bytes=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
    )


def build_artifact_manifest(
    *,
    artifact_kind: str,
    contract: str,
    conversation_id: str,
    index: int,
    files: Iterable[ArtifactFileEntry],
    format: str | None = None,
) -> StableArtifactManifest:
    normalized_files = tuple(files)
    if not normalized_files:
        raise ValueError("artifact manifest must contain at least one file")
    if not isinstance(index, int) or isinstance(index, bool) or index <= 0:
        raise ValueError("artifact manifest index must be a positive integer")
    if not isinstance(conversation_id, str) or not conversation_id.strip():
        raise ValueError("artifact manifest conversation_id is required")
    if not isinstance(artifact_kind, str) or not artifact_kind.strip():
        raise ValueError("artifact manifest artifact_kind is required")
    if not isinstance(contract, str) or not contract.strip():
        raise ValueError("artifact manifest contract is required")
    return StableArtifactManifest(
        artifact_kind=artifact_kind.strip(),
        contract=contract.strip(),
        conversation_id=conversation_id.strip(),
        index=index,
        files=normalized_files,
        format=format.strip().lower() if isinstance(format, str) and format.strip() else None,
    )


def render_artifact_manifest(manifest: StableArtifactManifest) -> str:
    return json.dumps(
        manifest.to_dict(),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def write_artifact_manifest(
    path: str | Path,
    manifest: StableArtifactManifest,
) -> Path:
    manifest_path = Path(path)
    if manifest_path.exists():
        raise FileExistsError(f"artifact manifest already exists: {manifest_path}")
    manifest_path.write_text(
        render_artifact_manifest(manifest),
        encoding="utf-8",
        newline="\n",
    )
    return manifest_path
