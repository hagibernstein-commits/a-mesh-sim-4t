"""Unit tests for Phase 5 Cooperative SAR Grid Planner, KML/WPML I/O & Configurable WGS84 Geodetic Origin."""

from __future__ import annotations
import io
import math
import xml.etree.ElementTree as ET
import zipfile
from fastapi.testclient import TestClient

from app.terrain import (
    TacticalTerrain,
    METERS_PER_DEG_LAT,
    DEFAULT_ORIGIN_LAT,
    DEFAULT_ORIGIN_LON,
    DEFAULT_ORIGIN_ALT_ASL,
    local_to_wgs84,
    wgs84_to_local,
    set_active_origin,
)
from app.mission_planner import (
    VALLEY_POLYGON,
    MissionPlanner,
    compute_swath,
    point_in_polygon,
    generate_lawnmower,
    partition_legs,
    reassign_waypoints,
    export_kml,
    export_autel_wpml_kmz,
    parse_kml_kmz,
)
from app.simulator import SwarmSimulator
from app.main import app, simulator

_TERRAIN = TacticalTerrain()


def test_swath_and_lane_spacing_thermal_vs_wide():
    t_swath = compute_swath(60.0, "THERMAL", 70.0)
    w_swath = compute_swath(60.0, "WIDE", 70.0)
    expected_t_w = 2.0 * 60.0 * math.tan(math.radians(42.0 / 2.0))
    assert abs(t_swath["swath_width_m"] - expected_t_w) < 0.05
    assert abs(t_swath["lane_spacing_m"] - expected_t_w * 0.30) < 0.05
    assert w_swath["swath_width_m"] > t_swath["swath_width_m"]


def test_lawnmower_terrain_following_and_coverage():
    alt = 60.0
    legs = generate_lawnmower(VALLEY_POLYGON, alt, "THERMAL", 70.0, 0.0, _TERRAIN)
    spacing = compute_swath(alt, "THERMAL", 70.0)["lane_spacing_m"]

    assert len(legs) == math.ceil(140.0 / spacing)
    for a, b in zip(legs[:-1], legs[1:]):
        assert (a["end"][0] - a["start"][0]) * (b["end"][0] - b["start"][0]) < 0
    for leg in legs:
        for (x, y, z) in leg["points"]:
            assert 60.0 - 1e-3 <= x <= 220.0 + 1e-3 and -70.0 - 1e-3 <= z <= 70.0 + 1e-3
            assert point_in_polygon(min(max(x, 60.01), 219.99), z, VALLEY_POLYGON)
            assert y >= _TERRAIN.sample_terrain(x, z) + alt - 1e-6


def test_balanced_three_uav_partition():
    legs = generate_lawnmower(VALLEY_POLYGON, 60.0, "THERMAL", 70.0, 0.0, _TERRAIN)
    parts = partition_legs(legs, ("UAV-1", "UAV-2", "UAV-3"))
    assert set(parts.keys()) == {"UAV-1", "UAV-2", "UAV-3"}
    total_assigned = sum(len(p["legs"]) for p in parts.values())
    assert total_assigned == len(legs)
    for uid in ("UAV-1", "UAV-2", "UAV-3"):
        assert len(parts[uid]["waypoints"]) >= 4


def test_relay_reassignment_preserves_coverage():
    legs = generate_lawnmower(VALLEY_POLYGON, 60.0, "THERMAL", 70.0, 0.0, _TERRAIN)
    parts = partition_legs(legs, ("UAV-1", "UAV-2", "UAV-3"))
    total_before = sum(len(p["waypoints"]) for p in parts.values())
    u2_count = len(parts["UAV-2"]["waypoints"])

    info = reassign_waypoints(parts, relay_uav_id="UAV-2")
    assert info["unvisited_count"] == u2_count
    assert len(parts["UAV-2"]["waypoints"]) == 0
    total_after = sum(len(p["waypoints"]) for p in parts.values())
    assert total_after == total_before


def test_mission_planner_relay_retask_state():
    planner = MissionPlanner(_TERRAIN)
    planner.generate_grid(VALLEY_POLYGON, 60.0, "THERMAL", 70.0, 0.0)
    retask = planner.handle_relay_failover()
    assert planner.relay_retasked is True
    assert retask["unvisited_count"] > 0


def test_wgs84_meridian_and_parallel_scaling_and_round_trip():
    set_active_origin(31.6915, 34.9785, 320.0)
    x, z = 140.0, -55.0
    lat, lon = local_to_wgs84(x, z)

    expected_dlat = -z / METERS_PER_DEG_LAT
    expected_dlon = x / (METERS_PER_DEG_LAT * math.cos(math.radians(31.6915)))
    assert abs((lat - 31.6915) - expected_dlat) < 1e-9
    assert abs((lon - 34.9785) - expected_dlon) < 1e-9

    rx, rz = wgs84_to_local(lat, lon)
    assert abs(rx - x) < 1e-4
    assert abs(rz - z) < 1e-4


def test_parse_raw_kml_polygon():
    set_active_origin(DEFAULT_ORIGIN_LAT, DEFAULT_ORIGIN_LON, DEFAULT_ORIGIN_ALT_ASL)
    planner = MissionPlanner(_TERRAIN)
    kml_text = export_kml(planner.get_state())
    parsed = parse_kml_kmz(kml_text.encode("utf-8"), filename="valley.kml")
    assert parsed["geometry_type"] == "POLYGON"
    assert len(parsed["polygon_xz"]) == 4


def test_parse_zipped_kmz_and_linestring():
    set_active_origin(DEFAULT_ORIGIN_LAT, DEFAULT_ORIGIN_LON, DEFAULT_ORIGIN_ALT_ASL)
    planner = MissionPlanner(_TERRAIN)
    kmz_bytes = export_autel_wpml_kmz(planner.get_state())
    assert kmz_bytes[:2] == b"PK"
    parsed = parse_kml_kmz(kmz_bytes, filename="mission_wpml.kmz")
    assert parsed["is_kmz"] is True
    assert parsed["is_wpml"] is True
    assert len(parsed["polygon_xz"]) >= 3


def test_parse_external_real_world_kml_auto_centers_datum():
    """Verify that importing an external real-world .kml automatically centers geodetic_origin on its centroid."""
    set_active_origin(DEFAULT_ORIGIN_LAT, DEFAULT_ORIGIN_LON, DEFAULT_ORIGIN_ALT_ASL)

    # Create an external real-world KML polygon in Southern California / Mojave (35.1200°N, -116.5400°W)
    ext_lats = [35.1195, 35.1195, 35.1205, 35.1205]
    ext_lons = [-116.5408, -116.5392, -116.5392, -116.5408]
    expected_centroid_lat = sum(ext_lats) / len(ext_lats)
    expected_centroid_lon = sum(ext_lons) / len(ext_lons)

    coord_ring = " ".join(
        f"{lon:.7f},{lat:.7f},410.0"
        for lon, lat in list(zip(ext_lons, ext_lats)) + [(ext_lons[0], ext_lats[0])]
    )
    external_kml = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>External Real-World SAR Polygon</name>
    <Placemark>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>{coord_ring}</coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>"""

    parsed = parse_kml_kmz(external_kml.encode("utf-8"), filename="external_site.kml")
    assert parsed["recentered"] is True
    assert abs(parsed["geodetic_origin"]["lat"] - expected_centroid_lat) < 1e-6
    assert abs(parsed["geodetic_origin"]["lon"] - expected_centroid_lon) < 1e-6

    # All converted local polygon vertices should be centered near (0, 0) inside the 3D viewport
    xs = [p[0] for p in parsed["polygon_xz"]]
    zs = [p[1] for p in parsed["polygon_xz"]]
    assert abs(sum(xs) / len(xs)) < 1.0
    assert abs(sum(zs) / len(zs)) < 1.0
    assert all(-420.0 <= x <= 420.0 and -420.0 <= z <= 420.0 for x, z in parsed["polygon_xz"])


def test_post_mission_origin_shifts_exported_kml_and_wpml_coordinates():
    """Verify POST /api/mission/origin shifts exported KML/WPML <coordinates> and validates lat/lon bounds."""
    client = TestClient(app)
    simulator.reset()

    # 1. Validation check: out-of-range latitude/longitude must be rejected
    bad_lat = client.post("/api/mission/origin", json={"lat": 95.0, "lon": 34.9, "alt_asl": 300.0})
    assert bad_lat.status_code in (400, 422)
    bad_lon = client.post("/api/mission/origin", json={"lat": 31.6, "lon": -195.0, "alt_asl": 300.0})
    assert bad_lon.status_code in (400, 422)

    # 2. Set custom WGS84 Site Origin (e.g., Ramon Crater / Negev: 30.6085°N, 34.8015°E, 510m ASL)
    custom_lat = 30.6085
    custom_lon = 34.8015
    custom_alt = 510.0
    origin_res = client.post(
        "/api/mission/origin",
        json={"lat": custom_lat, "lon": custom_lon, "alt_asl": custom_alt},
    )
    assert origin_res.status_code == 200
    origin_payload = origin_res.json()["geodetic_origin"]
    assert abs(origin_payload["lat"] - custom_lat) < 1e-6
    assert abs(origin_payload["lon"] - custom_lon) < 1e-6
    assert abs(origin_payload["alt_asl"] - custom_alt) < 1e-2

    # 3. Generate SAR Grid and export KML
    grid_res = client.post(
        "/api/mission/sar-grid",
        json={
            "polygon_xz": VALLEY_POLYGON,
            "altitude_agl_m": 60.0,
            "sensor_mode": "THERMAL",
            "sidelap_pct": 70.0,
            "sweep_angle_deg": 0.0,
        },
    )
    assert grid_res.status_code == 200

    kml_res = client.get("/api/mission/export-kml?format=kml")
    assert kml_res.status_code == 200
    root = ET.fromstring(kml_res.content)

    # First corner of VALLEY_POLYGON is (x=60, z=-70)
    expected_corner_lat, expected_corner_lon = local_to_wgs84(60.0, -70.0, custom_lat, custom_lon)
    expected_corner_alt = custom_alt + 60.0

    poly_coords_text = None
    for elem in root.iter():
        if elem.tag.split("}")[-1] == "Polygon":
            for sub in elem.iter():
                if sub.tag.split("}")[-1] == "coordinates" and sub.text:
                    poly_coords_text = sub.text.strip()
                    break
    assert poly_coords_text is not None
    first_tuple = poly_coords_text.split()[0].split(",")
    kml_lon, kml_lat, kml_alt = float(first_tuple[0]), float(first_tuple[1]), float(first_tuple[2])
    assert abs(kml_lat - expected_corner_lat) < 1e-5
    assert abs(kml_lon - expected_corner_lon) < 1e-5
    assert abs(kml_alt - expected_corner_alt) < 0.1

    # 4. Also verify exported Autel WPML (.kmz) reflects the custom origin
    kmz_res = client.get("/api/mission/export-kml?format=wpml_kmz")
    assert kmz_res.status_code == 200
    with zipfile.ZipFile(io.BytesIO(kmz_res.content), mode="r") as zf:
        wpml_xml = zf.read("wpmz/waylines.wpml").decode("utf-8")
        assert f"<wpml:originLat>{custom_lat:.7f}</wpml:originLat>" in wpml_xml
        assert f"<wpml:originLon>{custom_lon:.7f}</wpml:originLon>" in wpml_xml

    # 5. Also verify uploading an external real-world KML via POST /api/mission/upload-kml auto-centers simulator origin
    ext_kml = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>35.2100000,31.7700000,750.0 35.2120000,31.7700000,750.0 35.2120000,31.7720000,750.0 35.2100000,31.7720000,750.0 35.2100000,31.7700000,750.0</coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>"""
    up_res = client.post(
        "/api/mission/upload-kml",
        files={"file": ("jerusalem_sector.kml", ext_kml.encode("utf-8"), "application/vnd.google-earth.kml+xml")},
    )
    assert up_res.status_code == 200
    up_json = up_res.json()
    assert abs(up_json["geodetic_origin"]["lat"] - 31.7710) < 1e-4
    assert abs(up_json["geodetic_origin"]["lon"] - 35.2110) < 1e-4
    assert abs(simulator.origin_lat - 31.7710) < 1e-4
    assert abs(simulator.origin_lon - 35.2110) < 1e-4


def test_simulator_sar_execution_detects_heat_and_retasks_relay():
    sim = SwarmSimulator()
    sim.mission_planner.generate_grid(VALLEY_POLYGON, 60.0, "THERMAL", 70.0, 0.0)
    sim.execute_sar_mission()

    for _ in range(180):
        sim.step(0.1)
        if sim.mission_planner.relay_retasked and len(sim.sar_detections) >= 1:
            break

    assert sim.mission_planner.relay_retasked is True
    assert len(sim.sar_detections) >= 1


def test_origin_updates_lrf_blackbox_and_websocket_telemetry():
    client = TestClient(app)
    simulator.reset()
    simulator.pin_lrf_target("UAV-1")

    res = client.post(
        "/api/mission/origin",
        json={"lat": 32.8156, "lon": 34.9892, "alt_asl": 425.0},
    )
    assert res.status_code == 200

    # Verify live LRF readout and pinned target reflect the new datum
    state = client.get("/api/state").json()
    assert abs(state["geodetic_origin"]["lat"] - 32.8156) < 1e-6
    assert abs(state["geodetic_origin"]["lon"] - 34.9892) < 1e-6
    assert abs(state["geodetic_origin"]["alt_asl"] - 425.0) < 1e-2

    pin = state["pinned_targets"][0]
    exp_pin_lat, exp_pin_lon = local_to_wgs84(pin["position"][0], pin["position"][2], 32.8156, 34.9892)
    assert abs(pin["lat"] - exp_pin_lat) < 1e-4
    assert abs(pin["lon"] - exp_pin_lon) < 1e-4

    # Verify Blackbox CSV export reflects the new datum
    csv_text = client.get("/api/blackbox/export/csv").text
    assert "32.8" in csv_text

