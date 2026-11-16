"""Read-only Phase 6A dataset manifest and dependency audit.

The audit intentionally does not import TensorFlow, ``waymo_open_dataset`` or
``av2`` at module import time, and it never writes inside a dataset root.  A
missing optional parser is reported as ``SKIP`` rather than being converted to
a false validation success.  Full record parsing is a subsequent adapter
milestone; this module establishes deterministic split/file contracts first.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class AuditIssue:
    code: str
    message: str
    severity: str = "ERROR"

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class FileEntry:
    relative_path: str
    size_bytes: int
    kind: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SplitAudit:
    dataset: str
    requested_split: str
    resolved_split: Optional[str]
    root: str
    exists: bool
    file_count: int
    total_bytes: int
    files: tuple[FileEntry, ...]
    manifest_digest: str
    parser_dependency: str
    parser_available: bool
    future_labels_available: Optional[bool]
    issues: tuple[AuditIssue, ...] = ()

    @property
    def status(self) -> str:
        if any(issue.severity == "ERROR" for issue in self.issues):
            return "ERROR"
        if not self.exists or not self.parser_available:
            return "SKIP"
        return "PASS"

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["files"] = [x.to_dict() for x in self.files]
        out["issues"] = [x.to_dict() for x in self.issues]
        out["status"] = self.status
        return out


@dataclass(frozen=True)
class DatasetAuditReport:
    schema: str
    generated_by: str
    splits: tuple[SplitAudit, ...]
    config_digest: str = ""
    notes: tuple[str, ...] = ()

    @property
    def status(self) -> str:
        if any(x.status == "ERROR" for x in self.splits):
            return "ERROR"
        if any(x.status == "SKIP" for x in self.splits):
            return "SKIP"
        return "PASS"

    def to_dict(self) -> dict[str, Any]:
        return {"schema": self.schema, "generated_by": self.generated_by,
                "status": self.status, "config_digest": self.config_digest,
                "splits": [x.to_dict() for x in self.splits],
                "notes": list(self.notes)}


def _digest_entries(entries: list[FileEntry]) -> str:
    payload = "\n".join(f"{x.kind}\t{x.relative_path}\t{x.size_bytes}" for x in entries)
    return "manifest-sha256:" + hashlib.sha256(payload.encode()).hexdigest()


def _config_digest(config: Mapping[str, Any]) -> str:
    raw = json.dumps(config, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=True, allow_nan=False).encode()
    return "config-sha256:" + hashlib.sha256(raw).hexdigest()


def _dependency_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _resolve_child(root: Path, names: list[str]) -> tuple[Optional[Path], Optional[str]]:
    if not root.is_dir():
        return None, None
    children = {p.name.casefold(): p for p in root.iterdir() if p.is_dir()}
    for name in names:
        path = children.get(name.casefold())
        if path is not None:
            return path, path.name
    return None, None


def _entries(path: Optional[Path], predicate) -> tuple[FileEntry, ...]:
    rows: list[FileEntry] = []
    if path is None or not path.is_dir():
        return ()
    for item in sorted(path.rglob("*")):
        if item.is_file() and predicate(item):
            rows.append(FileEntry(item.relative_to(path).as_posix(), item.stat().st_size,
                                  item.suffix.lower() or "<no_suffix>"))
    return tuple(rows)


def _base_audit(dataset: str, requested_split: str, root: Path,
                resolved: Optional[Path], resolved_name: Optional[str],
                files: tuple[FileEntry, ...], dependency: str,
                dependency_module: str, future_labels: Optional[bool],
                issues: list[AuditIssue], max_files: int) -> SplitAudit:
    if resolved is None:
        issues.append(AuditIssue("SPLIT_PATH_MISSING",
                                 f"{dataset} split {requested_split!r} not found below {root}",
                                 "INFO"))
    elif not files:
        issues.append(AuditIssue("NO_CANDIDATE_FILES",
                                 f"no candidate files found in {resolved}"))
    if not _dependency_available(dependency_module):
        issues.append(AuditIssue("OPTIONAL_DEPENDENCY_MISSING",
                                 f"parser dependency {dependency!r} is not installed", "INFO"))
    shown = files[:max_files]
    return SplitAudit(dataset, requested_split, resolved_name, str(root), resolved is not None,
                      len(files), sum(x.size_bytes for x in files), shown,
                      _digest_entries(list(files)), dependency,
                      _dependency_available(dependency_module), future_labels, tuple(issues))


def audit_womd_scenario_root(root: str | Path, split: str = "validation",
                             *, max_files: int = 10) -> SplitAudit:
    """Audit a WOMD ``.../uncompressed/scenario`` directory without parsing records."""
    root_path = Path(root).expanduser()
    candidates = {"training": ["training"], "validation": ["validation"],
                  "testing": ["testing"], "training_20s": ["training_20s"],
                  "validation_interactive": ["validation_interactive"]}
    resolved, name = _resolve_child(root_path, candidates.get(split, [split]))
    files = _entries(resolved, lambda p: p.name.endswith(".tfrecord") or ".tfrecord-" in p.name)
    issues: list[AuditIssue] = []
    if split == "testing":
        future = False
        issues.append(AuditIssue("TEST_FUTURE_LABELS_UNAVAILABLE",
                                 "WOMD testing is treated as future-label unavailable", "INFO"))
    else:
        future = True
    return _base_audit("womd_scenario", split, root_path, resolved, name, files,
                       "waymo_open_dataset scenario protobuf", "waymo_open_dataset",
                       future, issues, max_files)


def _av2_pair_issues(path: Path, files: tuple[FileEntry, ...]) -> list[AuditIssue]:
    parquet_ids = {Path(x.relative_path).stem.removeprefix("scenario_") for x in files
                   if x.kind == ".parquet"}
    map_files = [x for x in files if x.kind == ".json" and "map" in x.relative_path.lower()]
    map_ids = {Path(x.relative_path).stem.removeprefix("log_map_archive_") for x in map_files}
    # A map archive may be shared by many scenarios.  A missing map is an
    # error only when map JSONs are present in the split; an empty map set is a
    # read-only layout warning, not proof that the scenario is invalid.
    if map_files:
        missing = sorted(parquet_ids - map_ids)
        if missing:
            return [AuditIssue("SCENARIO_MAP_UNPAIRED",
                               f"{len(missing)} parquet scenario ids have no matching map JSON")]
    return []


def audit_av2_motion_root(root: str | Path, split: str = "validation",
                          *, max_files: int = 10) -> SplitAudit:
    """Audit AV2 Motion parquet/map pairing; the official reader is optional."""
    root_path = Path(root).expanduser()
    aliases = {"train": ["train", "Train"], "validation": ["validation", "val", "Validation"],
               "test": ["test", "Test"]}
    resolved, name = _resolve_child(root_path, aliases.get(split, [split]))
    files = _entries(resolved, lambda p: p.suffix.lower() in {".parquet", ".json"})
    issues = _av2_pair_issues(resolved, files) if resolved else []
    if split == "test":
        future = False
        issues.append(AuditIssue("TEST_FUTURE_LABELS_UNAVAILABLE",
                                 "AV2 test is scored with withheld future labels", "INFO"))
    else:
        future = True
    return _base_audit("av2_motion", split, root_path, resolved, name, files,
                       "av2 official parquet/map reader", "av2", future,
                       issues, max_files)


def audit_from_config(config: Mapping[str, Any], *, max_files: int = 10,
                      include_optional_map_change: bool = False) -> DatasetAuditReport:
    """Build a deterministic report from the documented path configuration."""
    splits: list[SplitAudit] = []
    womd = config.get("womd", {})
    configured_womd_root = Path(womd.get("root", ""))
    scenario_root = (configured_womd_root if configured_womd_root.name.casefold() == "scenario"
                     else configured_womd_root / "scenario")
    for split in ("validation", "training", "testing"):
        splits.append(audit_womd_scenario_root(scenario_root, split, max_files=max_files))
    av2 = config.get("argoverse2_motion", {})
    av2_root = Path(av2.get("root", ""))
    for split in ("validation", "train", "test"):
        splits.append(audit_av2_motion_root(av2_root, split, max_files=max_files))
    notes = ["read_only_manifest_audit", "no_record_parser_invoked"]
    if not include_optional_map_change:
        notes.append("map_change_root_not_required_for_motion_phase6a")
    return DatasetAuditReport("rampd.phase6a.dataset-audit.v1", "rampd_core.dataset_audit",
                              tuple(splits), _config_digest(config), tuple(notes))


__all__ = ["AuditIssue", "FileEntry", "SplitAudit", "DatasetAuditReport",
           "audit_womd_scenario_root", "audit_av2_motion_root", "audit_from_config"]

