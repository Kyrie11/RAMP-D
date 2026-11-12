"""Phase 6B record adapters and explicit data-clock contracts.

The adapters in this module are deliberately conservative.  They decode a
small number of WOMD Scenario or Argoverse 2 Motion records into the immutable
``UnifiedScene`` contract, while keeping source identity, missing-state masks,
map provenance and parser versions attached to the result.  Dataset timestamps
describe sampling and observation labels; they do not describe a traffic-rule
activation, message issue/receipt, or first local observation.  Those four
clocks therefore have to be supplied explicitly through ``FourClockInjection``.

TensorFlow, the Waymo protobuf package, parquet engines and the AV2 package are
optional.  Imports happen only when a concrete reader is requested, so the
core package remains usable in a minimal test environment.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

from .protocol import ClockTrace, TimeWindow
from .scene_schema import SceneManifest, SceneTrack, TrackState, UnifiedScene


PHASE6B_SCHEMA = "rampd.phase6b.record-adapter.v1"
WOMD_PARSER_VERSION = "rampd-womd-scenario-v1"
AV2_PARSER_VERSION = "rampd-av2-motion-v1"


class OptionalDependencyError(RuntimeError):
    """Raised when a concrete reader needs an optional package."""


class RecordParseError(ValueError):
    """Raised when a source record violates the adapter contract."""


def _finite(value: Any, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise RecordParseError(f"{name} must be numeric") from exc
    if not math.isfinite(result):
        raise RecordParseError(f"{name} must be finite")
    return result


def _optional_float(value: Any, name: str) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise RecordParseError(f"{name} must be numeric or null") from exc
    return result if math.isfinite(result) else None


def _window(value: float | int | None) -> TimeWindow | None:
    if value is None:
        return None
    # Fraction(str(...)) avoids creating a huge binary-float rational while
    # retaining the decimal timestamp supplied by a simulator or test.
    from fractions import Fraction

    q = Fraction(str(_finite(value, "clock")))
    return TimeWindow(q, q)


@dataclass(frozen=True)
class FourClockInjection:
    """Explicit physical/message/local-observation timing metadata.

    ``t_activation`` is required because it is the event clock represented by
    an injected protocol branch.  The other clocks may be absent when a
    message or sensor observation is unavailable.  No ordering is inferred
    from numeric values; only relations listed in ``declared_relations`` are
    available to the formal protocol layer.
    """

    t_activation: float
    t_issue: float | None = None
    t_receipt: float | None = None
    t_first_local_observation: float | None = None
    simulator_frame: int | None = None
    sensor_frame: int | None = None
    sensor_production_time: float | None = None
    sensor_delivery_time: float | None = None
    declared_relations: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "t_activation", _finite(self.t_activation, "t_activation"))
        for name in ("t_issue", "t_receipt", "t_first_local_observation",
                     "sensor_production_time", "sensor_delivery_time"):
            value = getattr(self, name)
            if value is not None:
                value = _finite(value, name)
                if value < 0:
                    raise ValueError(f"{name} must be nonnegative")
                object.__setattr__(self, name, value)
        if self.t_activation < 0:
            raise ValueError("t_activation must be nonnegative")
        for name in ("simulator_frame", "sensor_frame"):
            value = getattr(self, name)
            if value is not None:
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise ValueError(f"{name} must be a nonnegative integer or null")
        allowed = {"activation", "issue", "receipt", "local"}
        relations = tuple((str(a), str(b)) for a, b in self.declared_relations)
        if any(a not in allowed or b not in allowed or a == b for a, b in relations):
            raise ValueError("invalid clock relation")
        if len(set(relations)) != len(relations):
            raise ValueError("duplicate clock relation")
        object.__setattr__(self, "declared_relations", relations)

    @property
    def t_local(self) -> float | None:
        return self.t_first_local_observation

    def to_clock_trace(self) -> ClockTrace:
        return ClockTrace(
            change=_window(self.t_activation),
            issue=_window(self.t_issue),
            receipt=_window(self.t_receipt),
            local=_window(self.t_first_local_observation),
            declared_relations=tuple(
                ("change" if a == "activation" else a,
                 "change" if b == "activation" else b)
                for a, b in self.declared_relations
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "t_activation": self.t_activation,
            "t_issue": self.t_issue,
            "t_receipt": self.t_receipt,
            "t_first_local_observation": self.t_first_local_observation,
            "simulator_frame": self.simulator_frame,
            "sensor_frame": self.sensor_frame,
            "sensor_production_time": self.sensor_production_time,
            "sensor_delivery_time": self.sensor_delivery_time,
            "declared_relations": [list(x) for x in self.declared_relations],
        }


@dataclass(frozen=True)
class ParsedScene:
    """A replayable scene plus source/parser metadata."""

    scene: UnifiedScene
    source_file: str
    record_index: int | None
    content_sha256: str
    parser_version: str
    source_schema: str
    clocks: FourClockInjection | None = None
    map_file: str | None = None
    map_content_sha256: str | None = None

    def __post_init__(self) -> None:
        if len(self.content_sha256) != 64 or any(c not in "0123456789abcdef" for c in self.content_sha256.lower()):
            raise ValueError("content_sha256 must be a lowercase/uppercase SHA-256 digest")
        if self.scene.manifest.source_file != self.source_file:
            raise ValueError("scene/source_file mismatch")

    @property
    def scenario_id(self) -> str:
        return self.scene.manifest.scenario_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": PHASE6B_SCHEMA,
            "scene": self.scene.to_dict(),
            "source_file": self.source_file,
            "record_index": self.record_index,
            "content_sha256": self.content_sha256,
            "parser_version": self.parser_version,
            "source_schema": self.source_schema,
            "clocks": None if self.clocks is None else self.clocks.to_dict(),
            "map_file": self.map_file,
            "map_content_sha256": self.map_content_sha256,
        }


def sha256_file(path: str | Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Return the full SHA-256 of a source file without modifying it."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while True:
            block = stream.read(chunk_size)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _json_digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=True, allow_nan=False, default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def _field(obj: Any, name: str, default: Any = None) -> Any:
    """Get a protobuf field or mapping item without accepting magic defaults."""
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _enum_name(value: Any, names: Mapping[int, str], default: str = "unknown") -> str:
    if isinstance(value, str):
        return value
    try:
        return names.get(int(value), str(int(value)))
    except (TypeError, ValueError):
        return default


_WOMD_OBJECT_TYPES = {0: "TYPE_UNSET", 1: "vehicle", 2: "pedestrian", 3: "cyclist"}


def _state_from_womd(state: Any, timestamp: float, observed: bool) -> TrackState:
    valid = bool(_field(state, "valid", False))
    if not valid:
        return TrackState(timestamp, None, None, None, None, None, False,
                          # WOMD has no per-state observed field.  Preserve the
                          # dataset current-time prefix separately from valid,
                          # so an invalid historical measurement is not
                          # rewritten as a future state.
                          observed=bool(observed))
    x = _optional_float(_field(state, "center_x"), "center_x")
    y = _optional_float(_field(state, "center_y"), "center_y")
    if x is None or y is None:
        return TrackState(timestamp, None, None, None, None, None, False,
                          observed=bool(observed),
                          metadata={"source_valid": True,
                                    "invalid_reason": "missing_center"})
    return TrackState(
        timestamp=timestamp,
        x=x,
        y=y,
        heading=_optional_float(_field(state, "heading"), "heading"),
        vx=_optional_float(_field(state, "velocity_x"), "velocity_x"),
        vy=_optional_float(_field(state, "velocity_y"), "velocity_y"),
        valid=True,
        length=_optional_float(_field(state, "length"), "length"),
        width=_optional_float(_field(state, "width"), "width"),
        height=_optional_float(_field(state, "height"), "height"),
        observed=bool(observed),
    )


def _proto_bytes(value: Any) -> bytes | None:
    serializer = getattr(value, "SerializeToString", None)
    if callable(serializer):
        try:
            return bytes(serializer())
        except Exception:
            return None
    return None


def parse_womd_scenario_proto(
    scenario: Any,
    *,
    source_file: str | Path = "<memory>",
    record_index: int | None = None,
    content_sha256: str | None = None,
    clocks: FourClockInjection | None = None,
    split: str = "unknown",
    parser_version: str = WOMD_PARSER_VERSION,
) -> ParsedScene:
    """Convert one ``waymo_open_dataset.protos.scenario_pb2.Scenario``.

    The adapter keeps the protobuf track array index in metadata and uses the
    numeric ``Track.id`` as the stable public identity.  Invalid states occupy
    their timestamp slot with ``valid=False``; they are never zero-filled.
    """
    source_file = str(source_file)
    timestamps_raw = tuple(_field(scenario, "timestamps_seconds", ()) or ())
    if not timestamps_raw:
        raise RecordParseError("WOMD scenario has no timestamps_seconds")
    timestamps = tuple(_finite(x, "timestamps_seconds") for x in timestamps_raw)
    if any(b <= a for a, b in zip(timestamps, timestamps[1:])):
        raise RecordParseError("WOMD timestamps_seconds must be strictly increasing")
    current = int(_field(scenario, "current_time_index", -1))
    if not 0 <= current < len(timestamps):
        raise RecordParseError("WOMD current_time_index is out of range")
    tracks_raw = tuple(_field(scenario, "tracks", ()) or ())
    sdc_index = int(_field(scenario, "sdc_track_index", -1))
    if sdc_index >= len(tracks_raw) or sdc_index < -1:
        raise RecordParseError("WOMD sdc_track_index is out of range")
    tracks: list[SceneTrack] = []
    track_ids: list[str] = []
    for index, track in enumerate(tracks_raw):
        raw_id = _field(track, "id", None)
        if raw_id is None:
            raise RecordParseError(f"WOMD track {index} has no Track.id")
        track_id = str(int(raw_id)) if isinstance(raw_id, (int, float)) else str(raw_id)
        if track_id in track_ids:
            raise RecordParseError("WOMD Track.id values must be unique")
        track_ids.append(track_id)
        states_raw = tuple(_field(track, "states", ()) or ())
        if len(states_raw) != len(timestamps):
            raise RecordParseError(f"WOMD track {track_id} state length mismatch")
        object_type = _enum_name(_field(track, "object_type", 0), _WOMD_OBJECT_TYPES)
        states = tuple(_state_from_womd(s, timestamps[i], i <= current)
                       for i, s in enumerate(states_raw))
        tracks.append(SceneTrack(
            track_id=track_id,
            category=object_type,
            states=states,
            is_sdc=index == sdc_index,
            to_predict=False,
            metadata={"source_track_index": index,
                      "source_track_id": track_id,
                      "object_type": object_type},
        ))
    index_to_id = {i: t for i, t in enumerate(track_ids)}
    to_predict_indices: list[int] = []
    to_predict_ids: list[str] = []
    for item in tuple(_field(scenario, "tracks_to_predict", ()) or ()):
        idx = _field(item, "track_index", None)
        if idx is None:
            continue
        idx = int(idx)
        if idx < 0 or idx >= len(track_ids):
            raise RecordParseError("WOMD tracks_to_predict index is out of range")
        to_predict_indices.append(idx)
        to_predict_ids.append(index_to_id[idx])
    predict_set = set(to_predict_ids)
    tracks = [replace(t, to_predict=t.track_id in predict_set) for t in tracks]
    dynamic_states = tuple(_field(scenario, "dynamic_map_states", ()) or ())
    if dynamic_states and len(dynamic_states) != len(timestamps):
        raise RecordParseError("WOMD dynamic_map_states length mismatch")
    map_features = tuple(_field(scenario, "map_features", ()) or ())
    map_ids = []
    for feature in map_features:
        value = _field(feature, "id", None)
        if value is not None:
            map_ids.append(str(value))
    objects_of_interest = tuple(_field(scenario, "objects_of_interest", ()) or ())
    metadata: dict[str, Any] = {
        "schema": "waymo_open_dataset.protos.scenario_pb2.Scenario",
        "parser_version": parser_version,
        "source_track_count": len(tracks),
        "source_track_indices": list(range(len(tracks))),
        "sdc_track_index": sdc_index,
        "tracks_to_predict_indices": to_predict_indices,
        "tracks_to_predict_ids": to_predict_ids,
        "objects_of_interest": [int(x) for x in objects_of_interest],
        "dynamic_map_state_count": len(dynamic_states),
        "dynamic_map_states_digest": _json_digest([str(x) for x in dynamic_states]) if dynamic_states else None,
        "map_feature_count": len(map_features),
        "sampling_semantics": "dataset_10hz_discrete_not_continuous_safety",
        "online_boundary_semantics": "current_time_index_prefix",
        "future_label_semantics": "withheld" if str(split).casefold() in {"test", "testing"} else "available",
    }
    raw = _proto_bytes(scenario)
    content_sha256 = content_sha256 or (hashlib.sha256(raw).hexdigest() if raw is not None else _json_digest(metadata))
    manifest = SceneManifest(
        dataset="womd_scenario", dataset_version="1.3.1",
        split=str(split), scenario_id=str(_field(scenario, "scenario_id", "")),
        source_file=source_file, timestamps=timestamps, current_time_index=current,
        coordinate_frame="womd_global_xy", position_reference="bounding_box_center",
        future_available=str(split).casefold() not in {"test", "testing"}, sample_rate_hz=10.0, source_digest=content_sha256,
        metadata=metadata,
    )
    if not manifest.scenario_id:
        raise RecordParseError("WOMD scenario_id is empty")
    scene = UnifiedScene(manifest, tuple(tracks), tuple(map_ids),
                         {"dynamic_map_states": metadata["dynamic_map_states_digest"]})
    scene.assert_valid()
    return ParsedScene(scene, source_file, record_index, content_sha256,
                       parser_version, "womd-scenario-proto-v1", clocks)


def _resolve_split(root: Path, names: Sequence[str]) -> Path:
    if not root.is_dir():
        raise FileNotFoundError(root)
    children = {p.name.casefold(): p for p in root.iterdir() if p.is_dir()}
    for name in names:
        if name.casefold() in children:
            return children[name.casefold()]
    raise FileNotFoundError(f"none of {tuple(names)!r} exists below {root}")


def _iter_tfrecord(path: Path) -> Iterator[bytes]:
    try:
        import tensorflow as tf  # type: ignore
    except ImportError:
        try:
            from tensorflow.python.lib.io import tf_record  # type: ignore
        except ImportError as exc:
            raise OptionalDependencyError("WOMD parsing requires tensorflow") from exc
        yield from tf_record.tf_record_iterator(str(path))
        return
    dataset = tf.data.TFRecordDataset([str(path)])
    for record in dataset.as_numpy_iterator():
        yield bytes(record)


def iter_womd_scenario_file(
    path: str | Path, *, max_records: int = 10,
    clocks: FourClockInjection | None = None,
) -> Iterator[ParsedScene]:
    """Yield at most ``max_records`` Scenario protos from one TFRecord shard."""
    if max_records <= 0:
        return
    try:
        from waymo_open_dataset.protos import scenario_pb2  # type: ignore
    except ImportError as exc:
        raise OptionalDependencyError("WOMD parsing requires waymo_open_dataset") from exc
    path = Path(path)
    digest = sha256_file(path)
    for index, payload in enumerate(_iter_tfrecord(path)):
        if index >= max_records:
            break
        scenario = scenario_pb2.Scenario()
        scenario.ParseFromString(payload)
        yield parse_womd_scenario_proto(scenario, source_file=path,
                                         record_index=index,
                                         content_sha256=digest, clocks=clocks,
                                         split="validation")


def iter_womd_validation(
    root: str | Path, *, max_records: int = 10, max_files: int = 10,
    clocks: FourClockInjection | None = None,
) -> Iterator[ParsedScene]:
    """Read a bounded sample from the case-insensitive Scenario/validation split."""
    split_root = _resolve_split(Path(root).expanduser(), ("validation",))
    files = sorted(p for p in split_root.rglob("*") if p.is_file() and
                   (p.name.endswith(".tfrecord") or ".tfrecord-" in p.name))
    if not files:
        raise FileNotFoundError(f"no TFRecord shards below {split_root}")
    emitted = 0
    for path in files[:max_files]:
        for parsed in iter_womd_scenario_file(path, max_records=max_records - emitted,
                                              clocks=clocks):
            yield parsed
            emitted += 1
            if emitted >= max_records:
                return


def _row_dicts(rows: Any) -> list[dict[str, Any]]:
    if hasattr(rows, "to_dict"):
        try:
            return [dict(x) for x in rows.to_dict(orient="records")]
        except TypeError:
            pass
    result = []
    for row in rows:
        if isinstance(row, Mapping):
            result.append(dict(row))
        else:
            result.append(dict(row))
    return result


def _first_value(rows: Sequence[Mapping[str, Any]], names: Sequence[str], default: Any = None) -> Any:
    for row in rows:
        for name in names:
            if name in row and row[name] is not None:
                value = row[name]
                try:
                    if not (isinstance(value, float) and math.isnan(value)):
                        return value
                except TypeError:
                    return value
    return default


def _av2_map_metadata(map_file: str | Path | None) -> tuple[str | None, tuple[str, ...], dict[str, Any]]:
    if map_file is None:
        return None, (), {"map_status": "not_provided"}
    path = Path(map_file)
    if not path.is_file():
        raise FileNotFoundError(path)
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise RecordParseError(f"invalid AV2 map JSON: {path}") from exc
    content_digest = sha256_file(path)
    semantic_digest = _json_digest(value)
    ids: list[str] = []
    if isinstance(value, Mapping):
        for key in ("id", "map_id", "log_id"):
            if value.get(key) is not None:
                ids.append(str(value[key]))
        for key in ("lane_segments", "drivable_areas", "pedestrian_crossings"):
            items = value.get(key)
            if isinstance(items, Mapping):
                ids.extend(str(x) for x in items.keys())
            elif isinstance(items, list):
                ids.extend(str(_field(x, "id", i)) for i, x in enumerate(items))
    return str(path), tuple(dict.fromkeys(ids)), {
        "map_status": "parsed_json",
        "map_content_sha256": content_digest,
        "map_semantic_sha256": semantic_digest,
        "map_feature_count": len(ids),
        "map_coordinate_frame": "av2_city_xy",
    }


def resolve_av2_map(parquet_file: str | Path, scenario_id: str | None = None,
                    map_file: str | Path | None = None) -> Path | None:
    """Resolve the scenario-local map archive without cross-scene guessing."""
    if map_file is not None:
        return Path(map_file)
    parquet = Path(parquet_file)
    sid = scenario_id or parquet.stem.removeprefix("scenario_")
    exact = parquet.parent / f"log_map_archive_{sid}.json"
    if exact.is_file():
        return exact
    # A single differently named archive is not enough evidence: a split can
    # contain a shared log map or an unrelated scenario.  Callers may pass an
    # explicit map_file after checking the parquet's map_id.
    return None


def parse_av2_rows(
    rows: Any, *, source_file: str | Path = "<memory>",
    split: str = "validation", scenario_id: str | None = None,
    map_file: str | Path | None = None, content_sha256: str | None = None,
    clocks: FourClockInjection | None = None,
    parser_version: str = AV2_PARSER_VERSION,
    nominal_sample_rate_hz: float = 10.0,
) -> ParsedScene:
    """Convert AV2 Motion parquet rows into a dense ``UnifiedScene``.

    Official AV2 rows are sparse per track.  The adapter reconstructs a dense
    global timestep axis and uses ``valid=False`` for absent rows.  The
    scenario-level start/end/num-timestamps columns are preferred; a nominal
    10 Hz axis is only a documented fallback when a synthetic fixture omits
    those columns.
    """
    source_file = str(source_file)
    records = _row_dicts(rows)
    if not records:
        raise RecordParseError("AV2 parquet contains no rows")
    sid_values = {str(r["scenario_id"]) for r in records if r.get("scenario_id") not in (None, "")}
    if len(sid_values) > 1:
        raise RecordParseError("AV2 parquet mixes scenario_id values")
    sid = scenario_id or (next(iter(sid_values)) if sid_values else None)
    if sid is None:
        sid = Path(source_file).stem.removeprefix("scenario_")
    if not sid:
        raise RecordParseError("AV2 scenario_id is empty")
    timestep_values = []
    for row in records:
        if row.get("timestep") is None:
            raise RecordParseError("AV2 rows require timestep")
        timestep = int(row["timestep"])
        if timestep < 0:
            raise RecordParseError("AV2 timestep must be nonnegative")
        timestep_values.append(timestep)
    start_ns = _first_value(records, ("start_timestamp", "start_timestamp_ns"))
    end_ns = _first_value(records, ("end_timestamp", "end_timestamp_ns"))
    n_steps_raw = _first_value(records, ("num_timestamps", "num_timesteps"))
    n_steps = int(n_steps_raw) if n_steps_raw is not None else max(timestep_values) + 1
    if n_steps <= max(timestep_values):
        raise RecordParseError("AV2 num_timestamps does not cover row timesteps")
    row_ts = {int(r["timestep"]): r.get("timestamp_ns") for r in records
              if r.get("timestamp_ns") is not None}
    all_ts = [x for x in row_ts.values() if x is not None]
    if len(all_ts) >= 2:
        first_ns = _finite(min(all_ts), "timestamp_ns")
        timestamps = tuple((_finite(row_ts.get(i, first_ns + i * 1e8), "timestamp_ns") - first_ns) / 1e9
                           for i in range(n_steps))
        time_source = "row_timestamp_ns"
    elif start_ns is not None and end_ns is not None:
        start = _finite(start_ns, "start_timestamp_ns")
        end = _finite(end_ns, "end_timestamp_ns")
        if end <= start:
            raise RecordParseError("AV2 end_timestamp must exceed start_timestamp")
        timestamps = tuple((start + (end - start) * i / (n_steps - 1) - start) / 1e9
                           for i in range(n_steps)) if n_steps > 1 else (0.0,)
        time_source = "scenario_start_end_timestamp_ns"
    else:
        timestamps = tuple(i / nominal_sample_rate_hz for i in range(n_steps))
        time_source = "nominal_sample_rate_fallback"
    if any(b <= a for a, b in zip(timestamps, timestamps[1:])):
        raise RecordParseError("AV2 timestamps must be strictly increasing")
    for row in records:
        if "observed" not in row:
            raise RecordParseError("AV2 rows require observed mask")
    focal_id = _first_value(records, ("focal_track_id",))
    focal_id_source = "focal_track_id" if focal_id is not None else None
    if focal_id is None:
        focal_candidates = sorted({str(r.get("track_id")) for r in records
                                   if str(r.get("object_category", r.get("track_category", ""))).upper()
                                   == "FOCAL_TRACK"})
        if len(focal_candidates) == 1:
            focal_id = focal_candidates[0]
            focal_id_source = "object_category"
    focal_observed_indices = [int(r["timestep"]) for r in records
                              if str(r.get("track_id", "")) == str(focal_id)
                              and bool(r["observed"])] if focal_id is not None else []
    observed_indices = focal_observed_indices or [int(r["timestep"]) for r in records
                                                   if bool(r["observed"])]
    current_index_source = ("focal_track_observed" if focal_observed_indices
                            else "global_observed_fallback")
    if not observed_indices:
        raise RecordParseError("AV2 has no observed prefix")
    current = max(observed_indices)
    if current >= n_steps:
        raise RecordParseError("AV2 current index out of range")
    by_track: dict[str, dict[int, Mapping[str, Any]]] = {}
    track_meta: dict[str, Mapping[str, Any]] = {}
    for row in records:
        track_id = str(row.get("track_id", ""))
        if not track_id:
            raise RecordParseError("AV2 track_id is empty")
        timestep = int(row["timestep"])
        bucket = by_track.setdefault(track_id, {})
        if timestep in bucket:
            raise RecordParseError(f"duplicate AV2 state for {track_id}@{timestep}")
        bucket[timestep] = row
        track_meta.setdefault(track_id, row)
    tracks: list[SceneTrack] = []
    for track_id in sorted(by_track):
        prototype = track_meta[track_id]
        object_type = str(prototype.get("object_type", "unknown"))
        category = str(prototype.get("object_category", prototype.get("track_category", "unknown")))
        states: list[TrackState] = []
        for i, timestamp in enumerate(timestamps):
            row = by_track[track_id].get(i)
            if row is None:
                states.append(TrackState(timestamp, None, None, None, None, None,
                                         False, observed=None))
                continue
            observed = bool(row["observed"])
            x = _optional_float(row.get("position_x"), "position_x")
            y = _optional_float(row.get("position_y"), "position_y")
            valid = x is not None and y is not None
            states.append(TrackState(timestamp, x, y,
                                     _optional_float(row.get("heading"), "heading"),
                                     _optional_float(row.get("velocity_x"), "velocity_x"),
                                     _optional_float(row.get("velocity_y"), "velocity_y"),
                                     valid, observed=observed,
                                     metadata={"source_timestep": i}))
        tracks.append(SceneTrack(track_id, object_type, tuple(states),
                                 is_sdc=str(focal_id) == track_id,
                                 to_predict=category in {"FOCAL_TRACK", "SCORED_TRACK"},
                                 metadata={"object_type": object_type,
                                           "object_category": category}))
    map_path, map_ids, map_metadata = _av2_map_metadata(map_file)
    content_sha256 = content_sha256 or (sha256_file(source_file) if Path(source_file).is_file()
                                        else _json_digest(records))
    metadata: dict[str, Any] = {
        "schema": "av2.motion_forecasting.parquet",
        "parser_version": parser_version,
        "time_axis_source": time_source,
        "timestamp_unit": "seconds_relative_to_first_timestamp",
        "source_timestamps_start_ns": start_ns,
        "source_timestamps_end_ns": end_ns,
        "num_timestamps": n_steps,
        "focal_track_id": None if focal_id is None else str(focal_id),
        "focal_track_id_source": focal_id_source,
        "current_index_source": current_index_source,
        "map_file": map_path,
        "sampling_semantics": "dataset_10hz_discrete_not_continuous_safety",
        **map_metadata,
    }
    future_available = str(split).casefold() not in {"test", "testing"}
    manifest = SceneManifest(
        dataset="av2_motion", dataset_version="2",
        split=str(split), scenario_id=str(sid), source_file=source_file,
        timestamps=timestamps, current_time_index=current,
        coordinate_frame="av2_city_xy", position_reference="bounding_box_center",
        future_available=future_available, sample_rate_hz=nominal_sample_rate_hz,
        source_digest=content_sha256, metadata=metadata,
    )
    scene = UnifiedScene(manifest, tuple(tracks), map_ids, map_metadata)
    scene.assert_valid()
    return ParsedScene(scene, source_file, None, content_sha256, parser_version,
                       "av2-motion-parquet-v1", clocks, map_path,
                       map_metadata.get("map_content_sha256"))


def parse_av2_parquet(path: str | Path, *, split: str = "validation",
                      map_file: str | Path | None = None,
                      clocks: FourClockInjection | None = None,
                      require_map: bool = True) -> ParsedScene:
    try:
        import pandas as pd  # type: ignore
    except ImportError as exc:
        raise OptionalDependencyError("AV2 parsing requires pandas and a parquet engine") from exc
    path = Path(path)
    try:
        frame = pd.read_parquet(path)
    except ImportError as exc:
        raise OptionalDependencyError("AV2 parquet parsing requires pyarrow or fastparquet") from exc
    except Exception as exc:
        raise RecordParseError(f"unable to decode AV2 parquet {path}: {exc}") from exc
    resolved_map = resolve_av2_map(path, map_file=map_file)
    if require_map and resolved_map is None:
        raise RecordParseError(
            f"AV2 scenario map archive unresolved for {path}; pass map_file explicitly"
        )
    return parse_av2_rows(frame, source_file=path, split=split,
                          map_file=resolved_map, content_sha256=sha256_file(path),
                          clocks=clocks)


def iter_av2_validation(root: str | Path, *, max_records: int = 10,
                        clocks: FourClockInjection | None = None) -> Iterator[ParsedScene]:
    split_root = _resolve_split(Path(root).expanduser(), ("validation", "val"))
    files = sorted(split_root.rglob("scenario_*.parquet"))
    if not files:
        raise FileNotFoundError(f"no AV2 scenario parquet below {split_root}")
    for path in files[:max_records]:
        yield parse_av2_parquet(path, split="validation", clocks=clocks)


def localize_scene(scene: UnifiedScene, *, origin_xy: tuple[float, float] = (0.0, 0.0),
                   yaw_rad: float = 0.0,
                   origin_track_id: str | None = None,
                   origin_time_index: int | None = None) -> UnifiedScene:
    """Convert track states to a deterministic local XY frame.

    Map JSON remains attached by provenance; its geometry is not silently
    rewritten because AV2 map archives contain heterogeneous lane/polygon
    schemas.  ``map_metadata.local_transform`` is the exact rigid transform a
    downstream map adapter must apply to every map point.
    """
    resolved_origin_index = origin_time_index
    if origin_track_id is not None:
        index = scene.manifest.current_time_index if origin_time_index is None else int(origin_time_index)
        resolved_origin_index = index
        matches = [track for track in scene.tracks if track.track_id == str(origin_track_id)]
        if len(matches) != 1:
            raise RecordParseError(f"origin_track_id {origin_track_id!r} is not present exactly once")
        if not 0 <= index < len(matches[0].states):
            raise RecordParseError("origin_time_index is out of range")
        anchor = matches[0].states[index]
        if not anchor.valid or anchor.x is None or anchor.y is None:
            raise RecordParseError("origin track has no valid position at origin_time_index")
        origin_xy = (anchor.x, anchor.y)
        if anchor.heading is None:
            raise RecordParseError("origin track has no heading at origin_time_index")
        yaw_rad = anchor.heading
    ox, oy = _finite(origin_xy[0], "origin_x"), _finite(origin_xy[1], "origin_y")
    yaw = _finite(yaw_rad, "yaw_rad")
    c, s = math.cos(yaw), math.sin(yaw)
    # world -> local: R(-yaw)(p-origin)
    def transform(x: float, y: float) -> tuple[float, float]:
        dx, dy = x - ox, y - oy
        return c * dx + s * dy, -s * dx + c * dy
    tracks: list[SceneTrack] = []
    for track in scene.tracks:
        states = []
        for state in track.states:
            if not state.valid or state.x is None or state.y is None:
                states.append(state)
                continue
            x, y = transform(state.x, state.y)
            vx = vy = None
            if state.vx is not None and state.vy is not None:
                vx, vy = c * state.vx + s * state.vy, -s * state.vx + c * state.vy
            heading = None if state.heading is None else state.heading - yaw
            states.append(replace(state, x=x, y=y, vx=vx, vy=vy, heading=heading,
                                  metadata={**state.metadata, "frame_transform": "world_to_local"}))
        tracks.append(replace(track, states=tuple(states)))
    metadata = dict(scene.manifest.metadata)
    metadata["local_transform"] = {"origin_xy": [ox, oy], "yaw_rad": yaw,
                                    "origin_track_id": origin_track_id,
                                    "origin_time_index": resolved_origin_index}
    manifest = replace(scene.manifest, coordinate_frame="local_xy", metadata=metadata)
    map_metadata = dict(scene.map_metadata)
    map_metadata["local_transform"] = metadata["local_transform"]
    return UnifiedScene(manifest, tuple(tracks), scene.map_ids, map_metadata)


def convert_center_scene_to_rear_axle(
    scene: UnifiedScene, *, offset_body: tuple[float, float],
    offset_source: str = "explicit_vehicle_geometry",
    yaw_rates: Mapping[tuple[str, int], float] | None = None,
    geometry_uncertainty: str = "explicit",
) -> UnifiedScene:
    """Apply ``p_rear = p_center - R(psi)o`` when an explicit offset is known.

    ``offset_body`` is the vector from the rear axle to the box centre in the
    body frame.  If yaw rates are supplied, velocity uses
    ``v_rear=v_center-psi_dot R(psi)J o``.  Without yaw rates the position is
    converted but velocity provenance remains explicitly marked as center-frame
    so a continuous-time verifier can reject the mixed reference if needed.
    """
    ox, oy = _finite(offset_body[0], "offset_body.x"), _finite(offset_body[1], "offset_body.y")
    yaw_rates = yaw_rates or {}
    velocity_total = 0
    velocity_converted = 0
    tracks: list[SceneTrack] = []
    for track in scene.tracks:
        track_velocity_total = 0
        track_velocity_converted = 0
        states = []
        for i, state in enumerate(track.states):
            if not state.valid or state.x is None or state.y is None or state.heading is None:
                states.append(state)
                continue
            c, s = math.cos(state.heading), math.sin(state.heading)
            rx, ry = state.x - (c * ox - s * oy), state.y - (s * ox + c * oy)
            vx, vy = state.vx, state.vy
            if vx is not None and vy is not None:
                velocity_total += 1
                track_velocity_total += 1
            yaw_rate = yaw_rates.get((track.track_id, i))
            if vx is not None and vy is not None and yaw_rate is not None:
                # J o = (-oy, ox), then rotate by R(psi).
                jx, jy = -oy, ox
                rjx, rjy = c * jx - s * jy, s * jx + c * jy
                vx, vy = vx - yaw_rate * rjx, vy - yaw_rate * rjy
                velocity_converted += 1
                track_velocity_converted += 1
            states.append(replace(state, x=rx, y=ry, vx=vx, vy=vy,
                                  metadata={**state.metadata,
                                            "reference_conversion": "center_to_rear_axle",
                                            "rear_axle_offset_body": [ox, oy],
                                            "yaw_rate_available": yaw_rate is not None}))
        tracks.append(replace(track, states=tuple(states),
                              metadata={**track.metadata,
                                        "reference_conversion": "center_to_rear_axle",
                                        "rear_axle_offset_body": [ox, oy],
                                        "rear_axle_offset_source": offset_source,
                                        "geometry_uncertainty": geometry_uncertainty,
                                        "velocity_reference": "rear_axle" if track_velocity_total and track_velocity_converted == track_velocity_total else "center_unconverted"}))
    velocity_reference = ("rear_axle" if velocity_total and velocity_converted == velocity_total
                          else "center_unconverted")
    manifest = replace(scene.manifest, position_reference="rear_axle_center",
                       metadata={**scene.manifest.metadata,
                                 "position_reference_source": "explicit_center_to_rear_axle",
                                 "rear_axle_offset_source": offset_source,
                                 "geometry_uncertainty": geometry_uncertainty,
                                 "velocity_reference": velocity_reference})
    return UnifiedScene(manifest, tuple(tracks), scene.map_ids, scene.map_metadata)


__all__ = [
    "PHASE6B_SCHEMA", "WOMD_PARSER_VERSION", "AV2_PARSER_VERSION",
    "OptionalDependencyError", "RecordParseError", "FourClockInjection",
    "ParsedScene", "sha256_file", "parse_womd_scenario_proto",
    "iter_womd_scenario_file", "iter_womd_validation", "resolve_av2_map",
    "parse_av2_rows", "parse_av2_parquet", "iter_av2_validation",
    "localize_scene", "convert_center_scene_to_rear_axle",
]
