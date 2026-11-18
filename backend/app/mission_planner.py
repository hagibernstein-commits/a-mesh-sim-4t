"""Cooperative Multi-UAV SAR Polygon Grid Planner, Dynamic Relay Re-Tasking & Autel KML/WPML (.kmz) I/O."""

from __future__ import annotations
import io
import math
import time
import xml.etree.ElementTree as ET
import zipfile
from typing import Dict, List, Any, Optional, Tuple
import numpy as np

from .specs import EVO_MAX_4T_SPECS
from .terrain import (
    TacticalTerrain,
    METERS_PER_DEG_LAT,
    DEFAULT_ORIGIN_LAT,
    DEFAULT_ORIGIN_LON,
    DEFAULT_ORIGIN_ALT_ASL,
    get_active_origin,
    set_active_origin,
    local_to_wgs84,
    wgs84_to_local,
    local_to_gps,
    gps_to_local,
)

# Canonical 4-stake East Tactical Valley polygon (160m x 140m = 22,400 m^2)
VALLEY_POLYGON: List[List[float]] = [
    [60.0, -70.0],
    [220.0, -70.0],
    [220.0, 70.0],
    [60.0, 70.0],
]


def compute_swath(
    altitude_agl_m: float,
    sensor_mode: str = "THERMAL",
    sidelap_pct: float = 70.0,
) -> Dict[str, float]:
    """Compute ground sensor swath width W = 2*h*tan(FOV/2) and lane spacing d = W*(1 - sidelap)."""
    h = max(10.0, min(500.0, float(altitude_agl_m)))
    sidelap = max(0.1, min(0.92, float(sidelap_pct) / 100.0))
    fov_deg = (
        EVO_MAX_4T_SPECS.thermal_fov_deg
        if str(sensor_mode).upper() == "THERMAL"
        else EVO_MAX_4T_SPECS.wide_fov_deg
    )
    fov_rad = math.radians(fov_deg)
    swath_width_m = 2.0 * h * math.tan(fov_rad * 0.5)
    lane_spacing_m = max(4.0, swath_width_m * (1.0 - sidelap))
    return {
        "altitude_agl_m": round(h, 2),
        "fov_deg": round(fov_deg, 1),
        "sidelap_pct": round(sidelap * 100.0, 1),
        "swath_width_m": round(swath_width_m, 2),
        "lane_spacing_m": round(lane_spacing_m, 2),
    }


def polygon_area_m2(polygon_xz: List[List[float]]) -> float:
    """Compute 2D polygon area in square meters using the Shoelace formula."""
    n = len(polygon_xz)
    if n < 3:
        return 0.0
    area2 = 0.0
    for i in range(n):
        x1, z1 = polygon_xz[i]
        x2, z2 = polygon_xz[(i + 1) % n]
        area2 += x1 * z2 - x2 * z1
    return round(abs(area2) * 0.5, 2)


def polygon_centroid_xz(polygon_xz: List[List[float]]) -> Tuple[float, float]:
    """Compute centroid (cx, cz) of a 2D polygon in local meters."""
    if not polygon_xz:
        return (0.0, 0.0)
    cx = sum(float(p[0]) for p in polygon_xz) / len(polygon_xz)
    cz = sum(float(p[1]) for p in polygon_xz) / len(polygon_xz)
    return (cx, cz)


def point_in_polygon(x: float, z: float, polygon_xz: List[List[float]]) -> bool:
    """Ray-casting point-in-polygon check (inclusive of boundary edges)."""
    n = len(polygon_xz)
    if n < 3:
        return False
    inside = False
    j = n - 1
    for i in range(n):
        xi, zi = float(polygon_xz[i][0]), float(polygon_xz[i][1])
        xj, zj = float(polygon_xz[j][0]), float(polygon_xz[j][1])
        # Check proximity to segment
        dx, dz = xj - xi, zj - zi
        seg_len2 = dx * dx + dz * dz
        if seg_len2 > 1e-9:
            t = max(0.0, min(1.0, ((x - xi) * dx + (z - zi) * dz) / seg_len2))
            px, pz = xi + t * dx, zi + t * dz
            if math.hypot(x - px, z - pz) <= 1e-3:
                return True
        intersect = ((zi > z) != (zj > z)) and (x < (xj - xi) * (z - zi) / ((zj - zi) + 1e-12) + xi)
        if intersect:
            inside = not inside
        j = i
    return inside


def generate_lawnmower(
    polygon_xz: List[List[float]],
    altitude_agl_m: float = 60.0,
    sensor_mode: str = "THERMAL",
    sidelap_pct: float = 70.0,
    sweep_angle_deg: float = 0.0,
    terrain: Optional[TacticalTerrain] = None,
) -> List[Dict[str, Any]]:
    """Generate terrain-following boustrophedon (lawnmower) sweep legs inside polygon_xz."""
    if len(polygon_xz) < 3:
        return []

    swath_info = compute_swath(altitude_agl_m, sensor_mode, sidelap_pct)
    spacing = swath_info["lane_spacing_m"]
    swath_w = swath_info["swath_width_m"]
    alt_agl = float(altitude_agl_m)

    pts = np.array([[float(p[0]), float(p[1])] for p in polygon_xz], dtype=float)
    centroid = np.mean(pts, axis=0)

    theta = math.radians(float(sweep_angle_deg))
    cos_t, sin_t = math.cos(-theta), math.sin(-theta)
    rot_mat = np.array([[cos_t, -sin_t], [sin_t, cos_t]], dtype=float)
    inv_mat = np.array([[cos_t, sin_t], [-sin_t, cos_t]], dtype=float)

    rot_pts = (pts - centroid) @ rot_mat.T
    min_v = float(np.min(rot_pts[:, 1]))
    max_v = float(np.max(rot_pts[:, 1]))
    span_v = max(1.0, max_v - min_v)

    num_legs = max(1, int(math.ceil(span_v / spacing)))
    step_v = span_v / num_legs
    legs: List[Dict[str, Any]] = []

    for leg_idx in range(num_legs):
        v = min_v + (leg_idx + 0.5) * step_v
        # Find polygon edge intersections with horizontal scanline v in rotated frame
        u_hits: List[float] = []
        n = len(rot_pts)
        for i in range(n):
            u1, v1 = float(rot_pts[i, 0]), float(rot_pts[i, 1])
            u2, v2 = float(rot_pts[(i + 1) % n, 0]), float(rot_pts[(i + 1) % n, 1])
            if (v1 <= v <= v2) or (v2 <= v <= v1):
                if abs(v2 - v1) > 1e-9:
                    t = (v - v1) / (v2 - v1)
                    if -1e-6 <= t <= 1.0 + 1e-6:
                        u_hits.append(u1 + t * (u2 - u1))
        if len(u_hits) < 2:
            continue
        u_hits.sort()
        u_start, u_end = u_hits[0], u_hits[-1]
        if u_end - u_start < 1.0:
            continue

        # Alternate sweep direction (boustrophedon)
        if leg_idx % 2 == 1:
            u_start, u_end = u_end, u_start

        seg_len = abs(u_end - u_start)
        num_samples = max(2, int(math.ceil(seg_len / 22.0)) + 1)
        us = np.linspace(u_start, u_end, num_samples)

        leg_points: List[List[float]] = []
        for u in us:
            world_xz = centroid + (np.array([u, v], dtype=float) @ inv_mat.T)
            wx, wz = float(world_xz[0]), float(world_xz[1])
            ground_y = terrain.sample_terrain(wx, wz) if terrain is not None else 18.0
            # Ensure y >= terrain.sample_terrain(wx, wz) + alt_agl
            wy = float(ground_y + alt_agl + 1e-4)
            leg_points.append([round(wx, 4), round(wy, 4), round(wz, 4)])

        legs.append(
            {
                "leg_index": leg_idx,
                "direction": "EAST" if leg_idx % 2 == 0 else "WEST",
                "swath_width_m": swath_w,
                "start": leg_points[0],
                "end": leg_points[-1],
                "points": leg_points,
                "length_m": round(seg_len, 2),
            }
        )

    return legs


def partition_legs(
    legs: List[Dict[str, Any]],
    uav_ids: Tuple[str, ...] = ("UAV-1", "UAV-2", "UAV-3"),
    batteries: Optional[Dict[str, float]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Partition lawnmower sweep legs across available UAVs weighted by battery capacity."""
    if not uav_ids:
        return {}
    bat = batteries or {uid: 100.0 for uid in uav_ids}
    weights = {uid: max(10.0, float(bat.get(uid, 100.0))) for uid in uav_ids}
    total_w = sum(weights.values())

    n_legs = len(legs)
    partitions: Dict[str, Dict[str, Any]] = {
        uid: {
            "uav_id": uid,
            "leg_indices": [],
            "legs": [],
            "waypoints": [],
            "total_distance_m": 0.0,
            "role_status": "SAR_SWEEPER",
        }
        for uid in uav_ids
    }
    if n_legs == 0:
        return partitions

    # Contiguous band slicing proportional to battery weights
    idx = 0
    for i, uid in enumerate(uav_ids):
        if i == len(uav_ids) - 1:
            assigned = legs[idx:]
        else:
            share = max(1, int(round(n_legs * (weights[uid] / total_w))))
            remaining_uavs = len(uav_ids) - i - 1
            max_allowed = max(0, n_legs - idx - remaining_uavs)
            count = min(share, max_allowed)
            assigned = legs[idx : idx + count]
            idx += count

        wps: List[List[float]] = []
        dist_sum = 0.0
        for leg in assigned:
            partitions[uid]["leg_indices"].append(leg["leg_index"])
            partitions[uid]["legs"].append(leg)
            wps.extend(leg["points"])
            dist_sum += float(leg.get("length_m", 0.0))
        partitions[uid]["waypoints"] = wps
        partitions[uid]["total_distance_m"] = round(dist_sum, 2)

    return partitions


def reassign_waypoints(
    partitions: Dict[str, Dict[str, Any]],
    relay_uav_id: str = "UAV-2",
    remaining_waypoints: Optional[List[List[float]]] = None,
    active_uavs: Tuple[str, ...] = ("UAV-1", "UAV-3"),
) -> Dict[str, Any]:
    """Reassign unvisited SAR waypoints from relay_uav_id to active_uavs when relay failover triggers."""
    relay_part = partitions.get(relay_uav_id, {})
    unvisited = (
        list(remaining_waypoints)
        if remaining_waypoints is not None
        else list(relay_part.get("waypoints", []))
    )

    reassigned_counts: Dict[str, int] = {uid: 0 for uid in active_uavs}
    reassigned_wps: Dict[str, List[List[float]]] = {uid: [] for uid in active_uavs}

    if unvisited and active_uavs:
        mid = len(unvisited) // len(active_uavs)
        for i, uid in enumerate(active_uavs):
            if i == len(active_uavs) - 1:
                chunk = unvisited[i * mid :]
            else:
                chunk = unvisited[i * mid : (i + 1) * mid]
            reassigned_wps[uid] = chunk
            reassigned_counts[uid] = len(chunk)
            if uid in partitions:
                partitions[uid]["waypoints"] = list(partitions[uid].get("waypoints", [])) + chunk

    if relay_uav_id in partitions:
        partitions[relay_uav_id]["waypoints"] = []
        partitions[relay_uav_id]["role_status"] = "AMESH_RELAY (RETASKED)"

    return {
        "relay_uav_id": relay_uav_id,
        "unvisited_count": len(unvisited),
        "reassigned_counts": reassigned_counts,
        "reassigned_waypoints": reassigned_wps,
        "partitions": partitions,
    }


def export_kml(
    mission_data: Dict[str, Any],
    sar_detections: Optional[List[Dict[str, Any]]] = None,
    pinned_targets: Optional[List[Dict[str, Any]]] = None,
    origin_lat: Optional[float] = None,
    origin_lon: Optional[float] = None,
    origin_alt_asl: Optional[float] = None,
) -> str:
    """Export OGC KML 2.2 mission file compatible with Autel Explorer V3 using active WGS84 datum."""
    active_origin = get_active_origin()
    o_lat = float(active_origin["lat"] if origin_lat is None else origin_lat)
    o_lon = float(active_origin["lon"] if origin_lon is None else origin_lon)
    o_alt = float(active_origin["alt_asl"] if origin_alt_asl is None else origin_alt_asl)

    mission_id = mission_data.get("mission_id", "SAR-001")
    polygon_xz = mission_data.get("polygon_xz") or VALLEY_POLYGON
    altitude_agl = float(mission_data.get("altitude_agl_m", 60.0))
    sensor_mode = mission_data.get("sensor_mode", "THERMAL")
    sidelap_pct = float(mission_data.get("sidelap_pct", 70.0))
    partitions = mission_data.get("partitions", {})
    detections = sar_detections if sar_detections is not None else mission_data.get("sar_detections", [])
    pins = pinned_targets if pinned_targets is not None else mission_data.get("pinned_targets", [])

    # Convert polygon corners to WGS84 (lon,lat,alt_asl)
    poly_coord_tuples: List[str] = []
    poly_ring = list(polygon_xz) + ([polygon_xz[0]] if polygon_xz else [])
    for pt in poly_ring:
        lat, lon = local_to_wgs84(float(pt[0]), float(pt[1]), o_lat, o_lon)
        alt_asl = o_alt + altitude_agl
        poly_coord_tuples.append(f"{lon:.7f},{lat:.7f},{alt_asl:.2f}")
    poly_coords_str = " ".join(poly_coord_tuples)

    # Build UAV route Placemarks
    uav_styles = {
        "UAV-1": ("ff81b910", "UAV-1 Scout Sweep Route"),
        "UAV-2": ("ffd4b606", "UAV-2 Relay Sweep Route"),
        "UAV-3": ("fffa8bfa", "UAV-3 Overwatch Sweep Route"),
    }
    route_placemarks: List[str] = []
    for uid, part in partitions.items():
        wps = part.get("waypoints", [])
        if not wps:
            continue
        color_hex, label = uav_styles.get(uid, ("ff00ffff", f"{uid} Sweep Route"))
        coord_strs: List[str] = []
        wp_placemarks: List[str] = []
        for idx, wp in enumerate(wps):
            wx, wy, wz = float(wp[0]), float(wp[1]), float(wp[2])
            lat, lon = local_to_wgs84(wx, wz, o_lat, o_lon)
            alt_asl = o_alt + wy
            coord_strs.append(f"{lon:.7f},{lat:.7f},{alt_asl:.2f}")
            wp_placemarks.append(
                f"""      <Placemark>
        <name>{uid}-WP{idx + 1:02d}</name>
        <ExtendedData>
          <Data name="uav_id"><value>{uid}</value></Data>
          <Data name="wp_index"><value>{idx}</value></Data>
          <Data name="altitude_agl_m"><value>{altitude_agl:.1f}</value></Data>
          <Data name="gimbal_pitch_deg"><value>-90.0</value></Data>
        </ExtendedData>
        <Point>
          <altitudeMode>absolute</altitudeMode>
          <coordinates>{lon:.7f},{lat:.7f},{alt_asl:.2f}</coordinates>
        </Point>
      </Placemark>"""
            )

        route_placemarks.append(
            f"""      <Placemark>
        <name>{label}</name>
        <Style>
          <LineStyle>
            <color>{color_hex}</color>
            <width>3</width>
          </LineStyle>
        </Style>
        <LineString>
          <tessellate>1</tessellate>
          <altitudeMode>absolute</altitudeMode>
          <coordinates>{' '.join(coord_strs)}</coordinates>
        </LineString>
      </Placemark>
{chr(10).join(wp_placemarks)}"""
        )

    # Build SAR Thermal Detections folder
    detection_placemarks: List[str] = []
    for det in detections:
        pos = det.get("position", [0.0, 20.0, 0.0])
        lat, lon = local_to_wgs84(float(pos[0]), float(pos[2]), o_lat, o_lon)
        alt_asl = o_alt + float(pos[1])
        det_id = det.get("id", "SAR-01")
        label = det.get("label", "Thermal Contact")
        temp_c = det.get("temp_c", 60.0)
        detection_placemarks.append(
            f"""      <Placemark>
        <name>{det_id} - {label} ({temp_c:.1f}C)</name>
        <description>Captured by {det.get('detected_by', 'UAV-1')} at T+{det.get('sim_time', 0.0):.1f}s</description>
        <Point>
          <altitudeMode>absolute</altitudeMode>
          <coordinates>{lon:.7f},{lat:.7f},{alt_asl:.2f}</coordinates>
        </Point>
      </Placemark>"""
        )

    # Build LRF Pinned Targets folder
    pin_placemarks: List[str] = []
    for pin in pins:
        pos = pin.get("position", [0.0, 20.0, 0.0])
        lat, lon = local_to_wgs84(float(pos[0]), float(pos[2]), o_lat, o_lon)
        alt_asl = o_alt + float(pos[1])
        pin_id = pin.get("id", "PIN-01")
        label = pin.get("label", "Pinned LRF Target")
        pin_placemarks.append(
            f"""      <Placemark>
        <name>{pin_id} - {label}</name>
        <Point>
          <altitudeMode>absolute</altitudeMode>
          <coordinates>{lon:.7f},{lat:.7f},{alt_asl:.2f}</coordinates>
        </Point>
      </Placemark>"""
        )

    kml_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Autel EVO Max 4T Mission - {mission_id}</name>
    <description>Cooperative A-Mesh SAR Grid Mission ({sensor_mode} @ {altitude_agl:.0f}m AGL, {sidelap_pct:.0f}% sidelap)</description>
    <ExtendedData>
      <Data name="mission_id"><value>{mission_id}</value></Data>
      <Data name="amesh_origin_lat"><value>{o_lat:.7f}</value></Data>
      <Data name="amesh_origin_lon"><value>{o_lon:.7f}</value></Data>
      <Data name="amesh_origin_alt_asl"><value>{o_alt:.2f}</value></Data>
      <Data name="altitude_agl_m"><value>{altitude_agl:.1f}</value></Data>
      <Data name="sensor_mode"><value>{sensor_mode}</value></Data>
      <Data name="sidelap_pct"><value>{sidelap_pct:.1f}</value></Data>
    </ExtendedData>
    <Folder>
      <name>Boundary_Polygon</name>
      <Placemark>
        <name>SAR Search Area Polygon</name>
        <Polygon>
          <extrude>1</extrude>
          <altitudeMode>relativeToGround</altitudeMode>
          <outerBoundaryIs>
            <LinearRing>
              <coordinates>{poly_coords_str}</coordinates>
            </LinearRing>
          </outerBoundaryIs>
        </Polygon>
      </Placemark>
    </Folder>
    <Folder>
      <name>Waypoint_Routes</name>
{chr(10).join(route_placemarks)}
    </Folder>
    <Folder>
      <name>SAR Thermal Detections</name>
{chr(10).join(detection_placemarks)}
    </Folder>
    <Folder>
      <name>LRF Pinned Targets</name>
{chr(10).join(pin_placemarks)}
    </Folder>
  </Document>
</kml>
"""
    return kml_xml


def export_autel_wpml_kmz(
    mission_data: Dict[str, Any],
    sar_detections: Optional[List[Dict[str, Any]]] = None,
    pinned_targets: Optional[List[Dict[str, Any]]] = None,
    origin_lat: Optional[float] = None,
    origin_lon: Optional[float] = None,
    origin_alt_asl: Optional[float] = None,
) -> bytes:
    """Export an Autel Smart Controller V3 / WPML 1.0 (.kmz) archive containing wpmz/template.kml and wpmz/waylines.wpml."""
    active_origin = get_active_origin()
    o_lat = float(active_origin["lat"] if origin_lat is None else origin_lat)
    o_lon = float(active_origin["lon"] if origin_lon is None else origin_lon)
    o_alt = float(active_origin["alt_asl"] if origin_alt_asl is None else origin_alt_asl)

    template_kml = export_kml(
        mission_data,
        sar_detections=sar_detections,
        pinned_targets=pinned_targets,
        origin_lat=o_lat,
        origin_lon=o_lon,
        origin_alt_asl=o_alt,
    )

    altitude_agl = float(mission_data.get("altitude_agl_m", 60.0))
    partitions = mission_data.get("partitions", {})
    placemarks: List[str] = []
    wp_idx = 0
    for uid in ("UAV-1", "UAV-2", "UAV-3"):
        part = partitions.get(uid, {})
        for wp in part.get("waypoints", []):
            wx, wy, wz = float(wp[0]), float(wp[1]), float(wp[2])
            lat, lon = local_to_wgs84(wx, wz, o_lat, o_lon)
            ellipsoid_h = o_alt + wy
            placemarks.append(
                f"""      <Placemark>
        <Point>
          <coordinates>{lon:.7f},{lat:.7f}</coordinates>
        </Point>
        <wpml:index>{wp_idx}</wpml:index>
        <wpml:ellipsoidHeight>{ellipsoid_h:.2f}</wpml:ellipsoidHeight>
        <wpml:height>{altitude_agl:.2f}</wpml:height>
        <wpml:waypointSpeed>18.5</wpml:waypointSpeed>
        <wpml:uavId>{uid}</wpml:uavId>
      </Placemark>"""
            )
            wp_idx += 1

    waylines_wpml = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2" xmlns:wpml="http://www.autelrobotics.com/wpml/1.0.2">
  <Document>
    <wpml:missionConfig>
      <wpml:flyToWaylineMode>safely</wpml:flyToWaylineMode>
      <wpml:finishAction>goHome</wpml:finishAction>
      <wpml:originLat>{o_lat:.7f}</wpml:originLat>
      <wpml:originLon>{o_lon:.7f}</wpml:originLon>
      <wpml:originAltAsl>{o_alt:.2f}</wpml:originAltAsl>
    </wpml:missionConfig>
    <Folder>
      <wpml:templateId>0</wpml:templateId>
      <wpml:waylineId>0</wpml:waylineId>
{chr(10).join(placemarks)}
    </Folder>
  </Document>
</kml>
"""

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("wpmz/template.kml", template_kml.encode("utf-8"))
        zf.writestr("wpmz/waylines.wpml", waylines_wpml.encode("utf-8"))
        zf.writestr("doc.kml", template_kml.encode("utf-8"))
    return buf.getvalue()


def _parse_coord_block(coord_text: str) -> List[Tuple[float, float, Optional[float]]]:
    """Parse KML <coordinates> string 'lon,lat[,alt] ...' into list of (lon, lat, alt)."""
    out: List[Tuple[float, float, Optional[float]]] = []
    for token in (coord_text or "").strip().split():
        parts = [p.strip() for p in token.split(",") if p.strip()]
        if len(parts) >= 2:
            try:
                lon = float(parts[0])
                lat = float(parts[1])
                alt = float(parts[2]) if len(parts) >= 3 else None
                out.append((lon, lat, alt))
            except ValueError:
                continue
    return out


def parse_kml_kmz(
    raw_bytes: bytes,
    filename: str = "mission.kml",
    auto_center_origin: bool = True,
) -> Dict[str, Any]:
    """Parse a raw .kml or zipped .kmz (including Autel WPML .kmz) into local tactical coordinates.

    If the imported file contains real-world WGS84 coordinates (and is not tagged with an internal
    round-trip origin), automatically centers the simulator's geodetic_origin on the imported
    mission's centroid so it renders cleanly inside the 3D viewport.
    """
    is_kmz = False
    is_wpml = False
    xml_bytes = raw_bytes

    if raw_bytes[:2] == b"PK" or filename.lower().endswith(".kmz"):
        is_kmz = True
        with zipfile.ZipFile(io.BytesIO(raw_bytes), mode="r") as zf:
            names = zf.namelist()
            if "wpmz/template.kml" in names:
                is_wpml = True
                xml_bytes = zf.read("wpmz/template.kml")
            elif "wpmz/waylines.wpml" in names:
                is_wpml = True
                xml_bytes = zf.read("wpmz/waylines.wpml")
            else:
                kml_names = [n for n in names if n.lower().endswith((".kml", ".wpml"))]
                if not kml_names:
                    raise ValueError("No .kml or .wpml file found inside .kmz archive")
                xml_bytes = zf.read(kml_names[0])

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ValueError(f"Invalid KML XML: {exc}") from exc

    # Check if this KML has embedded A-Mesh origin metadata
    embedded_origin: Dict[str, float] = {}
    for elem in root.iter():
        tag = elem.tag.split("}")[-1]
        if tag == "Data":
            name_attr = elem.attrib.get("name", "")
            val_elem = next((c for c in elem if c.tag.split("}")[-1] == "value"), None)
            if val_elem is not None and val_elem.text:
                try:
                    if name_attr == "amesh_origin_lat":
                        embedded_origin["lat"] = float(val_elem.text)
                    elif name_attr == "amesh_origin_lon":
                        embedded_origin["lon"] = float(val_elem.text)
                    elif name_attr == "amesh_origin_alt_asl":
                        embedded_origin["alt_asl"] = float(val_elem.text)
                except ValueError:
                    pass

    polygon_wgs84: List[Tuple[float, float, Optional[float]]] = []
    linestring_wgs84: List[Tuple[float, float, Optional[float]]] = []
    point_wgs84: List[Tuple[float, float, Optional[float]]] = []

    for elem in root.iter():
        tag = elem.tag.split("}")[-1]
        if tag == "Polygon" and not polygon_wgs84:
            for sub in elem.iter():
                if sub.tag.split("}")[-1] == "coordinates" and sub.text:
                    coords = _parse_coord_block(sub.text)
                    if len(coords) >= 3:
                        # Remove closing duplicate vertex if present
                        if len(coords) >= 4 and abs(coords[0][0] - coords[-1][0]) < 1e-8 and abs(coords[0][1] - coords[-1][1]) < 1e-8:
                            coords = coords[:-1]
                        polygon_wgs84 = coords
                        break
        elif tag == "LineString":
            for sub in elem.iter():
                if sub.tag.split("}")[-1] == "coordinates" and sub.text:
                    linestring_wgs84.extend(_parse_coord_block(sub.text))
        elif tag == "Point":
            for sub in elem.iter():
                if sub.tag.split("}")[-1] == "coordinates" and sub.text:
                    point_wgs84.extend(_parse_coord_block(sub.text))

    primary_coords = polygon_wgs84 or linestring_wgs84 or point_wgs84
    if not primary_coords:
        raise ValueError("No valid <Polygon>, <LineString>, or <Point> <coordinates> found in KML/KMZ")

    centroid_lon = sum(c[0] for c in primary_coords) / len(primary_coords)
    centroid_lat = sum(c[1] for c in primary_coords) / len(primary_coords)
    alts = [c[2] for c in primary_coords if c[2] is not None]
    centroid_alt = sum(alts) / len(alts) if alts else None

    current_origin = get_active_origin()
    recentered = False

    if "lat" in embedded_origin and "lon" in embedded_origin:
        # Round-trip import of an A-Mesh Sim 4T exported file: restore its exact site origin
        o_lat = embedded_origin["lat"]
        o_lon = embedded_origin["lon"]
        o_alt = embedded_origin.get("alt_asl", current_origin["alt_asl"])
        if auto_center_origin:
            set_active_origin(o_lat, o_lon, o_alt)
    else:
        # External real-world KML/KMZ: check distance from current origin and auto-center geodetic_origin
        cx_local, cz_local = wgs84_to_local(centroid_lat, centroid_lon, current_origin["lat"], current_origin["lon"])
        dist_from_origin = math.hypot(cx_local, cz_local)
        if auto_center_origin:
            # Automatically center geodetic_origin on the imported mission's WGS84 centroid
            set_active_origin(centroid_lat, centroid_lon, current_origin["alt_asl"])
            o_lat, o_lon, o_alt = centroid_lat, centroid_lon, current_origin["alt_asl"]
            if dist_from_origin > 1.0:
                recentered = True
        else:
            o_lat, o_lon, o_alt = current_origin["lat"], current_origin["lon"], current_origin["alt_asl"]

    # Convert primary coordinates to local (x, z)
    def _to_bounded_local(coords_list: List[Tuple[float, float, Optional[float]]]) -> List[List[float]]:
        raw_xz = [list(wgs84_to_local(lat, lon, o_lat, o_lon)) for (lon, lat, _) in coords_list]
        max_abs = max((max(abs(p[0]), abs(p[1])) for p in raw_xz), default=0.0)
        if max_abs > 420.0:
            # Scale large external polygons cleanly into the 3D tactical arena
            cx = sum(p[0] for p in raw_xz) / len(raw_xz)
            cz = sum(p[1] for p in raw_xz) / len(raw_xz)
            max_span = max(max(abs(p[0] - cx), abs(p[1] - cz)) for p in raw_xz)
            scale = 180.0 / max(max_span, 1.0)
            raw_xz = [[round((p[0] - cx) * scale, 2), round((p[1] - cz) * scale, 2)] for p in raw_xz]
        else:
            raw_xz = [[round(p[0], 2), round(p[1], 2)] for p in raw_xz]
        return raw_xz

    geometry_type = "POLYGON" if polygon_wgs84 else ("WPML_KMZ" if is_wpml else "LINESTRING")
    if polygon_wgs84:
        local_poly = _to_bounded_local(polygon_wgs84)
        local_route = _to_bounded_local(linestring_wgs84) if linestring_wgs84 else []
    else:
        local_route = _to_bounded_local(linestring_wgs84 or point_wgs84)
        xs = [p[0] for p in local_route]
        zs = [p[1] for p in local_route]
        min_x, max_x = min(xs) - 20.0, max(xs) + 20.0
        min_z, max_z = min(zs) - 20.0, max(zs) + 20.0
        local_poly = [[min_x, min_z], [max_x, min_z], [max_x, max_z], [min_x, max_z]]

    return {
        "filename": filename,
        "is_kmz": is_kmz,
        "is_wpml": is_wpml,
        "geometry_type": geometry_type,
        "polygon_xz": local_poly,
        "route_xz": local_route,
        "recentered": recentered,
        "centroid_wgs84": {
            "lat": round(centroid_lat, 7),
            "lon": round(centroid_lon, 7),
            "alt_asl": round(centroid_alt, 2) if centroid_alt is not None else round(o_alt, 2),
        },
        "geodetic_origin": get_active_origin(),
    }


class MissionPlanner:
    """Stateful manager for Cooperative Multi-UAV SAR Polygon Grid Planning and KML/WPML I/O."""

    def __init__(self, terrain: TacticalTerrain) -> None:
        self.terrain = terrain
        self.mission_id: str = "SAR-001"
        self.polygon_xz: List[List[float]] = [list(p) for p in VALLEY_POLYGON]
        self.altitude_agl_m: float = 60.0
        self.sensor_mode: str = "THERMAL"
        self.sidelap_pct: float = 70.0
        self.sweep_angle_deg: float = 0.0
        self.legs: List[Dict[str, Any]] = []
        self.partitions: Dict[str, Dict[str, Any]] = {}
        self.executing: bool = False
        self.relay_retasked: bool = False
        self.relay_retask_info: Optional[Dict[str, Any]] = None
        self.last_imported_filename: Optional[str] = None
        self._seq: int = 1
        self.generate_grid(
            polygon_xz=self.polygon_xz,
            altitude_agl_m=self.altitude_agl_m,
            sensor_mode=self.sensor_mode,
            sidelap_pct=self.sidelap_pct,
            sweep_angle_deg=self.sweep_angle_deg,
        )

    def set_geodetic_origin(
        self,
        lat: float,
        lon: float,
        alt_asl: Optional[float] = None,
    ) -> Dict[str, float]:
        """Update the active WGS84 datum on terrain and mission planner."""
        return self.terrain.set_origin(lat, lon, alt_asl)

    def generate_grid(
        self,
        polygon_xz: List[List[float]],
        altitude_agl_m: float = 60.0,
        sensor_mode: str = "THERMAL",
        sidelap_pct: float = 70.0,
        sweep_angle_deg: float = 0.0,
        batteries: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        if len(polygon_xz) < 3:
            raise ValueError("Polygon must have at least 3 vertices")
        self._seq += 1
        self.mission_id = f"SAR-{int(time.time() * 1000) % 900000 + 100000}"
        self.polygon_xz = [[round(float(p[0]), 2), round(float(p[1]), 2)] for p in polygon_xz]
        self.altitude_agl_m = float(altitude_agl_m)
        self.sensor_mode = str(sensor_mode).upper()
        self.sidelap_pct = float(sidelap_pct)
        self.sweep_angle_deg = float(sweep_angle_deg)
        self.relay_retasked = False
        self.relay_retask_info = None

        self.legs = generate_lawnmower(
            self.polygon_xz,
            self.altitude_agl_m,
            self.sensor_mode,
            self.sidelap_pct,
            self.sweep_angle_deg,
            self.terrain,
        )
        self.partitions = partition_legs(self.legs, ("UAV-1", "UAV-2", "UAV-3"), batteries=batteries)
        return self.get_state()

    def handle_relay_failover(
        self,
        remaining_uav2_waypoints: Optional[List[List[float]]] = None,
    ) -> Dict[str, Any]:
        """Re-task UAV-2's remaining SAR sweep waypoints to UAV-1 and UAV-3."""
        info = reassign_waypoints(
            self.partitions,
            relay_uav_id="UAV-2",
            remaining_waypoints=remaining_uav2_waypoints,
            active_uavs=("UAV-1", "UAV-3"),
        )
        self.relay_retasked = True
        self.relay_retask_info = {
            "relay_uav_id": info["relay_uav_id"],
            "unvisited_count": info["unvisited_count"],
            "reassigned_counts": info["reassigned_counts"],
            "reassigned_waypoints": info["reassigned_waypoints"],
        }
        return info

    def clear(self) -> Dict[str, Any]:
        self.legs = []
        self.partitions = {}
        self.executing = False
        self.relay_retasked = False
        self.relay_retask_info = None
        return self.get_state()

    def get_state(self) -> Dict[str, Any]:
        swath = compute_swath(self.altitude_agl_m, self.sensor_mode, self.sidelap_pct)
        area_m2 = polygon_area_m2(self.polygon_xz)
        total_wps = sum(len(p.get("waypoints", [])) for p in self.partitions.values())
        total_dist_m = sum(float(p.get("total_distance_m", 0.0)) for p in self.partitions.values())
        est_time_s = round(total_dist_m / (18.5 * max(1, len(self.partitions))) + len(self.legs) * 3.2, 1)

        origin = get_active_origin()
        cx, cz = polygon_centroid_xz(self.polygon_xz)
        c_lat, c_lon = local_to_wgs84(cx, cz, origin["lat"], origin["lon"])
        gcs_lat, gcs_lon = local_to_wgs84(
            float(self.terrain.gcs_position[0]),
            float(self.terrain.gcs_position[2]),
            origin["lat"],
            origin["lon"],
        )

        polygon_wgs84 = []
        for p in self.polygon_xz:
            plat, plon = local_to_wgs84(float(p[0]), float(p[1]), origin["lat"], origin["lon"])
            polygon_wgs84.append({"lat": round(plat, 7), "lon": round(plon, 7)})

        return {
            "mission_id": self.mission_id,
            "executing": self.executing,
            "polygon_xz": self.polygon_xz,
            "polygon_wgs84": polygon_wgs84,
            "polygon_center_wgs84": {
                "lat": round(c_lat, 7),
                "lon": round(c_lon, 7),
                "alt_asl": round(origin["alt_asl"] + self.terrain.get_elevation(cx, cz) + self.altitude_agl_m, 2),
            },
            "gcs_wgs84": {
                "lat": round(gcs_lat, 7),
                "lon": round(gcs_lon, 7),
                "alt_asl": round(origin["alt_asl"] + float(self.terrain.gcs_position[1]), 2),
            },
            "geodetic_origin": origin,
            "altitude_agl_m": self.altitude_agl_m,
            "sensor_mode": self.sensor_mode,
            "sidelap_pct": self.sidelap_pct,
            "sweep_angle_deg": self.sweep_angle_deg,
            "area_m2": area_m2,
            "swath_width_m": swath["swath_width_m"],
            "lane_spacing_m": swath["lane_spacing_m"],
            "total_legs": len(self.legs),
            "total_waypoints": total_wps,
            "total_distance_m": round(total_dist_m, 1),
            "estimated_time_s": est_time_s,
            "legs": self.legs,
            "partitions": self.partitions,
            "relay_retasked": self.relay_retasked,
            "relay_retask_info": self.relay_retask_info,
            "last_imported_filename": self.last_imported_filename,
        }
