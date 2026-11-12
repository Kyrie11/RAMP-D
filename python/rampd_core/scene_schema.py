"""Dataset-independent scene contracts for Phase 6.

The adapters deliberately produce a small, immutable representation.  It keeps
the source identity, time axis and validity masks alongside numeric states so
that an online model cannot accidentally consume future labels.  This module
has no TensorFlow, parquet, Waymo or Argoverse dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from typing import Any, Mapping, Optional


def _finite(value: float) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _canon(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _canon(value[k]) for k in sorted(value, key=str)}
    if isinstance(value, (tuple, list)):
        return [_canon(v) for v in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite value cannot enter a scene digest")
        return format(value, ".17g")
    if hasattr(value, "to_dict"):
        return _canon(value.to_dict())
    return value


@dataclass(frozen=True)
class SceneManifest:
    dataset: str
    dataset_version: str
    split: str
    scenario_id: str
    source_file: str
    timestamps: tuple[float, ...]
    current_time_index: int
    coordinate_frame: str
    position_reference: str
    future_available: bool
    sample_rate_hz: Optional[float] = None
    source_digest: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        for name in ("dataset", "dataset_version", "split", "scenario_id", "source_file",
                     "coordinate_frame", "position_reference"):
            if not getattr(self, name):
                errors.append(f"{name}:empty")
        if not self.timestamps:
            errors.append("timestamps:empty")
        elif any(not _finite(t) for t in self.timestamps):
            errors.append("timestamps:non_finite")
        elif any(b <= a for a, b in zip(self.timestamps, self.timestamps[1:])):
            errors.append("timestamps:not_strictly_increasing")
        if not isinstance(self.current_time_index, int):
            errors.append("current_time_index:not_int")
        elif self.timestamps and not 0 <= self.current_time_index < len(self.timestamps):
            errors.append("current_time_index:out_of_range")
        if self.sample_rate_hz is not None and (
            not _finite(self.sample_rate_hz) or self.sample_rate_hz <= 0
        ):
            errors.append("sample_rate_hz:invalid")
        if not isinstance(self.future_available, bool):
            errors.append("future_available:not_bool")
        return tuple(errors)

    @property
    def observed_end_time(self) -> float:
        return self.timestamps[self.current_time_index]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset, "dataset_version": self.dataset_version,
            "split": self.split, "scenario_id": self.scenario_id,
            "source_file": self.source_file, "timestamps": list(self.timestamps),
            "current_time_index": self.current_time_index,
            "coordinate_frame": self.coordinate_frame,
            "position_reference": self.position_reference,
            "future_available": self.future_available,
            "sample_rate_hz": self.sample_rate_hz, "source_digest": self.source_digest,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class TrackState:
    """One timestamped state; invalid measurements retain their time slot."""

    timestamp: float
    x: Optional[float]
    y: Optional[float]
    heading: Optional[float]
    vx: Optional[float]
    vy: Optional[float]
    valid: bool
    length: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    observed: Optional[bool] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not _finite(self.timestamp):
            errors.append("timestamp:non_finite")
        for name in ("x", "y"):
            value = getattr(self, name)
            if value is None:
                if self.valid:
                    errors.append(f"{name}:missing_for_valid_state")
            elif not _finite(value):
                errors.append(f"{name}:non_finite")
        for name in ("heading", "vx", "vy", "length", "width", "height"):
            value = getattr(self, name)
            if value is not None and not _finite(value):
                errors.append(f"{name}:non_finite")
        if not isinstance(self.valid, bool):
            errors.append("valid:not_bool")
        if self.observed is not None and not isinstance(self.observed, bool):
            errors.append("observed:not_bool")
        return tuple(errors)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp, "x": self.x, "y": self.y,
            "heading": self.heading, "vx": self.vx, "vy": self.vy,
            "valid": self.valid, "length": self.length, "width": self.width,
            "height": self.height, "observed": self.observed,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class SceneTrack:
    track_id: str
    category: str
    states: tuple[TrackState, ...]
    is_sdc: bool = False
    to_predict: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self, timestamps: tuple[float, ...]) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.track_id:
            errors.append("track_id:empty")
        if not self.category:
            errors.append(f"{self.track_id}:category_empty")
        if len(self.states) != len(timestamps):
            errors.append(f"{self.track_id}:state_length_mismatch")
        for i, state in enumerate(self.states):
            for issue in state.validate():
                errors.append(f"{self.track_id}[{i}]:{issue}")
            if i < len(timestamps) and state.timestamp != timestamps[i]:
                errors.append(f"{self.track_id}[{i}]:timestamp_mismatch")
        return tuple(errors)

    def online_states(self, current_time_index: int) -> tuple[TrackState, ...]:
        """Return history plus current state; never exposes future indices."""
        return self.states[: current_time_index + 1]


@dataclass(frozen=True)
class UnifiedScene:
    manifest: SceneManifest
    tracks: tuple[SceneTrack, ...]
    map_ids: tuple[str, ...] = ()
    map_metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> tuple[str, ...]:
        errors = list(self.manifest.validate())
        ids = [track.track_id for track in self.tracks]
        if len(ids) != len(set(ids)):
            errors.append("tracks:duplicate_track_id")
        if sum(track.is_sdc for track in self.tracks) > 1:
            errors.append("tracks:multiple_sdc")
        for track in self.tracks:
            errors.extend(track.validate(self.manifest.timestamps))
        return tuple(errors)

    def assert_valid(self) -> None:
        errors = self.validate()
        if errors:
            raise ValueError("invalid unified scene: " + "; ".join(errors))

    def online_view(self) -> "UnifiedScene":
        """Return a prefix scene; future states are absent from the tracks."""
        idx = self.manifest.current_time_index
        m = self.manifest
        manifest = SceneManifest(
            dataset=m.dataset, dataset_version=m.dataset_version, split=m.split,
            scenario_id=m.scenario_id, source_file=m.source_file,
            timestamps=m.timestamps[: idx + 1], current_time_index=idx,
            coordinate_frame=m.coordinate_frame, position_reference=m.position_reference,
            future_available=False, sample_rate_hz=m.sample_rate_hz,
            source_digest=m.source_digest,
            metadata={**m.metadata, "source_timestamps": list(m.timestamps)},
        )
        tracks = tuple(SceneTrack(t.track_id, t.category, t.online_states(idx),
                                  t.is_sdc, t.to_predict, t.metadata) for t in self.tracks)
        return UnifiedScene(manifest, tracks, self.map_ids, self.map_metadata)

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest": self.manifest.to_dict(),
            "tracks": [{"track_id": t.track_id, "category": t.category,
                         "states": [s.to_dict() for s in t.states],
                         "is_sdc": t.is_sdc, "to_predict": t.to_predict,
                         "metadata": dict(t.metadata)} for t in self.tracks],
            "map_ids": list(self.map_ids), "map_metadata": dict(self.map_metadata),
        }

    def digest(self) -> str:
        self.assert_valid()
        payload = json.dumps(_canon(self.to_dict()), sort_keys=True,
                             separators=(",", ":"), ensure_ascii=True).encode()
        return hashlib.sha256(payload).hexdigest()


def build_scene_digest(scene: UnifiedScene) -> str:
    """Explicit helper used by adapters and tests."""
    return scene.digest()

