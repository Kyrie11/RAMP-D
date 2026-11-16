"""Phase 6C-A2: dataset-faithful *descriptive* vector map and signal records.

Geometry is in a declared metric source frame. The objects deliberately do not
make claims about legal permissions, signal visibility, collision-free occupancy,
or mathematical safety certificates. In particular, recorded future traffic
signal states are supervision labels, never inputs to an online controller.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
import hashlib
import json
import math
from typing import Any, Mapping


class MapContractError(ValueError):
    pass


def _numeric(v: Any, name: str) -> float:
    if isinstance(v, bool):
        raise MapContractError(f"{name} must be numeric, not bool")
    try:
        x = float(v)
    except (ValueError, TypeError) as exc:
        raise MapContractError(f"{name} is not numeric") from exc
    if not math.isfinite(x):
        raise MapContractError(f"{name} must be finite")
    return x


def _get(v: Any, name: str, default: Any = None) -> Any:
    return v.get(name, default) if isinstance(v, Mapping) else getattr(v, name, default)


def _proto_optional(v: Any, name: str) -> Any:
    """Distinguish absent optional protobuf submessages from default (0,0,0).

    Proto2/3 message-valued fields can return a default instance when absent;
    manufacturing a (0,0) stop point or sign would corrupt map geometry.
    """
    has_field = getattr(v, "HasField", None)
    if callable(has_field):
        try:
            if not has_field(name):
                return None
        except ValueError:
            # Scalar proto3 fields and repeated fields have no presence bit.
            pass
    return _get(v, name)


def _items(v: Any) -> tuple[Any, ...]:
    if v is None:
        return ()
    if isinstance(v, Mapping):
        return tuple(v.values())
    return tuple(v)


def _text_enum(value: Any) -> str:
    # Numeric protobuf enums retain their integer identity; known WOMD states
    # are normalized below rather than conflated with permissions.
    if isinstance(value, str):
        return value
    try:
        return str(int(value))
    except (ValueError, TypeError):
        return str(value)


@dataclass(frozen=True)
class MapVertex:
    x: float
    y: float
    z: float | None = None

    def __post_init__(self):
        object.__setattr__(self, "x", _numeric(self.x, "map x"))
        object.__setattr__(self, "y", _numeric(self.y, "map y"))
        if self.z is not None:
            object.__setattr__(self, "z", _numeric(self.z, "map z"))

    def transform(self, origin: tuple[float, float], yaw_rad: float) -> "MapVertex":
        c, s = math.cos(yaw_rad), math.sin(yaw_rad)
        dx, dy = self.x - origin[0], self.y - origin[1]
        return MapVertex(c * dx + s * dy, -s * dx + c * dy, self.z)


def _vertex(item: Any) -> MapVertex:
    if isinstance(item, (list, tuple)):
        if len(item) not in (2, 3):
            raise MapContractError("map vertex array must have 2 or 3 coordinates")
        return MapVertex(*item)
    x, y = _get(item, "x"), _get(item, "y")
    if x is None or y is None:
        raise MapContractError("map vertex lacks x/y")
    return MapVertex(x, y, _get(item, "z"))


def _vertices(items: Any) -> tuple[MapVertex, ...]:
    return tuple(_vertex(p) for p in _items(items))


def _polyline_json(item: Any) -> tuple[MapVertex, ...]:
    # Official AV2 Polyline.from_json_data reads a list of {x,y,z} points.
    return _vertices(_get(item, "xyz", item))


def _polygon(vertices: tuple[MapVertex, ...]) -> tuple[MapVertex, ...]:
    if len(vertices) >= 2 and vertices[0] == vertices[-1]:
        return vertices[:-1]
    return vertices


@dataclass(frozen=True)
class MapPrimitive:
    feature_id: str
    kind: str
    geometry_type: str  # polyline | polygon | point | missing
    vertices: tuple[MapVertex, ...] = ()
    successors: tuple[str, ...] = ()
    predecessors: tuple[str, ...] = ()
    left_neighbors: tuple[str, ...] = ()
    right_neighbors: tuple[str, ...] = ()
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.feature_id or not self.kind:
            raise MapContractError("map feature requires id and kind")
        if self.geometry_type not in {"polyline", "polygon", "point", "missing"}:
            raise MapContractError("invalid geometry type")
        n = len(self.vertices)
        if ((self.geometry_type == "polyline" and n < 2) or
            (self.geometry_type == "polygon" and n < 3) or
            (self.geometry_type == "point" and n != 1) or
            (self.geometry_type == "missing" and n)):
            raise MapContractError(f"invalid {self.geometry_type} geometry for {self.feature_id}")
        if len({(x.x, x.y) for x in self.vertices}) < (3 if self.geometry_type == "polygon" else 1 if self.geometry_type == "point" else 2 if self.geometry_type == "polyline" else 0):
            raise MapContractError(f"degenerate geometry for {self.feature_id}")

    def transform(self, origin: tuple[float, float], yaw_rad: float) -> "MapPrimitive":
        return replace(self, vertices=tuple(v.transform(origin, yaw_rad) for v in self.vertices))


@dataclass(frozen=True)
class SignalRecord:
    timestep: int
    timestamp_s: float
    lane_id: str
    state: str
    stop_point: MapVertex | None = None
    # A logged state is NOT proof that the ego actually perceived it.
    visibility: str = "recorded_not_proven_observed"

    def __post_init__(self):
        if isinstance(self.timestep, bool) or not isinstance(self.timestep, int) or self.timestep < 0:
            raise MapContractError("signal timestep must be a nonnegative integer")
        object.__setattr__(self, "timestamp_s", _numeric(self.timestamp_s, "signal timestamp"))
        if not self.lane_id or not self.state or self.visibility != "recorded_not_proven_observed":
            raise MapContractError("untrusted dataset signal cannot claim verified visibility")

    def transform(self, origin: tuple[float, float], yaw_rad: float) -> "SignalRecord":
        return replace(self, stop_point=self.stop_point.transform(origin, yaw_rad) if self.stop_point else None)


@dataclass(frozen=True)
class MapContext:
    dataset: str
    scenario_id: str
    coordinate_frame: str
    primitives: tuple[MapPrimitive, ...]
    signals: tuple[SignalRecord, ...] = ()
    complete_geometry: bool = False
    source_map_sha256: str | None = None
    signal_semantics: str = "logged_ground_truth_not_ego_visibility"

    def __post_init__(self):
        if not self.dataset or not self.scenario_id or not self.coordinate_frame:
            raise MapContractError("map context requires dataset/scenario/frame")
        ids = [p.feature_id for p in self.primitives]
        if len(set(ids)) != len(ids):
            raise MapContractError("duplicate map feature IDs")
        if self.signal_semantics != "logged_ground_truth_not_ego_visibility":
            raise MapContractError("signal observations cannot be assumed from logs")
        if self.source_map_sha256 is not None and (len(self.source_map_sha256) != 64 or
            any(c not in "0123456789abcdef" for c in self.source_map_sha256.lower())):
            raise MapContractError("invalid map SHA-256")
        if any(a.timestamp_s > b.timestamp_s for a, b in zip(self.signals, self.signals[1:])):
            raise MapContractError("signal timeline must be sorted by time")
        if self.complete_geometry and any(p.geometry_type == "missing" for p in self.primitives):
            raise MapContractError("incomplete map cannot claim geometry coverage")

    def prefix(self, current_index: int) -> "MapContext":
        return replace(self, signals=tuple(s for s in self.signals if s.timestep <= current_index))

    def static_only(self) -> "MapContext":
        """Default safe encoder representation; no dynamic states, including past."""
        return replace(self, signals=())

    def transform(self, origin: tuple[float, float], yaw_rad: float) -> "MapContext":
        origin = (_numeric(origin[0], "origin x"), _numeric(origin[1], "origin y"))
        yaw_rad = _numeric(yaw_rad, "yaw")
        return replace(self, coordinate_frame="local_xy",
                       primitives=tuple(p.transform(origin, yaw_rad) for p in self.primitives),
                       signals=tuple(s.transform(origin, yaw_rad) for s in self.signals))

    @property
    def summary(self) -> dict[str, Any]:
        return {"primitives": len(self.primitives), "signals": len(self.signals),
                "complete_geometry": self.complete_geometry,
                "coordinate_frame": self.coordinate_frame}


_WOMD_MAP_KINDS = ("lane", "road_line", "road_edge", "stop_sign",
                   "crosswalk", "speed_bump", "driveway")
_WOMD_SIGNAL_STATES = {
    0: "LANE_STATE_UNKNOWN", 1: "LANE_STATE_ARROW_STOP", 2: "LANE_STATE_ARROW_CAUTION",
    3: "LANE_STATE_ARROW_GO", 4: "LANE_STATE_STOP", 5: "LANE_STATE_CAUTION",
    6: "LANE_STATE_GO", 7: "LANE_STATE_FLASHING_STOP", 8: "LANE_STATE_FLASHING_CAUTION",
}


def from_womd_scenario(scenario: Any) -> MapContext:
    """Decode the exact Scenario.map_features / dynamic_map_states fields."""
    primitives: list[MapPrimitive] = []
    geometry_complete = True
    features = _items(_get(scenario, "map_features", ()))
    if not features:
        geometry_complete = False
    for feature in features:
        fid = _get(feature, "id")
        if fid is None:
            raise MapContractError("WOMD MapFeature missing id")
        kind = None
        which = getattr(feature, "WhichOneof", None)
        if callable(which):
            kind = which("feature_data")
        if kind is None:
            candidates = [k for k in _WOMD_MAP_KINDS if _get(feature, k) is not None]
            if len(candidates) > 1:
                raise MapContractError(f"WOMD feature {fid} has multiple map types")
            kind = candidates[0] if candidates else "unknown"
        if kind not in _WOMD_MAP_KINDS:
            primitives.append(MapPrimitive(str(fid), "unknown", "missing"))
            geometry_complete = False
            continue
        obj = _get(feature, kind)
        verts: tuple[MapVertex, ...]
        geom = "polyline"
        if kind in {"lane", "road_line", "road_edge"}:
            verts = _vertices(_get(obj, "polyline", ()))
        elif kind in {"crosswalk", "speed_bump", "driveway"}:
            geom = "polygon"
            verts = _polygon(_vertices(_get(obj, "polygon", ())))
        else:
            geom = "point"
            position = _proto_optional(obj, "position")
            verts = (_vertex(position),) if position is not None else ()
        if len(verts) < (3 if geom == "polygon" else 2 if geom == "polyline" else 1):
            # Explicitly mark incomplete geometry instead of manufacturing
            # arbitrary points or falsely counting the map as fully parsed.
            geometry_complete = False
            geom, verts = "missing", ()
        attrs: dict[str, Any] = {}
        if kind == "lane":
            attrs = {"speed_limit_mph": _get(obj, "speed_limit_mph"),
                     "lane_type": _text_enum(_get(obj, "type", 0))}
        elif kind in ("road_line", "road_edge"):
            attrs = {"boundary_type": _text_enum(_get(obj, "type", 0))}
        elif kind == "stop_sign":
            attrs = {"controlled_lane_ids": tuple(str(x) for x in _items(_get(obj, "lane", ())))}
        primitives.append(MapPrimitive(
            str(fid), kind, geom, verts,
            successors=tuple(str(x) for x in _items(_get(obj, "exit_lanes", ()))) if kind == "lane" else (),
            predecessors=tuple(str(x) for x in _items(_get(obj, "entry_lanes", ()))) if kind == "lane" else (),
            left_neighbors=tuple(str(_get(x, "feature_id")) for x in _items(_get(obj, "left_neighbors", ()))) if kind == "lane" else (),
            right_neighbors=tuple(str(_get(x, "feature_id")) for x in _items(_get(obj, "right_neighbors", ()))) if kind == "lane" else (),
            attributes=attrs,
        ))
    times = tuple(_numeric(t, "WOMD timestamp") for t in _items(_get(scenario, "timestamps_seconds", ())))
    states = _items(_get(scenario, "dynamic_map_states", ()))
    if states and len(states) != len(times):
        raise MapContractError("WOMD signal timeline does not match timestamps")
    signals: list[SignalRecord] = []
    for i, state in enumerate(states):
        lanes_at_t = set()
        for lane_state in _items(_get(state, "lane_states", ())):
            lane_id = _get(lane_state, "lane")
            if lane_id is None:
                raise MapContractError("WOMD TrafficSignalLaneState missing lane")
            if str(lane_id) in lanes_at_t:
                raise MapContractError("WOMD duplicate signal record for lane/time")
            lanes_at_t.add(str(lane_id))
            raw_state = _get(lane_state, "state", 0)
            if isinstance(raw_state, str) and raw_state.startswith("LANE_STATE_"):
                state_name = raw_state
            else:
                state_name = _WOMD_SIGNAL_STATES.get(int(raw_state), f"UNRECOGNIZED_{raw_state}")
            stop = _proto_optional(lane_state, "stop_point")
            signals.append(SignalRecord(i, times[i], str(lane_id), state_name,
                                        _vertex(stop) if stop is not None else None))
    signals.sort(key=lambda r: (r.timestep, r.lane_id))
    return MapContext("womd_scenario", str(_get(scenario, "scenario_id", "")),
                      "womd_global_xy", tuple(primitives), tuple(signals), geometry_complete)


def from_av2_map_json(value: Mapping[str, Any], *, scenario_id: str,
                      content_sha256: str | None = None) -> MapContext:
    """Interpret the AV2 scenario-local log_map_archive_* JSON (no 1TB Map Change requirement)."""
    if not isinstance(value, Mapping):
        raise MapContractError("AV2 map JSON root must be an object")
    primitives: list[MapPrimitive] = []
    complete = all(isinstance(value.get(k), Mapping) for k in
                   ("lane_segments", "drivable_areas", "pedestrian_crossings"))
    for key, kind in (("lane_segments", "lane_segment"),
                      ("drivable_areas", "drivable_area"),
                      ("pedestrian_crossings", "pedestrian_crossing")):
        raw = value.get(key, {})
        if not isinstance(raw, Mapping):
            raise MapContractError(f"AV2 {key} must be an object keyed by ID")
        for dict_key, item in raw.items():
            if not isinstance(item, Mapping):
                raise MapContractError("AV2 map feature must be an object")
            fid = str(item.get("id", dict_key))
            if fid != str(dict_key):
                raise MapContractError(f"AV2 map {key} ID/key disagree")
            feature_id = f"{kind}:{fid}"
            geom = "polygon"
            verts: tuple[MapVertex, ...] = ()
            attrs: dict[str, Any] = {}
            successors = predecessors = left = right = ()
            if kind == "lane_segment":
                l = item.get("left_lane_boundary")
                r = item.get("right_lane_boundary")
                if l is not None and r is not None:
                    lv, rv = _polyline_json(l), _polyline_json(r)
                    if len(lv) >= 2 and len(rv) >= 2:
                        # The official AV2 lane polygon concatenates boundary
                        # polylines in opposite traversal directions.
                        verts = _polygon(tuple(lv) + tuple(reversed(rv)))
                predecessors = tuple(f"lane_segment:{x}" for x in item.get("predecessors", ()))
                successors = tuple(f"lane_segment:{x}" for x in item.get("successors", ()))
                left = (f"lane_segment:{item['left_neighbor_id']}",) if item.get("left_neighbor_id") is not None else ()
                right = (f"lane_segment:{item['right_neighbor_id']}",) if item.get("right_neighbor_id") is not None else ()
                attrs = {"lane_type": item.get("lane_type"),
                         "is_intersection": item.get("is_intersection"),
                         "left_mark_type": item.get("left_lane_mark_type"),
                         "right_mark_type": item.get("right_lane_mark_type"),
                         "polygon_is_boundary_stitch": True}
                if len(verts) >= 3:
                    primitives.append(MapPrimitive(f"{feature_id}:left", "lane_boundary_left", "polyline", lv))
                    primitives.append(MapPrimitive(f"{feature_id}:right", "lane_boundary_right", "polyline", rv))
            elif kind == "drivable_area":
                verts = _polygon(_vertices(item.get("area_boundary", ())))
            else:
                e1 = _polyline_json(item.get("edge1", {}))
                e2 = _polyline_json(item.get("edge2", {}))
                if len(e1) == 2 and len(e2) == 2:
                    verts = _polygon((e1[0], e1[1], e2[1], e2[0]))
            if len(verts) < 3:
                geom, verts, complete = "missing", (), False
            primitives.append(MapPrimitive(feature_id, kind, geom, verts,
                                           successors, predecessors, left, right, attrs))
    return MapContext("av2_motion", scenario_id, "av2_city_xy",
                      tuple(primitives), complete_geometry=(complete and bool(primitives)),
                      source_map_sha256=content_sha256)


def load_av2_map_file(path: str | Path, *, scenario_id: str) -> MapContext:
    path = Path(path)
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise MapContractError("AV2 map archive is not valid JSON") from exc
    return from_av2_map_json(value, scenario_id=scenario_id,
                            content_sha256=hashlib.sha256(raw).hexdigest())


__all__ = ["MapContractError", "MapVertex", "MapPrimitive", "SignalRecord",
           "MapContext", "from_womd_scenario", "from_av2_map_json", "load_av2_map_file"]
