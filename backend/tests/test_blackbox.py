"""Unit tests for Phase 4 Flight Data Blackbox Recorder, Replay & Debrief Export."""

from __future__ import annotations
import json
from fastapi.testclient import TestClient

from app.simulator import SwarmSimulator
from app.main import app, simulator


def test_blackbox_recording_and_event_detection():
    sim = SwarmSimulator()
    sim.trigger_valley_dome_wire_scenario()
    sim.ambient_lux = 5.0
    for _ in range(15):
        sim.step(0.1)
    sim.pin_lrf_target("UAV-1")

    summary = sim.blackbox.get_summary()
    assert summary["total_frames"] >= 15
    event_types = {e["event_type"] for e in summary["events"]}
    assert "GNSS_JAMMING_ENTER" in event_types
    assert "VSLAM_LOW_LIGHT_DEGRADED" in event_types
    assert "LRF_TARGET_PINNED" in event_types


def test_blackbox_replay_snapshot_and_trails():
    sim = SwarmSimulator()
    for _ in range(12):
        sim.step(0.1)

    snap = sim.blackbox.get_replay_snapshot(6)
    assert snap["frame_index"] == 6
    assert "replay_trails" in snap
    assert len(snap["replay_trails"]["UAV-1"]["true"]) >= 1
    assert "geodetic_origin" in snap


def test_blackbox_csv_and_json_debrief_exports():
    client = TestClient(app)
    simulator.reset()
    for _ in range(5):
        simulator.step(0.1)

    csv_res = client.get("/api/blackbox/export/csv")
    assert csv_res.status_code == 200
    assert "wgs84_lat" in csv_res.text
    assert "UAV-1" in csv_res.text

    json_res = client.get("/api/blackbox/export/json")
    assert json_res.status_code == 200
    parsed = json.loads(json_res.text)
    assert "geodetic_origin" in parsed
    assert parsed["total_frames"] >= 5
