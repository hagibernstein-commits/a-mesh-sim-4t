"""20Hz Multi-UAV Swarm Simulator Engine with Configurable WGS84 Geodetic Origin."""

from __future__ import annotations
from collections import deque
import math
from typing import Deque, Dict, List, Any, Optional
import numpy as np

from .specs import EVO_MAX_4T_SPECS
from .terrain import (
    TacticalTerrain,
    DEFAULT_ORIGIN_LAT,
    DEFAULT_ORIGIN_LON,
    DEFAULT_ORIGIN_ALT_ASL,
    local_to_wgs84,
)
from .drone import EvoMax4T
from .amesh import AMeshEngine
from .blackbox import FlightBlackbox
from .mission_planner import (
    MissionPlanner,
    VALLEY_POLYGON,
    compute_swath,
    export_kml,
    export_autel_wpml_kmz,
    parse_kml_kmz,
)


class SwarmSimulator:
    """Orchestrates the 3-UAV Autel EVO Max 4T swarm, A-Mesh RF engine, Blackbox, and SAR Mission Planner."""

    def __init__(
        self,
        origin_lat: float = 31.6935,
        origin_lon: float = 34.9780,
        origin_alt_asl: float = 335.0,
    ) -> None:
        self.origin_lat: float = float(origin_lat)
        self.origin_lon: float = float(origin_lon)
        self.origin_alt_asl: float = float(origin_alt_asl)

        self.terrain = TacticalTerrain(
            origin_lat=self.origin_lat,
            origin_lon=self.origin_lon,
            origin_alt_asl=self.origin_alt_asl,
        )
        self.amesh = AMeshEngine(self.terrain)
        self.blackbox = FlightBlackbox(max_frames=12000)
        self.mission_planner = MissionPlanner(self.terrain)

        self.sim_time: float = 0.0
        self.paused: bool = False
        self.ambient_lux: float = 650.0
        self.wind_speed_ms: float = 4.5
        self.wind_dir_deg: float = 115.0
        self.ew_jamming_active: bool = False

        self.drones: Dict[str, EvoMax4T] = {}
        self.links: List[Dict[str, Any]] = []
        self.mesh_summary: Dict[str, Any] = {}
        self.pinned_targets: List[Dict[str, Any]] = []
        self.jamming_zones: List[Dict[str, Any]] = []
        self.sar_detections: List[Dict[str, Any]] = []
        self._detected_entity_ids: set[str] = set()
        self.event_log: Deque[str] = deque(maxlen=40)

        self._init_drones()
        self.step(0.05)

    def _init_drones(self) -> None:
        # UAV-1 patrols Giv'ot Eden outer security perimeter fence line and descends into Route 375 / Emek HaEla
        u1_wps = [
            [-280.0, 74.0, -85.0],
            [-95.0, 92.0, -82.0],
            [45.0, 88.0, -20.0],
            [145.0, 78.0, -10.0],
            [175.0, 82.0, 32.0],
            [-95.0, 90.0, 85.0],
            [-280.0, 76.0, 82.0],
        ]
        # UAV-2 loiters over Giv'ot Eden eastern ridge line to bridge A-Mesh LOS into Emek HaEla
        u2_wps = [
            [-165.0, 112.0, -25.0],
            [-115.0, 124.0, 5.0],
            [-145.0, 118.0, 38.0],
        ]
        # UAV-3 provides overwatch along the Route 375 / Emek HaEla valley corridor and HV transmission towers
        u3_wps = [
            [75.0, 115.0, -55.0],
            [165.0, 118.0, -45.0],
            [175.0, 115.0, 45.0],
            [85.0, 112.0, 40.0],
        ]

        self.drones = {
            "UAV-1": EvoMax4T("UAV-1", "ALPHA-1", "Scout", [-240.0, 68.0, -25.0], u1_wps),
            "UAV-2": EvoMax4T("UAV-2", "BRAVO-2", "Relay", [-165.0, 108.0, 15.0], u2_wps),
            "UAV-3": EvoMax4T("UAV-3", "CHARLIE-3", "Overwatch", [75.0, 112.0, -45.0], u3_wps),
        }
        self.event_log.append(
            "[0.0s] [SYSTEM] A-Mesh 1.0 Swarm online @ Giv'ot Eden / Emek HaEla (GCS-GIVOT-EDEN • 31.6935°N, 34.9780°E)."
        )

    def set_geodetic_origin(
        self,
        lat: float,
        lon: float,
        alt_asl: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Update the active WGS84 coordinate datum across simulator, terrain, LRF, pins, and exports."""
        alt_val = self.origin_alt_asl if alt_asl is None else float(alt_asl)
        updated = self.terrain.set_origin(float(lat), float(lon), alt_val)
        self.origin_lat = updated["lat"]
        self.origin_lon = updated["lon"]
        self.origin_alt_asl = updated["alt_asl"]
        self.mission_planner.set_geodetic_origin(self.origin_lat, self.origin_lon, self.origin_alt_asl)

        # Immediately re-project all pinned LRF targets
        for pin in self.pinned_targets:
            pos = pin.get("position", [0.0, 20.0, 0.0])
            plat, plon = self.terrain.local_to_wgs84(float(pos[0]), float(pos[2]))
            pin["lat"] = round(plat, 6)
            pin["lon"] = round(plon, 6)
            pin["alt_asl"] = round(self.origin_alt_asl + float(pos[1]), 1)

        # Immediately re-project all SAR thermal detections
        for det in self.sar_detections:
            pos = det.get("position", [0.0, 20.0, 0.0])
            dlat, dlon = self.terrain.local_to_wgs84(float(pos[0]), float(pos[2]))
            det["lat"] = round(dlat, 6)
            det["lon"] = round(dlon, 6)
            det["alt_asl"] = round(self.origin_alt_asl + float(pos[1]), 1)

        # Immediately refresh live LRF readouts on all drones
        for d in self.drones.values():
            abs_yaw = d.heading_deg + d.gimbal_yaw_deg
            d.lrf_readout = self.terrain.raycast_lrf(d.true_position, d.gimbal_pitch_deg, abs_yaw)

        self.event_log.append(
            f"[{self.sim_time:.1f}s] [DATUM] WGS84 Site Origin updated -> ({self.origin_lat:.6f}°, {self.origin_lon:.6f}°, {self.origin_alt_asl:.1f}m ASL)"
        )
        return self.get_geodetic_origin_summary()

    def get_geodetic_origin_summary(self) -> Dict[str, Any]:
        gcs_lat, gcs_lon = self.terrain.local_to_wgs84(
            float(self.terrain.gcs_position[0]),
            float(self.terrain.gcs_position[2]),
        )
        planner_state = self.mission_planner.get_state()
        return {
            "lat": round(self.origin_lat, 7),
            "lon": round(self.origin_lon, 7),
            "alt_asl": round(self.origin_alt_asl, 2),
            "origin_lat": round(self.origin_lat, 7),
            "origin_lon": round(self.origin_lon, 7),
            "origin_alt_asl": round(self.origin_alt_asl, 2),
            "gcs_lat": round(gcs_lat, 7),
            "gcs_lon": round(gcs_lon, 7),
            "gcs_alt_asl": round(self.origin_alt_asl + float(self.terrain.gcs_position[1]), 2),
            "polygon_center_wgs84": planner_state.get("polygon_center_wgs84"),
        }

    def reset(self) -> None:
        self.sim_time = 0.0
        self.paused = False
        self.ambient_lux = 650.0
        self.wind_speed_ms = 4.5
        self.ew_jamming_active = False
        self.pinned_targets.clear()
        self.jamming_zones.clear()
        self.sar_detections.clear()
        self._detected_entity_ids.clear()
        self.event_log.clear()
        self.blackbox.clear()
        self.mission_planner.executing = False
        self.mission_planner.relay_retasked = False
        self.mission_planner.relay_retask_info = None
        self._init_drones()
        self.step(0.05)

    def _is_in_jamming_zone(self, pos: np.ndarray) -> bool:
        if self.ew_jamming_active and float(pos[0]) > -30.0:
            return True
        for jz in self.jamming_zones:
            j_pos = np.array(jz["position"], dtype=float)
            horiz_d = math.hypot(float(pos[0] - j_pos[0]), float(pos[2] - j_pos[2]))
            if horiz_d <= float(jz.get("radius_m", 110.0)):
                return True
        return False

    def drop_jamming_zone(
        self,
        x: float = 135.0,
        z: float = -10.0,
        radius_m: float = 115.0,
    ) -> Dict[str, Any]:
        y = self.terrain.get_elevation(x, z)
        zone = {
            "id": f"JAM-DOME-{len(self.jamming_zones) + 1:02d}",
            "position": [round(float(x), 2), round(float(y), 2), round(float(z), 2)],
            "radius_m": round(float(radius_m), 1),
            "power_dbm": 42.0,
        }
        self.jamming_zones.append(zone)
        self.event_log.append(
            f"[{self.sim_time:.1f}s] [EW-JAM] Deployed GNSS Denial Dome {zone['id']} at ({x:.0f}m, {z:.0f}m, R={radius_m:.0f}m)"
        )
        return zone

    def trigger_valley_dome_wire_scenario(self) -> Dict[str, Any]:
        """Configure UAV-1 to traverse the GNSS Jamming Dome and HV Power-Line Corridor in East Valley."""
        self.jamming_zones.clear()
        zone = self.drop_jamming_zone(x=135.0, z=-5.0, radius_m=115.0)
        u1 = self.drones["UAV-1"]
        u1.clear_sar_waypoints()
        u1.true_position = np.array([75.0, 52.0, -25.0], dtype=float)
        u1.position = u1.true_position.copy()
        u1.estimated_position = u1.true_position.copy()
        u1.waypoints = [
            np.array([145.0, 50.0, 0.0], dtype=float),
            np.array([205.0, 52.0, 10.0], dtype=float),
            np.array([255.0, 62.0, 15.0], dtype=float),
        ]
        u1.current_wp_idx = 0
        self.event_log.append(
            f"[{self.sim_time:.1f}s] [SCENARIO] Valley Jamming Dome + 230kV HV Wire Run activated for UAV-1."
        )
        return {"status": "ok", "jamming_zone": zone}

    def pin_lrf_target(self, drone_id: str = "UAV-1") -> Dict[str, Any]:
        drone = self.drones.get(drone_id) or self.drones["UAV-1"]
        lrf = drone.lrf_readout
        pos = lrf.get("target_pos", [140.0, 22.0, 0.0])
        lat, lon = self.terrain.local_to_wgs84(float(pos[0]), float(pos[2]))
        alt_asl = self.origin_alt_asl + float(pos[1])

        pin = {
            "id": f"PIN-{len(self.pinned_targets) + 1:02d}",
            "pinned_by": drone.id,
            "sim_time": round(self.sim_time, 1),
            "target_id": lrf.get("target_id", "TERRAIN"),
            "label": lrf.get("target_label", "Tactical Pin"),
            "temp_c": lrf.get("target_temp_c", 24.0),
            "slant_range_m": lrf.get("slant_range_m", 100.0),
            "position": pos,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "alt_asl": round(alt_asl, 1),
        }
        self.pinned_targets.append(pin)

        # Automatically slew UAV-3 Overwatch gimbal onto the newly pinned target
        u3 = self.drones.get("UAV-3")
        if u3 is not None and u3.id != drone.id:
            u3.slew_gimbal_to_point(np.array(pos, dtype=float))
            u3.sensor_mode = "THERMAL"

        self.blackbox.record_event(
            sim_time=self.sim_time,
            event_type="LRF_TARGET_PINNED",
            drone_id=drone.id,
            severity="INFO",
            message=f"{drone.id} pinned {pin['id']} ({pin['label']}) at {pin['lat']:.5f}N, {pin['lon']:.5f}E — UAV-3 Overwatch slewed",
            position=pos,
            details=pin,
        )
        self.event_log.append(
            f"[{self.sim_time:.1f}s] [A-MESH PIN] {drone.id} broadcasts {pin['id']} ({pin['label']}) -> UAV-3 Overwatch gimbal locked."
        )
        return pin

    def execute_sar_mission(self) -> Dict[str, Any]:
        """Start cooperative 3-UAV SAR sweep across the planned polygon grid."""
        if not self.mission_planner.legs:
            self.mission_planner.generate_grid(
                polygon_xz=self.mission_planner.polygon_xz or VALLEY_POLYGON,
                altitude_agl_m=self.mission_planner.altitude_agl_m,
                sensor_mode=self.mission_planner.sensor_mode,
                sidelap_pct=self.mission_planner.sidelap_pct,
                sweep_angle_deg=self.mission_planner.sweep_angle_deg,
                batteries={uid: d.battery_pct for uid, d in self.drones.items()},
            )

        self.mission_planner.relay_retasked = False
        self.mission_planner.relay_retask_info = None
        self.mission_planner.executing = True
        self.sar_detections.clear()
        self._detected_entity_ids.clear()

        partitions = self.mission_planner.partitions
        for uid, d in self.drones.items():
            wps = partitions.get(uid, {}).get("waypoints", [])
            d.assign_sar_waypoints(wps)
            if wps:
                # Place drone near approach to its first SAR waypoint so sweep progresses briskly
                first_wp = np.array(wps[0], dtype=float)
                d.true_position = first_wp + np.array([-18.0, 2.0, 0.0], dtype=float)
                d.position = d.true_position.copy()
                d.estimated_position = d.true_position.copy()

        self.event_log.append(
            f"[{self.sim_time:.1f}s] [SAR PLANNER] Cooperative 3-UAV Nadir Sweep started ({self.mission_planner.mission_id})."
        )
        return self.mission_planner.get_state()

    def clear_sar_mission(self) -> Dict[str, Any]:
        for d in self.drones.values():
            d.clear_sar_waypoints()
        self.sar_detections.clear()
        self._detected_entity_ids.clear()
        return self.mission_planner.clear()

    def import_kml_kmz(self, raw_bytes: bytes, filename: str = "mission.kml") -> Dict[str, Any]:
        """Parse an uploaded .kml/.kmz file, auto-center geodetic_origin if external, and generate SAR grid."""
        parsed = parse_kml_kmz(raw_bytes, filename=filename, auto_center_origin=True)
        new_origin = parsed.get("geodetic_origin", {})
        if "lat" in new_origin and "lon" in new_origin:
            self.set_geodetic_origin(
                new_origin["lat"],
                new_origin["lon"],
                new_origin.get("alt_asl", self.origin_alt_asl),
            )
        self.mission_planner.last_imported_filename = filename
        grid_state = self.mission_planner.generate_grid(
            polygon_xz=parsed["polygon_xz"],
            altitude_agl_m=self.mission_planner.altitude_agl_m,
            sensor_mode=self.mission_planner.sensor_mode,
            sidelap_pct=self.mission_planner.sidelap_pct,
            sweep_angle_deg=self.mission_planner.sweep_angle_deg,
            batteries={uid: d.battery_pct for uid, d in self.drones.items()},
        )
        grid_state["imported"] = parsed
        return grid_state

    def export_mission_kml(self) -> str:
        return export_kml(
            self.mission_planner.get_state(),
            sar_detections=self.sar_detections,
            pinned_targets=self.pinned_targets,
            origin_lat=self.origin_lat,
            origin_lon=self.origin_lon,
            origin_alt_asl=self.origin_alt_asl,
        )

    def export_mission_wpml_kmz(self) -> bytes:
        return export_autel_wpml_kmz(
            self.mission_planner.get_state(),
            sar_detections=self.sar_detections,
            pinned_targets=self.pinned_targets,
            origin_lat=self.origin_lat,
            origin_lon=self.origin_lon,
            origin_alt_asl=self.origin_alt_asl,
        )

    def _check_sar_relay_failover_and_detections(self) -> None:
        if not self.mission_planner.executing:
            return

        # 1. Check if UAV-2 was pulled to A-Mesh relay while holding unvisited SAR waypoints
        u2 = self.drones["UAV-2"]
        if u2.override_target is not None and u2.sar_active and not self.mission_planner.relay_retasked:
            rem_wps = u2.get_remaining_sar_waypoints()
            if rem_wps:
                retask = self.mission_planner.handle_relay_failover(rem_wps)
                u2.clear_sar_waypoints()
                u2.flight_mode = "AMESH_RELAY (SAR RETASKED)"
                for target_uid, extra_wps in retask["reassigned_waypoints"].items():
                    if extra_wps and target_uid in self.drones:
                        td = self.drones[target_uid]
                        td.sar_waypoints.extend([np.array(w, dtype=float) for w in extra_wps])
                        td.sar_total_count = len(td.sar_waypoints)
                        td.sar_active = True

                msg = (
                    f"UAV-2 pulled to A-Mesh Relay — {retask['unvisited_count']} unvisited WP reassigned "
                    f"(UAV-1: +{retask['reassigned_counts'].get('UAV-1', 0)}, UAV-3: +{retask['reassigned_counts'].get('UAV-3', 0)})"
                )
                self.blackbox.record_event(
                    sim_time=self.sim_time,
                    event_type="SAR_RELAY_RETASK",
                    drone_id="UAV-2",
                    severity="WARNING",
                    message=msg,
                    position=[round(float(v), 2) for v in u2.true_position],
                    details=self.mission_planner.relay_retask_info or {},
                )
                self.event_log.append(f"[{self.sim_time:.1f}s] [SAR FAILOVER] {msg}")

        # 2. Check nadir thermal footprint intersections with valley ThermalEntities
        swath_r = max(24.0, compute_swath(self.mission_planner.altitude_agl_m, "THERMAL", 70.0)["swath_width_m"] * 0.68)
        for uid, d in self.drones.items():
            if not d.sar_active and d.flight_mode not in ("SAR_SWEEP_NADIR", "SAR_SWEEP_COMPLETE"):
                continue
            dx, dz = float(d.true_position[0]), float(d.true_position[2])
            for ent in self.terrain.thermal_entities:
                if ent.id in self._detected_entity_ids:
                    continue
                horiz_dist = math.hypot(dx - ent.x, dz - ent.z)
                if horiz_dist <= swath_r:
                    self._detected_entity_ids.add(ent.id)
                    lat, lon = self.terrain.local_to_wgs84(ent.x, ent.z)
                    alt_asl = self.origin_alt_asl + ent.y
                    det = {
                        "id": f"SAR-{len(self.sar_detections) + 1:02d}",
                        "entity_id": ent.id,
                        "label": ent.label,
                        "category": ent.category,
                        "temp_c": round(ent.temp_c, 1),
                        "detected_by": uid,
                        "sim_time": round(self.sim_time, 1),
                        "position": [round(ent.x, 2), round(ent.y, 2), round(ent.z, 2)],
                        "lat": round(lat, 6),
                        "lon": round(lon, 6),
                        "alt_asl": round(alt_asl, 1),
                    }
                    self.sar_detections.append(det)
                    self.blackbox.record_event(
                        sim_time=self.sim_time,
                        event_type="SAR_THERMAL_DETECTION",
                        drone_id=uid,
                        severity="CRITICAL",
                        message=f"SAR HEAT CONTACT [{det['id']}] {ent.id} {ent.label} ({ent.temp_c:.1f}°C) captured by {uid} @ {lat:.5f}°N, {lon:.5f}°E",
                        position=det["position"],
                        details=det,
                    )
                    self.event_log.append(
                        f"[{self.sim_time:.1f}s] [SAR CONTACT] {det['id']} ({ent.label}, {ent.temp_c:.1f}°C) locked by {uid} (-90° nadir)."
                    )

        # Check if all sweepers completed
        if all(not d.sar_active for d in self.drones.values()):
            self.mission_planner.executing = False

    def step(self, dt: float = 0.05) -> None:
        if self.paused:
            return

        self.sim_time += dt
        for ent in self.terrain.thermal_entities:
            ent.update(self.sim_time, self.terrain)

        wind_rad = math.radians(self.wind_dir_deg)
        wind_vec = np.array(
            [math.cos(wind_rad) * self.wind_speed_ms, 0.0, math.sin(wind_rad) * self.wind_speed_ms],
            dtype=float,
        )

        # Update A-Mesh links & relay override targets
        self.links, self.mesh_summary = self.amesh.update_mesh(self.drones, self.jamming_zones)

        # Step each UAV
        for d in self.drones.values():
            in_jam = self._is_in_jamming_zone(d.true_position)
            d.step(
                dt=dt,
                terrain=self.terrain,
                wind_vec=wind_vec,
                ambient_lux=self.ambient_lux,
                in_jamming_zone=in_jam,
                sim_time=self.sim_time,
            )

        # Re-evaluate links after drone movement and check SAR progress
        self.links, self.mesh_summary = self.amesh.update_mesh(self.drones, self.jamming_zones)
        self._check_sar_relay_failover_and_detections()

        snapshot = self.get_state_snapshot()
        self.blackbox.record_frame(snapshot)

    def get_state_snapshot(self) -> Dict[str, Any]:
        return {
            "sim_time": round(self.sim_time, 2),
            "paused": self.paused,
            "ambient_lux": round(self.ambient_lux, 1),
            "wind_speed_ms": round(self.wind_speed_ms, 1),
            "wind_dir_deg": round(self.wind_dir_deg, 1),
            "ew_jamming_active": self.ew_jamming_active,
            "specs": EVO_MAX_4T_SPECS.to_dict(),
            "geodetic_origin": self.get_geodetic_origin_summary(),
            "gcs_position": [round(float(v), 2) for v in self.terrain.gcs_position],
            "drones": [d.to_telemetry(self.terrain) for d in self.drones.values()],
            "links": self.links,
            "mesh_summary": self.mesh_summary,
            "thermal_entities": [e.to_dict(self.terrain) for e in self.terrain.thermal_entities],
            "pinned_targets": self.pinned_targets,
            "jamming_zones": self.jamming_zones,
            "sar_mission": self.mission_planner.get_state(),
            "sar_detections": self.sar_detections,
            "event_log": list(self.event_log)[-18:],
            "blackbox_frames": len(self.blackbox.frames),
        }
