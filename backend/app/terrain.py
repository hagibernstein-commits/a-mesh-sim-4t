"""3D Tactical Terrain, WGS84 Geodetic Projection, Thermal Entities, HV Power Lines & 720° Obstacle Raycasting."""

from __future__ import annotations
from dataclasses import dataclass
import math
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
from .specs import EVO_MAX_4T_SPECS

METERS_PER_DEG_LAT: float = 111320.0
DEFAULT_ORIGIN_LAT: float = 31.6935
DEFAULT_ORIGIN_LON: float = 34.9780
DEFAULT_ORIGIN_ALT_ASL: float = 335.0

_ACTIVE_ORIGIN: Dict[str, float] = {
    "lat": DEFAULT_ORIGIN_LAT,
    "lon": DEFAULT_ORIGIN_LON,
    "alt_asl": DEFAULT_ORIGIN_ALT_ASL,
}


def get_active_origin() -> Dict[str, float]:
    """Return a copy of the active simulator WGS84 geodetic origin."""
    return {
        "lat": float(_ACTIVE_ORIGIN["lat"]),
        "lon": float(_ACTIVE_ORIGIN["lon"]),
        "alt_asl": float(_ACTIVE_ORIGIN["alt_asl"]),
    }


def set_active_origin(
    lat: float,
    lon: float,
    alt_asl: Optional[float] = None,
) -> Dict[str, float]:
    """Update the active simulator WGS84 geodetic origin with validation."""
    lat_f = float(lat)
    lon_f = float(lon)
    if not (-90.0 <= lat_f <= 90.0):
        raise ValueError(f"Latitude must be between -90 and 90 degrees (got {lat_f})")
    if not (-180.0 <= lon_f <= 180.0):
        raise ValueError(f"Longitude must be between -180 and 180 degrees (got {lon_f})")
    _ACTIVE_ORIGIN["lat"] = lat_f
    _ACTIVE_ORIGIN["lon"] = lon_f
    if alt_asl is not None:
        _ACTIVE_ORIGIN["alt_asl"] = float(alt_asl)
    return get_active_origin()


def local_to_wgs84(
    x: float,
    z: float,
    origin_lat: Optional[float] = None,
    origin_lon: Optional[float] = None,
) -> Tuple[float, float]:
    """Convert local tactical meters (x East, z South) to WGS84 (lat, lon) degrees.

    Uses meridian/parallel scaling:
      d_lat = -z / 111,320.0
      d_lon =  x / (111,320.0 * cos(radians(origin_lat)))
    """
    o_lat = float(_ACTIVE_ORIGIN["lat"] if origin_lat is None else origin_lat)
    o_lon = float(_ACTIVE_ORIGIN["lon"] if origin_lon is None else origin_lon)
    cos_lat = max(math.cos(math.radians(o_lat)), 1e-6)
    d_lat = -float(z) / METERS_PER_DEG_LAT
    d_lon = float(x) / (METERS_PER_DEG_LAT * cos_lat)
    return (o_lat + d_lat, o_lon + d_lon)


def wgs84_to_local(
    lat: float,
    lon: float,
    origin_lat: Optional[float] = None,
    origin_lon: Optional[float] = None,
) -> Tuple[float, float]:
    """Convert WGS84 (lat, lon) degrees to local tactical meters (x East, z South)."""
    o_lat = float(_ACTIVE_ORIGIN["lat"] if origin_lat is None else origin_lat)
    o_lon = float(_ACTIVE_ORIGIN["lon"] if origin_lon is None else origin_lon)
    cos_lat = max(math.cos(math.radians(o_lat)), 1e-6)
    z = -(float(lat) - o_lat) * METERS_PER_DEG_LAT
    x = (float(lon) - o_lon) * (METERS_PER_DEG_LAT * cos_lat)
    return (x, z)


# Aliases for backward compatibility
local_to_gps = local_to_wgs84
gps_to_local = wgs84_to_local


@dataclass
class Building:
    id: str
    name: str
    x: float
    z: float
    width: float
    depth: float
    height: float
    base_elevation: float
    rotation_deg: float = 0.0
    category: str = "RESIDENTIAL"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "x": round(self.x, 2),
            "z": round(self.z, 2),
            "width": round(self.width, 2),
            "depth": round(self.depth, 2),
            "height": round(self.height, 2),
            "base_elevation": round(self.base_elevation, 2),
            "rotation_deg": round(self.rotation_deg, 1),
            "category": self.category,
        }


@dataclass
class ThermalEntity:
    id: str
    label: str
    category: str
    base_x: float
    base_z: float
    temp_c: float
    radius_m: float
    height_m: float
    patrol_rx: float = 0.0
    patrol_rz: float = 0.0
    patrol_omega: float = 0.0
    phase: float = 0.0
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def update(self, sim_time: float, terrain: "TacticalTerrain") -> None:
        if self.patrol_omega != 0.0:
            ang = sim_time * self.patrol_omega + self.phase
            self.x = self.base_x + math.cos(ang) * self.patrol_rx
            self.z = self.base_z + math.sin(ang) * self.patrol_rz
        else:
            self.x = self.base_x
            self.z = self.base_z
        self.y = terrain.get_elevation(self.x, self.z)

    def to_dict(self, terrain: Optional["TacticalTerrain"] = None) -> Dict[str, Any]:
        if terrain is not None:
            lat, lon = terrain.local_to_wgs84(self.x, self.z)
            alt_asl = terrain.origin_alt_asl + self.y
        else:
            lat, lon = local_to_wgs84(self.x, self.z)
            alt_asl = _ACTIVE_ORIGIN["alt_asl"] + self.y
        return {
            "id": self.id,
            "label": self.label,
            "category": self.category,
            "position": [round(self.x, 2), round(self.y, 2), round(self.z, 2)],
            "temp_c": round(self.temp_c, 1),
            "radius_m": round(self.radius_m, 2),
            "height_m": round(self.height_m, 2),
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "alt_asl": round(alt_asl, 2),
        }


@dataclass
class TransmissionPylon:
    id: str
    name: str
    x: float
    z: float
    base_elevation: float
    height: float
    crossarm_width: float = 14.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "x": round(self.x, 2),
            "z": round(self.z, 2),
            "base_elevation": round(self.base_elevation, 2),
            "height": round(self.height, 2),
            "crossarm_width": round(self.crossarm_width, 2),
        }


@dataclass
class PowerLineSpan:
    id: str
    name: str
    pylon_a_id: str
    pylon_b_id: str
    start_pos: List[float]
    end_pos: List[float]
    sag_m: float
    wire_diameter_mm: float = 15.0
    voltage_kv: int = 230
    conductors: int = 3

    def sample_points(self, num_samples: int = 24) -> List[List[float]]:
        pts: List[List[float]] = []
        p0 = np.array(self.start_pos, dtype=float)
        p1 = np.array(self.end_pos, dtype=float)
        for i in range(num_samples + 1):
            t = i / float(num_samples)
            pos = (1.0 - t) * p0 + t * p1
            sag_offset = 4.0 * self.sag_m * t * (1.0 - t)
            pos[1] -= sag_offset
            pts.append([round(float(pos[0]), 2), round(float(pos[1]), 2), round(float(pos[2]), 2)])
        return pts

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "pylon_a_id": self.pylon_a_id,
            "pylon_b_id": self.pylon_b_id,
            "start_pos": [round(v, 2) for v in self.start_pos],
            "end_pos": [round(v, 2) for v in self.end_pos],
            "sag_m": round(self.sag_m, 2),
            "wire_diameter_mm": round(self.wire_diameter_mm, 1),
            "voltage_kv": self.voltage_kv,
            "conductors": self.conductors,
            "points": self.sample_points(24),
        }


@dataclass
class CliffOutcrop:
    id: str
    name: str
    x: float
    z: float
    radius: float
    height: float
    base_elevation: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "x": round(self.x, 2),
            "z": round(self.z, 2),
            "radius": round(self.radius, 2),
            "height": round(self.height, 2),
            "base_elevation": round(self.base_elevation, 2),
        }


class TacticalTerrain:
    """Procedural 3D terrain of Giv'ot Eden & Emek HaEla (Route 375), Israel with limestone ridges, HV powerlines, and WGS84 datum."""

    def __init__(
        self,
        size_m: float = 1000.0,
        resolution: int = 80,
        origin_lat: float = DEFAULT_ORIGIN_LAT,
        origin_lon: float = DEFAULT_ORIGIN_LON,
        origin_alt_asl: float = DEFAULT_ORIGIN_ALT_ASL,
    ) -> None:
        self.size_m = size_m
        self.half_size = size_m / 2.0
        self.resolution = resolution
        self.origin_lat = float(origin_lat)
        self.origin_lon = float(origin_lon)
        self.origin_alt_asl = float(origin_alt_asl)
        set_active_origin(self.origin_lat, self.origin_lon, self.origin_alt_asl)

        # Ground Control Station (GCS-GIVOT-EDEN) on the central residential hilltop of Giv'ot Eden
        self.gcs_id: str = "GCS-GIVOT-EDEN"
        self.gcs_label: str = "GCS-GIVOT-EDEN (Giv'ot Eden Hilltop Command)"
        gcs_x, gcs_z = -215.0, 12.0
        gcs_ground = self.get_elevation(gcs_x, gcs_z)
        self.gcs_position = np.array([gcs_x, gcs_ground + 8.0, gcs_z], dtype=float)

        # Outer security perimeter fence line circling Giv'ot Eden (NW hilltop, main neighborhood, and eastern wing)
        self.perimeter_fence_xz: List[List[float]] = [
            [-332.0, -298.0],
            [-235.0, -312.0],
            [-212.0, -245.0],
            [-218.0, -95.0],
            [-145.0, -18.0],
            [-55.0, 42.0],
            [28.0, 74.0],
            [26.0, 102.0],
            [-85.0, 138.0],
            [-172.0, 206.0],
            [-268.0, 206.0],
            [-304.0, 128.0],
            [-298.0, -35.0],
            [-335.0, -225.0],
        ]

        # Valley road corridor centerline (Route 375 / Emek HaEla)
        self.valley_road_xz: List[List[float]] = [
            [118.0, -460.0],
            [128.0, -240.0],
            [138.0, -80.0],
            [148.0, 40.0],
            [162.0, 220.0],
            [176.0, 460.0],
        ]

        self.buildings: List[Building] = self._generate_buildings()
        self.thermal_entities: List[ThermalEntity] = self._generate_thermal_entities()
        self.pylons: List[TransmissionPylon] = self._generate_pylons()
        self.power_lines: List[PowerLineSpan] = self._generate_power_lines()
        self.cliff_outcrops: List[CliffOutcrop] = self._generate_cliff_outcrops()

    def set_origin(
        self,
        lat: float,
        lon: float,
        alt_asl: Optional[float] = None,
    ) -> Dict[str, float]:
        """Update the terrain and module-level active WGS84 geodetic origin."""
        updated = set_active_origin(lat, lon, alt_asl)
        self.origin_lat = updated["lat"]
        self.origin_lon = updated["lon"]
        self.origin_alt_asl = updated["alt_asl"]
        return updated

    def local_to_wgs84(self, x: float, z: float) -> Tuple[float, float]:
        return local_to_wgs84(x, z, self.origin_lat, self.origin_lon)

    def wgs84_to_local(self, lat: float, lon: float) -> Tuple[float, float]:
        return wgs84_to_local(lat, lon, self.origin_lat, self.origin_lon)

    def local_to_gps(self, x: float, z: float) -> Tuple[float, float]:
        return self.local_to_wgs84(x, z)

    def gps_to_local(self, lat: float, lon: float) -> Tuple[float, float]:
        return self.wgs84_to_local(lat, lon)

    def get_elevation(self, x: float, z: float) -> float:
        """Compute local 3D relief for Giv'ot Eden hillcrests, limestone ridge, and Emek HaEla valley floor."""
        # HaEla Limestone Escarpment / Ridge running N-S near x = -38m creating A-Mesh LOS shadow zones
        ridge_center_x = -38.0 + 16.0 * math.sin(z * 0.006)
        dx_ridge = x - ridge_center_x
        main_ridge = 118.0 * math.exp(-((dx_ridge / 74.0) ** 2)) * math.exp(-((z / 430.0) ** 2))

        # Secondary karst limestone crest modulation along the escarpment
        crest_mod = 14.0 * math.exp(-((dx_ridge / 40.0) ** 2)) * (0.55 + 0.45 * math.cos(z * 0.018))

        # Giv'ot Eden residential hilltop plateau (main bowl + northern hilltop spur)
        givot_eden_dome = 22.0 * math.exp(-(((x + 195.0) / 145.0) ** 2 + ((z - 45.0) / 195.0) ** 2))
        north_spur_dome = 18.0 * math.exp(-(((x + 285.0) / 85.0) ** 2 + ((z + 250.0) / 95.0) ** 2))

        # Lower Emek HaEla / Route 375 valley floor (east of ridge, x > 45m) with gentle rolling terraces
        valley_terrace = 4.0 * math.sin(x * 0.014) * math.cos(z * 0.014) + 14.5

        elev = valley_terrace + main_ridge + crest_mod + givot_eden_dome + north_spur_dome
        return max(8.0, float(elev))

    def get_elevation_asl(self, x: float, z: float) -> float:
        """Return real-world ASL elevation (m): ~340m–375m on Giv'ot Eden hillcrests, ~265m–295m in Emek HaEla valley."""
        # Smooth transition from Giv'ot Eden hilltop (~350-375m ASL) down into Emek HaEla valley (~265-295m ASL)
        valley_drop = 62.0 / (1.0 + math.exp(-(x - 28.0) / 34.0))
        local_h = self.get_elevation(x, z)
        return round(self.origin_alt_asl + (local_h * 0.32) - valley_drop + 12.0, 2)

    def sample_terrain(self, x: float, z: float) -> float:
        """Alias for get_elevation used by MissionPlanner."""
        return self.get_elevation(x, z)

    def _generate_buildings(self) -> List[Building]:
        # Specs: (id, name, x, z, width, depth, height, rotation_deg, category)
        specs: List[Tuple[str, str, float, float, float, float, float, float, str]] = [
            # --- 1. Central Command & Community Complex ---
            ("BLD-01", "GCS-GIVOT-EDEN Hilltop Command Center", -215.0, 12.0, 24.0, 18.0, 12.0, 28.0, "COMMAND"),
            # --- 2. Northern Hilltop Cluster (image_2.png) ---
            ("GE-NH-01", "North Hilltop Villa 01", -306.0, -264.0, 11.5, 10.0, 8.5, 28.0, "RESIDENTIAL"),
            ("GE-NH-02", "North Hilltop Villa 02", -292.0, -271.0, 11.5, 10.0, 8.5, 28.0, "RESIDENTIAL"),
            ("GE-NH-03", "North Hilltop Villa 03", -278.0, -278.0, 11.5, 10.0, 8.5, 28.0, "RESIDENTIAL"),
            ("GE-NH-04", "North Hilltop Villa 04", -264.0, -285.0, 11.5, 10.0, 8.5, 28.0, "RESIDENTIAL"),
            ("GE-NH-05", "North Hilltop Villa 05", -300.0, -246.0, 11.5, 10.0, 8.5, 28.0, "RESIDENTIAL"),
            ("GE-NH-06", "North Hilltop Villa 06", -286.0, -253.0, 11.5, 10.0, 8.5, 28.0, "RESIDENTIAL"),
            ("GE-NH-07", "North Hilltop Villa 07", -272.0, -260.0, 11.5, 10.0, 8.5, 28.0, "RESIDENTIAL"),
            ("GE-NH-08", "North Hilltop Villa 08", -288.0, -228.0, 11.5, 10.0, 8.5, 28.0, "RESIDENTIAL"),
            ("GE-NH-09", "North Hilltop Villa 09", -274.0, -235.0, 11.5, 10.0, 8.5, 28.0, "RESIDENTIAL"),
            ("GE-NH-10", "North Hilltop Villa 10", -260.0, -242.0, 11.5, 10.0, 8.5, 28.0, "RESIDENTIAL"),
            ("GE-NH-11", "North Hilltop Villa 11", -276.0, -211.0, 11.5, 10.0, 8.5, 28.0, "RESIDENTIAL"),
            ("GE-NH-12", "North Hilltop Villa 12", -262.0, -218.0, 11.5, 10.0, 8.5, 28.0, "RESIDENTIAL"),
            ("GE-NH-13", "North Hilltop Villa 13", -250.0, -226.0, 11.5, 10.0, 8.5, 28.0, "RESIDENTIAL"),
            ("GE-NH-14", "North Hilltop Perimeter Compound", -242.0, -296.0, 14.0, 14.0, 9.5, 28.0, "COMMAND"),
            # --- 3. NW Residential Quarter (image_3.png) ---
            ("GE-NW-01", "NW Arc Villa 01", -282.0, 5.0, 12.0, 10.5, 8.5, 15.0, "RESIDENTIAL"),
            ("GE-NW-02", "NW Arc Villa 02", -284.0, 24.0, 12.0, 10.5, 8.5, 5.0, "RESIDENTIAL"),
            ("GE-NW-03", "NW Arc Villa 03", -280.0, 43.0, 12.0, 10.5, 8.5, -12.0, "RESIDENTIAL"),
            ("GE-NW-04", "NW Row A Villa 01", -264.0, -12.0, 12.0, 10.5, 8.5, 28.0, "RESIDENTIAL"),
            ("GE-NW-05", "NW Row A Villa 02", -248.0, -20.0, 12.0, 10.5, 8.5, 28.0, "RESIDENTIAL"),
            ("GE-NW-06", "NW Row A Villa 03", -232.0, -28.0, 12.0, 10.5, 8.5, 28.0, "RESIDENTIAL"),
            ("GE-NW-07", "NW Row A Villa 04", -216.0, -36.0, 12.0, 10.5, 8.5, 28.0, "RESIDENTIAL"),
            ("GE-NW-08", "NW Row B Villa 01", -252.0, 8.0, 12.0, 10.5, 8.5, 28.0, "RESIDENTIAL"),
            ("GE-NW-09", "NW Row B Villa 02", -236.0, 0.0, 12.0, 10.5, 8.5, 28.0, "RESIDENTIAL"),
            ("GE-NW-10", "NW Row B Villa 03", -220.0, -8.0, 12.0, 10.5, 8.5, 28.0, "RESIDENTIAL"),
            ("GE-NW-11", "NW Row B Villa 04", -204.0, -16.0, 12.0, 10.5, 8.5, 28.0, "RESIDENTIAL"),
            ("GE-NW-12", "NW Flank Villa 01", -192.0, -38.0, 12.0, 10.5, 8.5, -30.0, "RESIDENTIAL"),
            ("GE-NW-13", "NW Flank Villa 02", -182.0, -22.0, 12.0, 10.5, 8.5, -30.0, "RESIDENTIAL"),
            ("GE-NW-14", "NW Flank Villa 03", -172.0, -6.0, 12.0, 10.5, 8.5, -30.0, "RESIDENTIAL"),
            ("GE-NW-15", "NW Central Villa 01", -240.0, 28.0, 12.0, 10.5, 8.5, 28.0, "RESIDENTIAL"),
            ("GE-NW-16", "NW Central Villa 02", -224.0, 36.0, 12.0, 10.5, 8.5, 28.0, "RESIDENTIAL"),
            ("GE-NW-17", "NW Central Villa 03", -208.0, 44.0, 12.0, 10.5, 8.5, 28.0, "RESIDENTIAL"),
            ("GE-NW-18", "NW Central Villa 04", -192.0, 52.0, 12.0, 10.5, 8.5, 28.0, "RESIDENTIAL"),
            ("GE-NW-19", "NW Central Villa 05", -226.0, 48.0, 12.0, 10.5, 8.5, 28.0, "RESIDENTIAL"),
            ("GE-NW-20", "NW Central Villa 06", -210.0, 56.0, 12.0, 10.5, 8.5, 28.0, "RESIDENTIAL"),
            ("GE-NW-21", "NW Central Villa 07", -194.0, 64.0, 12.0, 10.5, 8.5, 28.0, "RESIDENTIAL"),
            ("GE-NW-22", "NW Central Villa 08", -178.0, 72.0, 12.0, 10.5, 8.5, 28.0, "RESIDENTIAL"),
            ("GE-NW-23", "NW South Arc Villa 01", -262.0, 62.0, 12.0, 10.5, 8.5, 20.0, "RESIDENTIAL"),
            ("GE-NW-24", "NW South Arc Villa 02", -246.0, 68.0, 12.0, 10.5, 8.5, 20.0, "RESIDENTIAL"),
            ("GE-NW-25", "NW South Arc Villa 03", -230.0, 74.0, 12.0, 10.5, 8.5, 20.0, "RESIDENTIAL"),
            ("GE-NW-26", "NW South Arc Villa 04", -214.0, 80.0, 12.0, 10.5, 8.5, 20.0, "RESIDENTIAL"),
            # --- 4. South-Central Residential Bowl (image_4.png left/center) ---
            ("GE-SC-01", "South-West Curve Villa 01", -270.0, 148.0, 12.0, 10.5, 8.5, 12.0, "RESIDENTIAL"),
            ("GE-SC-02", "South-West Curve Villa 02", -262.0, 166.0, 12.0, 10.5, 8.5, 25.0, "RESIDENTIAL"),
            ("GE-SC-03", "South-West Curve Villa 03", -250.0, 180.0, 12.0, 10.5, 8.5, 38.0, "RESIDENTIAL"),
            ("GE-SC-04", "South-West Curve Villa 04", -234.0, 189.0, 12.0, 10.5, 8.5, 15.0, "RESIDENTIAL"),
            ("GE-SC-05", "South-West Curve Villa 05", -216.0, 193.0, 12.0, 10.5, 8.5, 5.0, "RESIDENTIAL"),
            ("GE-SC-06", "South Bowl Row 1 Villa 01", -256.0, 102.0, 12.0, 10.5, 8.5, 22.0, "RESIDENTIAL"),
            ("GE-SC-07", "South Bowl Row 1 Villa 02", -238.0, 109.0, 12.0, 10.5, 8.5, 22.0, "RESIDENTIAL"),
            ("GE-SC-08", "South Bowl Row 1 Villa 03", -220.0, 116.0, 12.0, 10.5, 8.5, 22.0, "RESIDENTIAL"),
            ("GE-SC-09", "South Bowl Row 1 Villa 04", -202.0, 123.0, 12.0, 10.5, 8.5, 22.0, "RESIDENTIAL"),
            ("GE-SC-10", "South Bowl Row 1 Villa 05", -184.0, 130.0, 12.0, 10.5, 8.5, 22.0, "RESIDENTIAL"),
            ("GE-SC-11", "South Bowl Row 2 Villa 01", -250.0, 122.0, 12.0, 10.5, 8.5, 22.0, "RESIDENTIAL"),
            ("GE-SC-12", "South Bowl Row 2 Villa 02", -232.0, 129.0, 12.0, 10.5, 8.5, 22.0, "RESIDENTIAL"),
            ("GE-SC-13", "South Bowl Row 2 Villa 03", -214.0, 136.0, 12.0, 10.5, 8.5, 22.0, "RESIDENTIAL"),
            ("GE-SC-14", "South Bowl Row 2 Villa 04", -196.0, 143.0, 12.0, 10.5, 8.5, 22.0, "RESIDENTIAL"),
            ("GE-SC-15", "South Bowl Row 2 Villa 05", -178.0, 150.0, 12.0, 10.5, 8.5, 22.0, "RESIDENTIAL"),
            ("GE-SC-16", "South Bowl Row 3 Villa 01", -244.0, 142.0, 12.0, 10.5, 8.5, 22.0, "RESIDENTIAL"),
            ("GE-SC-17", "South Bowl Row 3 Villa 02", -226.0, 149.0, 12.0, 10.5, 8.5, 22.0, "RESIDENTIAL"),
            ("GE-SC-18", "South Bowl Row 3 Villa 03", -208.0, 156.0, 12.0, 10.5, 8.5, 22.0, "RESIDENTIAL"),
            ("GE-SC-19", "South Bowl Row 3 Villa 04", -190.0, 163.0, 12.0, 10.5, 8.5, 22.0, "RESIDENTIAL"),
            ("GE-SC-20", "South Bowl Row 3 Villa 05", -172.0, 170.0, 12.0, 10.5, 8.5, 22.0, "RESIDENTIAL"),
            ("GE-SC-21", "South Bowl Row 4 Villa 01", -234.0, 164.0, 12.0, 10.5, 8.5, 22.0, "RESIDENTIAL"),
            ("GE-SC-22", "South Bowl Row 4 Villa 02", -216.0, 171.0, 12.0, 10.5, 8.5, 22.0, "RESIDENTIAL"),
            ("GE-SC-23", "South Bowl Row 4 Villa 03", -198.0, 178.0, 12.0, 10.5, 8.5, 22.0, "RESIDENTIAL"),
            ("GE-SC-24", "South Bowl Row 4 Villa 04", -180.0, 185.0, 12.0, 10.5, 8.5, 22.0, "RESIDENTIAL"),
            ("GE-SC-25", "South Bowl East Flank 01", -162.0, 118.0, 12.0, 10.5, 8.5, 22.0, "RESIDENTIAL"),
            ("GE-SC-26", "South Bowl East Flank 02", -156.0, 138.0, 12.0, 10.5, 8.5, 22.0, "RESIDENTIAL"),
            ("GE-SC-27", "South Bowl East Flank 03", -150.0, 158.0, 12.0, 10.5, 8.5, 22.0, "RESIDENTIAL"),
            ("GE-SC-28", "South Bowl East Flank 04", -158.0, 176.0, 12.0, 10.5, 8.5, 22.0, "RESIDENTIAL"),
            # --- 5. Central-East Block (image_4.png middle) ---
            ("GE-CE-01", "Central-East Villa 01", -134.0, 58.0, 12.0, 10.5, 8.5, -18.0, "RESIDENTIAL"),
            ("GE-CE-02", "Central-East Villa 02", -118.0, 63.0, 12.0, 10.5, 8.5, -18.0, "RESIDENTIAL"),
            ("GE-CE-03", "Central-East Villa 03", -102.0, 68.0, 12.0, 10.5, 8.5, -18.0, "RESIDENTIAL"),
            ("GE-CE-04", "Central-East Villa 04", -86.0, 73.0, 12.0, 10.5, 8.5, -18.0, "RESIDENTIAL"),
            ("GE-CE-05", "Central-East Villa 05", -140.0, 78.0, 12.0, 10.5, 8.5, -18.0, "RESIDENTIAL"),
            ("GE-CE-06", "Central-East Villa 06", -124.0, 83.0, 12.0, 10.5, 8.5, -18.0, "RESIDENTIAL"),
            ("GE-CE-07", "Central-East Villa 07", -108.0, 88.0, 12.0, 10.5, 8.5, -18.0, "RESIDENTIAL"),
            ("GE-CE-08", "Central-East Villa 08", -92.0, 93.0, 12.0, 10.5, 8.5, -18.0, "RESIDENTIAL"),
            ("GE-CE-09", "Central-East Villa 09", -146.0, 98.0, 12.0, 10.5, 8.5, -18.0, "RESIDENTIAL"),
            ("GE-CE-10", "Central-East Villa 10", -130.0, 103.0, 12.0, 10.5, 8.5, -18.0, "RESIDENTIAL"),
            ("GE-CE-11", "Central-East Villa 11", -114.0, 108.0, 12.0, 10.5, 8.5, -18.0, "RESIDENTIAL"),
            ("GE-CE-12", "Central-East Villa 12", -98.0, 113.0, 12.0, 10.5, 8.5, -18.0, "RESIDENTIAL"),
            # --- 6. Eastern Extension Wing (image_4.png right) ---
            ("GE-EW-01", "East Wing Villa 01", -64.0, 68.0, 11.5, 10.0, 8.5, -18.0, "RESIDENTIAL"),
            ("GE-EW-02", "East Wing Villa 02", -48.0, 72.0, 11.5, 10.0, 8.5, -18.0, "RESIDENTIAL"),
            ("GE-EW-03", "East Wing Villa 03", -32.0, 76.0, 11.5, 10.0, 8.5, -18.0, "RESIDENTIAL"),
            ("GE-EW-04", "East Wing Villa 04", -16.0, 80.0, 11.5, 10.0, 8.5, -18.0, "RESIDENTIAL"),
            ("GE-EW-05", "East Wing Villa 05", -60.0, 86.0, 11.5, 10.0, 8.5, -18.0, "RESIDENTIAL"),
            ("GE-EW-06", "East Wing Villa 06", -44.0, 90.0, 11.5, 10.0, 8.5, -18.0, "RESIDENTIAL"),
            ("GE-EW-07", "East Wing Villa 07", -28.0, 94.0, 11.5, 10.0, 8.5, -18.0, "RESIDENTIAL"),
            ("GE-EW-08", "East Wing Villa 08", -14.0, 97.0, 11.5, 10.0, 8.5, -18.0, "RESIDENTIAL"),
            ("GE-EW-09", "East Wing Villa 09", -54.0, 102.0, 11.5, 10.0, 8.5, -18.0, "RESIDENTIAL"),
            ("GE-EW-10", "East Wing Villa 10", -38.0, 106.0, 11.5, 10.0, 8.5, -18.0, "RESIDENTIAL"),
            ("GE-EW-11", "East Wing Villa 11", -22.0, 109.0, 11.5, 10.0, 8.5, -18.0, "RESIDENTIAL"),
            # --- 7. Emek HaEla / Route 375 Valley Infrastructure ---
            ("BLD-V1", "Route 375 Agricultural Warehouse", 105.0, -55.0, 24.0, 18.0, 14.0, 0.0, "INFRASTRUCTURE"),
            ("BLD-V2", "Emek HaEla Regional Grid Substation", 145.0, -15.0, 28.0, 24.0, 19.0, 0.0, "INFRASTRUCTURE"),
            ("BLD-V3", "Elah Valley Field Logistics Hangar", 165.0, 35.0, 30.0, 20.0, 17.0, 0.0, "INFRASTRUCTURE"),
            ("BLD-V4", "Route 375 East Observation Watchtower", 235.0, -25.0, 14.0, 14.0, 28.0, 0.0, "INFRASTRUCTURE"),
        ]
        buildings: List[Building] = []
        for bid, name, x, z, w, d, h, rot, cat in specs:
            base = self.get_elevation(x, z)
            buildings.append(Building(bid, name, x, z, w, d, h, base, rot, cat))
        return buildings

    def _generate_thermal_entities(self) -> List[ThermalEntity]:
        entities = [
            ThermalEntity(
                id="THM-01",
                label="Route 375 Armored Security Convoy (APC)",
                category="VEHICLE_ARMOR",
                base_x=115.0,
                base_z=-20.0,
                temp_c=68.5,
                radius_m=5.5,
                height_m=3.6,
                patrol_rx=18.0,
                patrol_rz=10.0,
                patrol_omega=0.14,
                phase=0.0,
            ),
            ThermalEntity(
                id="THM-02",
                label="Route 375 Tactical Patrol Pickup",
                category="VEHICLE_SUPPORT",
                base_x=168.0,
                base_z=18.0,
                temp_c=63.2,
                radius_m=5.0,
                height_m=3.4,
                patrol_rx=16.0,
                patrol_rz=14.0,
                patrol_omega=-0.12,
                phase=1.2,
            ),
            ThermalEntity(
                id="THM-03",
                label="Emek HaEla Substation Diesel Generator",
                category="INFRASTRUCTURE_HEAT",
                base_x=145.0,
                base_z=-15.0,
                temp_c=84.5,
                radius_m=6.0,
                height_m=4.5,
                patrol_rx=0.0,
                patrol_rz=0.0,
                patrol_omega=0.0,
                phase=0.0,
            ),
            ThermalEntity(
                id="THM-04",
                label="Emek HaEla Perimeter Foot Patrol (SAR)",
                category="PERSONNEL_SAR",
                base_x=135.0,
                base_z=38.0,
                temp_c=37.2,
                radius_m=4.2,
                height_m=2.2,
                patrol_rx=12.0,
                patrol_rz=9.0,
                patrol_omega=0.18,
                phase=2.4,
            ),
        ]
        for ent in entities:
            ent.update(0.0, self)
        return entities

    def _generate_pylons(self) -> List[TransmissionPylon]:
        coords = [
            ("PYLON-1", "Emek HaEla HV Tower North-West", 75.0, -95.0, 42.0),
            ("PYLON-2", "Route 375 HV Tower Center-West", 95.0, 5.0, 44.0),
            ("PYLON-3", "Route 375 HV Tower Center-East", 195.0, -5.0, 44.0),
            ("PYLON-4", "Emek HaEla HV Tower South-East", 215.0, 95.0, 42.0),
        ]
        pylons: List[TransmissionPylon] = []
        for pid, name, x, z, h in coords:
            base = self.get_elevation(x, z)
            pylons.append(TransmissionPylon(pid, name, x, z, base, h))
        return pylons

    def _generate_power_lines(self) -> List[PowerLineSpan]:
        p_map = {p.id: p for p in self.pylons}
        p1, p2, p3, p4 = p_map["PYLON-1"], p_map["PYLON-2"], p_map["PYLON-3"], p_map["PYLON-4"]
        return [
            PowerLineSpan(
                id="WIRE-SPAN-1",
                name="161kV Emek HaEla Cross-Valley HV Line (15mm ACSR)",
                pylon_a_id=p1.id,
                pylon_b_id=p2.id,
                start_pos=[p1.x, p1.base_elevation + p1.height - 4.0, p1.z],
                end_pos=[p2.x, p2.base_elevation + p2.height - 4.0, p2.z],
                sag_m=6.5,
                wire_diameter_mm=15.0,
                voltage_kv=161,
            ),
            PowerLineSpan(
                id="WIRE-SPAN-2",
                name="400kV Route 375 Substation Feeder HV Line (15mm ACSR)",
                pylon_a_id=p2.id,
                pylon_b_id=p3.id,
                start_pos=[p2.x, p2.base_elevation + p2.height - 3.5, p2.z],
                end_pos=[p3.x, p3.base_elevation + p3.height - 3.5, p3.z],
                sag_m=7.0,
                wire_diameter_mm=15.0,
                voltage_kv=400,
            ),
            PowerLineSpan(
                id="WIRE-SPAN-3",
                name="400kV Emek HaEla East Corridor HV Line (15mm ACSR)",
                pylon_a_id=p3.id,
                pylon_b_id=p4.id,
                start_pos=[p3.x, p3.base_elevation + p3.height - 4.0, p3.z],
                end_pos=[p4.x, p4.base_elevation + p4.height - 4.0, p4.z],
                sag_m=6.5,
                wire_diameter_mm=15.0,
                voltage_kv=400,
            ),
        ]

    def _generate_cliff_outcrops(self) -> List[CliffOutcrop]:
        specs = [
            ("OUTCROP-1", "Giv'ot Eden North Limestone Escarpment", -35.0, -75.0, 16.0, 26.0),
            ("OUTCROP-2", "HaEla Central Limestone Ridge Crest", -22.0, 15.0, 15.0, 24.0),
            ("OUTCROP-3", "Tel Sokho Karst Bluff", 62.0, -18.0, 13.0, 28.0),
        ]
        outcrops: List[CliffOutcrop] = []
        for oid, name, x, z, r, h in specs:
            base = self.get_elevation(x, z)
            outcrops.append(CliffOutcrop(oid, name, x, z, r, h, base))
        return outcrops

    def check_los(self, p1: np.ndarray, p2: np.ndarray, num_samples: int = 48) -> Tuple[bool, float, List[float]]:
        """Check Line-of-Sight between two 3D points across the Giv'ot Eden / Emek HaEla limestone ridges."""
        max_obstruction_m = 0.0
        worst_point = [float((p1[0] + p2[0]) * 0.5), float((p1[1] + p2[1]) * 0.5), float((p1[2] + p2[2]) * 0.5)]
        for i in range(1, num_samples):
            t = i / float(num_samples)
            pt = (1.0 - t) * p1 + t * p2
            terr_h = self.get_elevation(float(pt[0]), float(pt[2]))
            diff = terr_h - float(pt[1])
            if diff > max_obstruction_m:
                max_obstruction_m = diff
                worst_point = [round(float(pt[0]), 2), round(float(terr_h), 2), round(float(pt[2]), 2)]
        has_los = max_obstruction_m <= 0.0
        return has_los, round(float(max_obstruction_m), 2), worst_point

    def scan_720_obstacles(
        self,
        drone_pos: np.ndarray,
        ambient_lux: float = 650.0,
    ) -> Dict[str, Any]:
        """Evaluate 720° Omnidirectional Perception (Binocular Fisheye + 60GHz/24GHz mmWave Radar)."""
        fisheye_active = ambient_lux >= EVO_MAX_4T_SPECS.fisheye_min_lux
        mmwave_active = True
        fisheye_range = EVO_MAX_4T_SPECS.fisheye_range_m if fisheye_active else 0.0
        mmwave_range = EVO_MAX_4T_SPECS.mmwave_range_m

        contacts: List[Dict[str, Any]] = []
        repulsive_vec = np.zeros(3, dtype=float)
        closest_dist = 999.0
        primary_threat: Optional[Dict[str, Any]] = None

        # 1. Check High-Voltage Power-Line Catenary Spans (15mm wires — mmWave always detects >= 12.7mm)
        for span in self.power_lines:
            pts = span.sample_points(20)
            best_span_dist = 999.0
            best_pt: Optional[np.ndarray] = None
            for pt_list in pts:
                pt = np.array(pt_list, dtype=float)
                d = float(np.linalg.norm(drone_pos - pt))
                if d < best_span_dist:
                    best_span_dist = d
                    best_pt = pt
            if best_pt is not None and best_span_dist <= mmwave_range:
                detected_by = "FISHEYE+RADAR" if (fisheye_active and best_span_dist <= fisheye_range) else "MMWAVE_RADAR_60GHZ"
                contact = {
                    "id": span.id,
                    "label": span.name,
                    "type": "HV_POWERLINE",
                    "distance_m": round(best_span_dist, 2),
                    "wire_diameter_mm": span.wire_diameter_mm,
                    "position": [round(float(best_pt[0]), 2), round(float(best_pt[1]), 2), round(float(best_pt[2]), 2)],
                    "detected_by": detected_by,
                }
                contacts.append(contact)
                if best_span_dist < closest_dist:
                    closest_dist = best_span_dist
                    primary_threat = contact
                if best_span_dist < 26.0:
                    # Climb safely over suspended HV conductors
                    strength = max(0.0, (26.0 - best_span_dist) / 26.0)
                    repulsive_vec[1] += 6.5 * strength + 1.8

        # 2. Check Transmission Pylons
        for pylon in self.pylons:
            top_y = pylon.base_elevation + pylon.height
            clamped_y = min(max(float(drone_pos[1]), pylon.base_elevation), top_y)
            nearest = np.array([pylon.x, clamped_y, pylon.z], dtype=float)
            d = float(np.linalg.norm(drone_pos - nearest))
            if d <= mmwave_range:
                detected_by = "FISHEYE+RADAR" if (fisheye_active and d <= fisheye_range) else "MMWAVE_RADAR_60GHZ"
                contact = {
                    "id": pylon.id,
                    "label": pylon.name,
                    "type": "PYLON_TOWER",
                    "distance_m": round(d, 2),
                    "position": [round(float(nearest[0]), 2), round(float(nearest[1]), 2), round(float(nearest[2]), 2)],
                    "detected_by": detected_by,
                }
                contacts.append(contact)
                if d < closest_dist:
                    closest_dist = d
                    primary_threat = contact
                if d < 24.0:
                    diff = drone_pos - nearest
                    norm = max(float(np.linalg.norm(diff)), 1.0)
                    repulsive_vec += (diff / norm) * ((24.0 - d) * 0.35)
                    repulsive_vec[1] += 2.5

        # 3. Check Cliff Outcrops & Buildings
        for outcrop in self.cliff_outcrops:
            top_y = outcrop.base_elevation + outcrop.height
            clamped_y = min(max(float(drone_pos[1]), outcrop.base_elevation), top_y)
            nearest = np.array([outcrop.x, clamped_y, outcrop.z], dtype=float)
            d = max(0.5, float(np.linalg.norm(drone_pos - nearest)) - outcrop.radius)
            if d <= mmwave_range:
                detected_by = "FISHEYE+RADAR" if (fisheye_active and d <= fisheye_range) else "MMWAVE_RADAR_60GHZ"
                contact = {
                    "id": outcrop.id,
                    "label": outcrop.name,
                    "type": "CLIFF_OUTCROP",
                    "distance_m": round(d, 2),
                    "position": [round(float(nearest[0]), 2), round(float(nearest[1]), 2), round(float(nearest[2]), 2)],
                    "detected_by": detected_by,
                }
                contacts.append(contact)
                if d < closest_dist:
                    closest_dist = d
                    primary_threat = contact
                if d < 22.0:
                    diff = drone_pos - nearest
                    norm = max(float(np.linalg.norm(diff)), 1.0)
                    repulsive_vec += (diff / norm) * ((22.0 - d) * 0.4)
                    repulsive_vec[1] += 2.2

        for bld in self.buildings:
            top_y = bld.base_elevation + bld.height
            if float(drone_pos[1]) <= top_y + 14.0:
                clamped_y = min(max(float(drone_pos[1]), bld.base_elevation), top_y)
                nearest = np.array([bld.x, clamped_y, bld.z], dtype=float)
                d = max(0.5, float(np.linalg.norm(drone_pos - nearest)) - max(bld.width, bld.depth) * 0.5)
                if d <= mmwave_range:
                    detected_by = "FISHEYE+RADAR" if (fisheye_active and d <= fisheye_range) else "MMWAVE_RADAR_60GHZ"
                    contact = {
                        "id": bld.id,
                        "label": bld.name,
                        "type": "URBAN_STRUCTURE",
                        "distance_m": round(d, 2),
                        "position": [round(float(nearest[0]), 2), round(float(nearest[1]), 2), round(float(nearest[2]), 2)],
                        "detected_by": detected_by,
                    }
                    contacts.append(contact)
                    if d < closest_dist:
                        closest_dist = d
                        primary_threat = contact
                    if d < 18.0:
                        repulsive_vec[1] += 3.5

        contacts.sort(key=lambda c: c["distance_m"])
        apas_active = float(np.linalg.norm(repulsive_vec)) > 0.1
        if apas_active and primary_threat is not None:
            apas_status = f"CLIMBING ({primary_threat['detected_by']})"
        elif fisheye_active:
            apas_status = "NOMINAL (720° FISHEYE+RADAR)"
        else:
            apas_status = "LOW-LIGHT RADAR GUARD (60GHz)"

        return {
            "fisheye_status": "ACTIVE" if fisheye_active else "LOW-LIGHT BLIND",
            "mmwave_status": "ACTIVE (≥12.7mm WIRE)",
            "ambient_lux": round(ambient_lux, 1),
            "closest_obstacle_m": round(closest_dist, 2) if contacts else None,
            "apas_active": apas_active,
            "apas_status": apas_status,
            "avoidance_vector": [
                round(float(repulsive_vec[0]), 2),
                round(float(repulsive_vec[1]), 2),
                round(float(repulsive_vec[2]), 2),
            ],
            "primary_threat": primary_threat,
            "contacts": contacts[:6],
        }

    def raycast_lrf(
        self,
        origin: np.ndarray,
        pitch_deg: float,
        yaw_deg: float,
        max_range_m: float = 1200.0,
    ) -> Dict[str, Any]:
        """Raycast 1200m Laser Rangefinder from drone gimbal and return local + WGS84 target coordinates."""
        pitch_rad = math.radians(pitch_deg)
        yaw_rad = math.radians(yaw_deg)

        dx = math.cos(pitch_rad) * math.cos(yaw_rad)
        dy = math.sin(pitch_rad)
        dz = math.cos(pitch_rad) * math.sin(yaw_rad)
        ray_dir = np.array([dx, dy, dz], dtype=float)
        norm = np.linalg.norm(ray_dir)
        if norm > 1e-6:
            ray_dir /= norm

        # First check proximity to thermal entities & buildings along ray
        best_hit_pos: Optional[np.ndarray] = None
        best_dist: float = max_range_m
        best_label = "Terrain Surface"
        best_id = "TERRAIN"
        best_temp_c = 18.5

        for ent in self.thermal_entities:
            ent_pos = np.array([ent.x, ent.y + ent.height_m * 0.5, ent.z], dtype=float)
            to_ent = ent_pos - origin
            proj = float(np.dot(to_ent, ray_dir))
            if 5.0 <= proj <= max_range_m:
                closest_pt = origin + ray_dir * proj
                perp_dist = float(np.linalg.norm(closest_pt - ent_pos))
                if perp_dist <= max(ent.radius_m * 2.2, 12.0) and proj < best_dist:
                    best_dist = proj
                    best_hit_pos = ent_pos
                    best_label = ent.label
                    best_id = ent.id
                    best_temp_c = ent.temp_c

        if best_hit_pos is None:
            for bld in self.buildings:
                bld_pos = np.array([bld.x, bld.base_elevation + bld.height * 0.5, bld.z], dtype=float)
                to_bld = bld_pos - origin
                proj = float(np.dot(to_bld, ray_dir))
                if 5.0 <= proj <= max_range_m:
                    closest_pt = origin + ray_dir * proj
                    perp_dist = float(np.linalg.norm(closest_pt - bld_pos))
                    if perp_dist <= max(bld.width, bld.depth) * 0.75 and proj < best_dist:
                        best_dist = proj
                        best_hit_pos = closest_pt
                        best_label = f"{bld.id} {bld.name}"
                        best_id = bld.id
                        best_temp_c = 27.4

        # March ray against terrain heightmap if no entity/structure hit closer
        if best_hit_pos is None:
            step_m = 4.0
            steps = int(max_range_m / step_m)
            for i in range(1, steps + 1):
                d = i * step_m
                pt = origin + ray_dir * d
                terr_y = self.get_elevation(float(pt[0]), float(pt[2]))
                if float(pt[1]) <= terr_y:
                    best_dist = d
                    best_hit_pos = np.array([float(pt[0]), terr_y, float(pt[2])], dtype=float)
                    break

        if best_hit_pos is None:
            best_hit_pos = origin + ray_dir * 250.0
            best_hit_pos[1] = max(best_hit_pos[1], self.get_elevation(float(best_hit_pos[0]), float(best_hit_pos[2])))
            best_dist = float(np.linalg.norm(best_hit_pos - origin))

        hit_x, hit_y, hit_z = float(best_hit_pos[0]), float(best_hit_pos[1]), float(best_hit_pos[2])
        target_lat, target_lon = self.local_to_wgs84(hit_x, hit_z)
        target_alt_asl = self.origin_alt_asl + hit_y

        return {
            "valid": True,
            "slant_range_m": round(best_dist, 1),
            "target_id": best_id,
            "target_label": best_label,
            "target_temp_c": round(best_temp_c, 1),
            "target_pos": [round(hit_x, 2), round(hit_y, 2), round(hit_z, 2)],
            "target_lat": round(target_lat, 6),
            "target_lon": round(target_lon, 6),
            "target_alt_asl": round(target_alt_asl, 1),
            "target_alt_local_m": round(hit_y, 1),
        }

    def export_heightmap(self) -> Dict[str, Any]:
        """Serialize the 3D terrain mesh, obstacles, thermal entities, and geodetic origin."""
        xs = np.linspace(-self.half_size, self.half_size, self.resolution)
        zs = np.linspace(-self.half_size, self.half_size, self.resolution)
        grid: List[List[float]] = []
        for z in zs:
            row = [round(self.get_elevation(float(x), float(z)), 2) for x in xs]
            grid.append(row)

        gcs_lat, gcs_lon = self.local_to_wgs84(float(self.gcs_position[0]), float(self.gcs_position[2]))
        return {
            "sector_name": "Giv'ot Eden / Emek HaEla (Route 375), Israel",
            "size_m": self.size_m,
            "resolution": self.resolution,
            "origin_lat": round(self.origin_lat, 7),
            "origin_lon": round(self.origin_lon, 7),
            "origin_alt_asl": round(self.origin_alt_asl, 2),
            "geodetic_origin": {
                "lat": round(self.origin_lat, 7),
                "lon": round(self.origin_lon, 7),
                "alt_asl": round(self.origin_alt_asl, 2),
            },
            "gcs_id": self.gcs_id,
            "gcs_label": self.gcs_label,
            "gcs_position": [round(float(v), 2) for v in self.gcs_position],
            "gcs_wgs84": {
                "lat": round(gcs_lat, 7),
                "lon": round(gcs_lon, 7),
                "alt_asl": round(self.origin_alt_asl + float(self.gcs_position[1]), 2),
            },
            "perimeter_fence_xz": self.perimeter_fence_xz,
            "valley_road_xz": self.valley_road_xz,
            "heights": grid,
            "buildings": [b.to_dict() for b in self.buildings],
            "thermal_entities": [e.to_dict(self) for e in self.thermal_entities],
            "pylons": [p.to_dict() for p in self.pylons],
            "power_lines": [s.to_dict() for s in self.power_lines],
            "cliff_outcrops": [c.to_dict() for c in self.cliff_outcrops],
        }
