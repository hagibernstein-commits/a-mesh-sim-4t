"""Unit tests for Phase 1, 2 & 3 Simulation, A-Mesh Relay, Gimbal LRF, and 720° Perception."""

from __future__ import annotations
import numpy as np
from fastapi.testclient import TestClient

from app.specs import EVO_MAX_4T_SPECS
from app.simulator import SwarmSimulator
from app.main import app, simulator


def test_evo_max_4t_specs():
    assert EVO_MAX_4T_SPECS.mass_kg == 1.62
    assert EVO_MAX_4T_SPECS.max_horizontal_speed_ms == 23.0
    assert EVO_MAX_4T_SPECS.max_flight_time_min == 42.0
    assert EVO_MAX_4T_SPECS.wide_fov_deg == 85.0
    assert EVO_MAX_4T_SPECS.thermal_fov_deg == 42.0
    assert EVO_MAX_4T_SPECS.lrf_max_range_m == 1200.0
    assert EVO_MAX_4T_SPECS.fisheye_range_m == 40.0
    assert EVO_MAX_4T_SPECS.fisheye_min_lux == 15.0
    assert EVO_MAX_4T_SPECS.mmwave_range_m == 50.0
    assert EVO_MAX_4T_SPECS.mmwave_min_wire_diameter_mm == 12.7


def test_ridge_crossing_and_autonomous_amesh_relay():
    sim = SwarmSimulator()
    u1 = sim.drones["UAV-1"]
    u2 = sim.drones["UAV-2"]

    # Place UAV-1 in East Tactical Valley behind Diablo Ridge
    u1.true_position = np.array([150.0, 58.0, 0.0], dtype=float)
    u1.position = u1.true_position.copy()
    sim.step(0.05)

    assert sim.mesh_summary["topology_mode"] == "2_HOP_AMESH_ACTIVE"
    assert sim.mesh_summary["active_route"] == ["GCS", "UAV-2", "UAV-1"]
    assert u2.override_target is not None
    assert float(u2.override_target[1]) >= 175.0


def test_phase2_thermal_entities_gimbal_lrf_and_pin_target():
    sim = SwarmSimulator()
    assert len(sim.terrain.thermal_entities) == 4

    u1 = sim.drones["UAV-1"]
    u1.set_gimbal(pitch_deg=-35.0, yaw_deg=15.0, sensor_mode="THERMAL", thermal_palette="IRONBOW", zoom_level=10.0)
    sim.step(0.05)

    telem = u1.to_telemetry(sim.terrain)
    assert telem["sensor_mode"] == "THERMAL"
    assert telem["thermal_palette"] == "IRONBOW"
    assert telem["zoom_level"] == 10.0
    assert telem["lrf"]["valid"] is True

    pin = sim.pin_lrf_target("UAV-1")
    assert pin["id"] == "PIN-01"
    assert len(sim.pinned_targets) == 1
    assert sim.drones["UAV-3"].gimbal_tracking_target is not None


def test_phase3_720_perception_powerlines_and_vslam_imu_drift():
    sim = SwarmSimulator()
    sim.trigger_valley_dome_wire_scenario()
    u1 = sim.drones["UAV-1"]

    # Place UAV-1 near 230kV HV wire span inside Jamming Dome in daylight (650 lux -> V-SLAM)
    span2_pt = np.array(sim.terrain.power_lines[1].sample_points(10)[5], dtype=float)
    u1.true_position = span2_pt + np.array([0.0, 4.0, 0.0], dtype=float)
    sim.ambient_lux = 650.0
    sim.step(0.1)

    assert u1.nav_mode == "V-SLAM"
    assert u1.perception_state["fisheye_status"] == "ACTIVE"
    assert u1.perception_state["apas_active"] is True

    # Switch to Night 5 lux -> Fisheye LOW-LIGHT BLIND, mmWave still active, nav_mode -> IMU-DRIFT
    sim.ambient_lux = 5.0
    for _ in range(10):
        sim.step(0.1)
    assert u1.nav_mode == "IMU-DRIFT"
    assert u1.perception_state["fisheye_status"] == "LOW-LIGHT BLIND"
    assert "ACTIVE" in u1.perception_state["mmwave_status"]


def test_websocket_and_controls():
    client = TestClient(app)
    simulator.reset()

    res = client.get("/api/terrain")
    assert res.status_code == 200
    data = res.json()
    assert "geodetic_origin" in data
    assert len(data["buildings"]) >= 90

    health_res = client.get("/api/health")
    assert health_res.status_code == 200
    assert health_res.json() == {"status": "ok"}

    spa_res = client.get("/")
    assert spa_res.status_code == 200
    assert "<!doctype html>" in spa_res.text.lower() or "<div id=\"root\">" in spa_res.text.lower()

    with client.websocket_connect("/ws/telemetry") as ws:
        msg = ws.receive_json()
        assert "drones" in msg
        assert "geodetic_origin" in msg
        assert abs(msg["geodetic_origin"]["lat"] - simulator.origin_lat) < 1e-6
        assert abs(msg["geodetic_origin"]["lon"] - simulator.origin_lon) < 1e-6

