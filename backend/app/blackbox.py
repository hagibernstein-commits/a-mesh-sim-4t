"""Flight Data Blackbox Recorder, MissionEvent Marker Detection, 3D Timeline Replay & CSV/JSON Debrief Export."""

from __future__ import annotations
from collections import deque
from dataclasses import dataclass, asdict
import csv
import io
import json
from typing import Deque, Dict, List, Any, Optional
from .terrain import get_active_origin, local_to_wgs84


@dataclass
class MissionEvent:
    id: str
    frame_index: int
    sim_time: float
    event_type: str
    drone_id: str
    severity: str
    message: str
    position: List[float]
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FlightBlackbox:
    """20Hz ring-buffer telemetry recorder with automatic MissionEvent tagging and debrief export."""

    def __init__(self, max_frames: int = 12000) -> None:
        self.max_frames = max_frames
        self.frames: Deque[Dict[str, Any]] = deque(maxlen=max_frames)
        self.events: List[MissionEvent] = []
        self._event_seq: int = 0
        self._prev_topology: str = "DIRECT_GCS_LOS"
        self._prev_jammed: Dict[str, bool] = {}
        self._prev_nav_mode: Dict[str, str] = {}
        self._last_apas_event_time: Dict[str, float] = {}

    def clear(self) -> None:
        self.frames.clear()
        self.events.clear()
        self._event_seq = 0
        self._prev_topology = "DIRECT_GCS_LOS"
        self._prev_jammed.clear()
        self._prev_nav_mode.clear()
        self._last_apas_event_time.clear()

    def record_event(
        self,
        sim_time: float,
        event_type: str,
        drone_id: str,
        severity: str,
        message: str,
        position: List[float],
        details: Optional[Dict[str, Any]] = None,
    ) -> MissionEvent:
        self._event_seq += 1
        frame_idx = max(0, len(self.frames) - 1)
        origin = get_active_origin()
        lat, lon = local_to_wgs84(position[0], position[2], origin["lat"], origin["lon"])
        merged_details = dict(details or {})
        merged_details.setdefault("lat", round(lat, 6))
        merged_details.setdefault("lon", round(lon, 6))
        merged_details.setdefault("alt_asl", round(origin["alt_asl"] + float(position[1]), 2))
        ev = MissionEvent(
            id=f"MKR-{self._event_seq:03d}",
            frame_index=frame_idx,
            sim_time=round(float(sim_time), 2),
            event_type=event_type,
            drone_id=drone_id,
            severity=severity,
            message=message,
            position=[round(float(v), 2) for v in position],
            details=merged_details,
        )
        self.events.append(ev)
        return ev

    def record_frame(self, snapshot: Dict[str, Any]) -> None:
        frame_idx = len(self.frames)
        sim_time = float(snapshot.get("sim_time", 0.0))
        origin = snapshot.get("geodetic_origin") or get_active_origin()

        drones_compact: List[Dict[str, Any]] = []
        for d in snapshot.get("drones", []):
            did = d["id"]
            pos = d["true_position"]
            lat, lon = local_to_wgs84(pos[0], pos[2], origin["lat"], origin["lon"])
            alt_asl = float(origin["alt_asl"]) + float(pos[1])
            drones_compact.append(
                {
                    "id": did,
                    "callsign": d["callsign"],
                    "role": d["role"],
                    "position": d["position"],
                    "true_position": d["true_position"],
                    "estimated_position": d["estimated_position"],
                    "position_drift_m": d["position_drift_m"],
                    "velocity": d["velocity"],
                    "speed_ms": d["speed_ms"],
                    "heading_deg": d["heading_deg"],
                    "alt_agl": d["alt_agl"],
                    "alt_msl": round(alt_asl, 1),
                    "alt_asl": round(alt_asl, 1),
                    "gps_lat": round(lat, 6),
                    "gps_lon": round(lon, 6),
                    "battery_pct": d["battery_pct"],
                    "flight_mode": d["flight_mode"],
                    "nav_mode": d["nav_mode"],
                    "nav_state": d["nav_state"],
                    "gnss_jammed": d["gnss_jammed"],
                    "in_jamming_zone": d["in_jamming_zone"],
                    "rssi_dbm": d["rssi_dbm"],
                    "link_quality_pct": d["link_quality_pct"],
                    "connected_via": d["connected_via"],
                    "sensor_mode": d["sensor_mode"],
                    "thermal_palette": d["thermal_palette"],
                    "zoom_level": d["zoom_level"],
                    "fov_deg": d["fov_deg"],
                    "gimbal_pitch_deg": d["gimbal_pitch_deg"],
                    "gimbal_yaw_deg": d["gimbal_yaw_deg"],
                    "lrf": d["lrf"],
                    "perception_720": d["perception_720"],
                    "sar_progress": d.get("sar_progress", {}),
                }
            )

            # Detect automatic state transition events
            jammed = bool(d.get("gnss_jammed", False))
            was_jammed = self._prev_jammed.get(did, False)
            if jammed and not was_jammed:
                self.record_event(
                    sim_time=sim_time,
                    event_type="GNSS_JAMMING_ENTER",
                    drone_id=did,
                    severity="WARNING",
                    message=f"{did} entered GNSS Jamming Zone — switching to {d['nav_mode']}",
                    position=d["true_position"],
                    details={"nav_mode": d["nav_mode"]},
                )
            elif (not jammed) and was_jammed:
                self.record_event(
                    sim_time=sim_time,
                    event_type="GNSS_RTK_REACQUIRED",
                    drone_id=did,
                    severity="INFO",
                    message=f"{did} exited Jamming Zone — RTK-FIXED navigation restored (±0.03m)",
                    position=d["true_position"],
                    details={"nav_mode": d["nav_mode"]},
                )
            self._prev_jammed[did] = jammed

            nav_mode = d.get("nav_mode", "RTK-FIXED")
            prev_nav = self._prev_nav_mode.get(did, "RTK-FIXED")
            if nav_mode == "IMU-DRIFT" and prev_nav != "IMU-DRIFT":
                self.record_event(
                    sim_time=sim_time,
                    event_type="VSLAM_LOW_LIGHT_DEGRADED",
                    drone_id=did,
                    severity="CRITICAL",
                    message=f"{did} V-SLAM degraded in low light ({snapshot.get('ambient_lux', 5):.0f} lux < 15 lux) — entering IMU-DRIFT regime!",
                    position=d["true_position"],
                    details={"ambient_lux": snapshot.get("ambient_lux", 5.0)},
                )
            self._prev_nav_mode[did] = nav_mode

            perc = d.get("perception_720", {})
            if perc.get("apas_active") and perc.get("primary_threat"):
                last_t = self._last_apas_event_time.get(did, -999.0)
                if sim_time - last_t >= 6.0:
                    threat = perc["primary_threat"]
                    self._last_apas_event_time[did] = sim_time
                    self.record_event(
                        sim_time=sim_time,
                        event_type="APAS_OBSTACLE_AVOIDANCE",
                        drone_id=did,
                        severity="WARNING",
                        message=f"{did} bypassing {threat['id']} ({threat['label']}) via {threat['detected_by']}",
                        position=d["true_position"],
                        details={"threat_id": threat["id"], "distance_m": threat["distance_m"]},
                    )

        mesh_summary = snapshot.get("mesh_summary", {})
        topo = mesh_summary.get("topology_mode", "DIRECT_GCS_LOS")
        if topo != self._prev_topology:
            u2_pos = next((d["true_position"] for d in drones_compact if d["id"] == "UAV-2"), [0.0, 150.0, 0.0])
            self.record_event(
                sim_time=sim_time,
                event_type="AMESH_RELAY_HANDOFF",
                drone_id="UAV-2",
                severity="INFO",
                message=f"A-Mesh topology switched to {topo} ({' -> '.join(mesh_summary.get('active_route', []))})",
                position=u2_pos,
                details={"topology_mode": topo, "route": mesh_summary.get("active_route", [])},
            )
            self._prev_topology = topo

        frame = {
            "frame_index": frame_idx,
            "sim_time": round(sim_time, 2),
            "ambient_lux": snapshot.get("ambient_lux", 650.0),
            "wind_speed_ms": snapshot.get("wind_speed_ms", 4.5),
            "ew_jamming_active": snapshot.get("ew_jamming_active", False),
            "geodetic_origin": origin,
            "drones": drones_compact,
            "links": snapshot.get("links", []),
            "mesh_summary": mesh_summary,
            "thermal_entities": snapshot.get("thermal_entities", []),
            "pinned_targets": snapshot.get("pinned_targets", []),
            "jamming_zones": snapshot.get("jamming_zones", []),
            "sar_mission": snapshot.get("sar_mission", {}),
            "sar_detections": snapshot.get("sar_detections", []),
        }
        self.frames.append(frame)

    def get_summary(self, max_series_points: int = 180) -> Dict[str, Any]:
        total = len(self.frames)
        if total == 0:
            return {
                "total_frames": 0,
                "duration_sec": 0.0,
                "geodetic_origin": get_active_origin(),
                "events": [],
                "series": [],
                "trails": {},
            }

        step = max(1, total // max_series_points)
        sampled = list(self.frames)[::step]
        if sampled[-1]["frame_index"] != self.frames[-1]["frame_index"]:
            sampled.append(self.frames[-1])

        series: List[Dict[str, Any]] = []
        trails: Dict[str, Dict[str, List[List[float]]]] = {
            "UAV-1": {"true": [], "estimated": []},
            "UAV-2": {"true": [], "estimated": []},
            "UAV-3": {"true": [], "estimated": []},
        }

        for fr in sampled:
            d_map = {d["id"]: d for d in fr["drones"]}
            u1 = d_map.get("UAV-1", {})
            u2 = d_map.get("UAV-2", {})
            u3 = d_map.get("UAV-3", {})
            series.append(
                {
                    "frame_index": fr["frame_index"],
                    "sim_time": fr["sim_time"],
                    "uav1_rssi": u1.get("rssi_dbm", -60.0),
                    "uav2_rssi": u2.get("rssi_dbm", -55.0),
                    "uav3_rssi": u3.get("rssi_dbm", -58.0),
                    "uav1_drift_m": u1.get("position_drift_m", 0.03),
                    "uav2_drift_m": u2.get("position_drift_m", 0.03),
                    "uav3_drift_m": u3.get("position_drift_m", 0.03),
                    "uav1_alt_agl": u1.get("alt_agl", 50.0),
                    "uav1_obstacle_m": (u1.get("perception_720") or {}).get("closest_obstacle_m") or 50.0,
                }
            )
            for uid in ("UAV-1", "UAV-2", "UAV-3"):
                if uid in d_map:
                    trails[uid]["true"].append(d_map[uid]["true_position"])
                    trails[uid]["estimated"].append(d_map[uid]["estimated_position"])

        return {
            "total_frames": total,
            "duration_sec": self.frames[-1]["sim_time"],
            "geodetic_origin": get_active_origin(),
            "events": [e.to_dict() for e in self.events[-80:]],
            "series": series,
            "trails": trails,
        }

    def get_replay_snapshot(self, frame_index: int) -> Dict[str, Any]:
        if not self.frames:
            return {"error": "No recorded frames"}
        idx = max(0, min(len(self.frames) - 1, int(frame_index)))
        frame = dict(self.frames[idx])

        # Re-project drone & target WGS84 coordinates with current active geodetic origin
        origin = get_active_origin()
        frame["geodetic_origin"] = origin

        # Build historical 3D trails up to idx
        step = max(1, (idx + 1) // 90)
        trails: Dict[str, Dict[str, List[List[float]]]] = {
            "UAV-1": {"true": [], "estimated": []},
            "UAV-2": {"true": [], "estimated": []},
            "UAV-3": {"true": [], "estimated": []},
        }
        frames_list = list(self.frames)
        for i in range(0, idx + 1, step):
            for d in frames_list[i]["drones"]:
                uid = d["id"]
                if uid in trails:
                    trails[uid]["true"].append(d["true_position"])
                    trails[uid]["estimated"].append(d["estimated_position"])
        frame["replay_trails"] = trails
        frame["total_frames"] = len(self.frames)
        return frame

    def export_csv(self) -> str:
        """Export flattened multi-UAV telemetry debrief CSV using active WGS84 geodetic origin."""
        origin = get_active_origin()
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "frame_index",
                "sim_time_s",
                "drone_id",
                "callsign",
                "flight_mode",
                "nav_mode",
                "true_x_m",
                "true_y_m",
                "true_z_m",
                "wgs84_lat",
                "wgs84_lon",
                "wgs84_alt_asl_m",
                "est_x_m",
                "est_y_m",
                "est_z_m",
                "drift_m",
                "alt_agl_m",
                "speed_ms",
                "battery_pct",
                "rssi_dbm",
                "connected_via",
                "closest_obstacle_m",
            ]
        )
        for fr in self.frames:
            for d in fr["drones"]:
                tx, ty, tz = d["true_position"]
                ex, ey, ez = d["estimated_position"]
                lat, lon = local_to_wgs84(tx, tz, origin["lat"], origin["lon"])
                alt_asl = origin["alt_asl"] + float(ty)
                obs_m = (d.get("perception_720") or {}).get("closest_obstacle_m")
                writer.writerow(
                    [
                        fr["frame_index"],
                        fr["sim_time"],
                        d["id"],
                        d["callsign"],
                        d["flight_mode"],
                        d["nav_mode"],
                        tx,
                        ty,
                        tz,
                        round(lat, 7),
                        round(lon, 7),
                        round(alt_asl, 2),
                        ex,
                        ey,
                        ez,
                        d["position_drift_m"],
                        d["alt_agl"],
                        d["speed_ms"],
                        d["battery_pct"],
                        d["rssi_dbm"],
                        d["connected_via"],
                        obs_m if obs_m is not None else "",
                    ]
                )
        return buf.getvalue()

    def export_json(self) -> str:
        """Export structured JSON mission debrief with active WGS84 geodetic origin."""
        origin = get_active_origin()
        payload = {
            "platform": "Autel EVO Max 4T // A-Mesh Sim 4T Blackbox Debrief",
            "geodetic_origin": origin,
            "total_frames": len(self.frames),
            "duration_sec": self.frames[-1]["sim_time"] if self.frames else 0.0,
            "events": [e.to_dict() for e in self.events],
            "summary": self.get_summary(max_series_points=240),
        }
        return json.dumps(payload, indent=2)
