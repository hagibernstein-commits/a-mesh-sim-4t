"""Autel EVO Max 4T Flight Controller, 720° Obstacle Avoidance, Gimbal Payload & Navigation Drift."""

from __future__ import annotations
import math
from typing import Dict, List, Any, Optional
import numpy as np
from .specs import EVO_MAX_4T_SPECS
from .terrain import TacticalTerrain


class EvoMax4T:
    """Simulated Autel EVO Max 4T UAV with RTK/V-SLAM/IMU navigation and 4T Fusion Gimbal."""

    def __init__(
        self,
        drone_id: str,
        callsign: str,
        role: str,
        initial_pos: List[float],
        waypoints: List[List[float]],
    ) -> None:
        self.id = drone_id
        self.callsign = callsign
        self.role = role
        self.position = np.array(initial_pos, dtype=float)
        self.true_position = np.array(initial_pos, dtype=float)
        self.estimated_position = np.array(initial_pos, dtype=float)
        self.drift_offset = np.zeros(3, dtype=float)
        self.position_drift_m: float = 0.03

        self.velocity = np.zeros(3, dtype=float)
        self.heading_deg: float = 0.0
        self.pitch_deg: float = 0.0
        self.roll_deg: float = 0.0
        self.battery_pct: float = 100.0

        self.waypoints: List[np.ndarray] = [np.array(wp, dtype=float) for wp in waypoints]
        self.current_wp_idx: int = 0
        self.loop_waypoints: bool = True

        # Autonomous Relay / SAR Override Target
        self.override_target: Optional[np.ndarray] = None
        self.sar_waypoints: List[np.ndarray] = []
        self.sar_wp_idx: int = 0
        self.sar_active: bool = False
        self.sar_completed_count: int = 0
        self.sar_total_count: int = 0

        # Navigation & Perception state
        self.flight_mode: str = "MISSION_PATROL"
        self.nav_mode: str = "RTK-FIXED"
        self.nav_state: str = "RTK_GNSS_NOMINAL"
        self.in_jamming_zone: bool = False
        self.gnss_jammed: bool = False
        self.ambient_lux: float = 650.0
        self.perception_state: Dict[str, Any] = {}

        # Gimbal & Sensor Payload
        self.sensor_mode: str = "THERMAL"  # WIDE | ZOOM | THERMAL
        self.thermal_palette: str = "IRONBOW"  # WHITE_HOT | IRONBOW | BLACK_HOT
        self.zoom_level: float = 1.0
        self.gimbal_pitch_deg: float = -28.0
        self.gimbal_yaw_deg: float = 0.0
        self.gimbal_tracking_target: Optional[np.ndarray] = None

        # A-Mesh Link Metrics
        self.rssi_dbm: float = -52.0
        self.link_quality_pct: float = 98.0
        self.connected_via: str = "GCS"
        self.lrf_readout: Dict[str, Any] = {}

    def set_gimbal(
        self,
        pitch_deg: Optional[float] = None,
        yaw_deg: Optional[float] = None,
        sensor_mode: Optional[str] = None,
        thermal_palette: Optional[str] = None,
        zoom_level: Optional[float] = None,
    ) -> None:
        if pitch_deg is not None:
            self.gimbal_pitch_deg = float(
                max(EVO_MAX_4T_SPECS.gimbal_pitch_min_deg, min(EVO_MAX_4T_SPECS.gimbal_pitch_max_deg, pitch_deg))
            )
            self.gimbal_tracking_target = None
        if yaw_deg is not None:
            self.gimbal_yaw_deg = float(((yaw_deg + 180.0) % 360.0) - 180.0)
            self.gimbal_tracking_target = None
        if sensor_mode is not None and sensor_mode in ("WIDE", "ZOOM", "THERMAL"):
            self.sensor_mode = sensor_mode
        if thermal_palette is not None and thermal_palette in ("WHITE_HOT", "IRONBOW", "BLACK_HOT"):
            self.thermal_palette = thermal_palette
        if zoom_level is not None:
            self.zoom_level = float(max(1.0, min(EVO_MAX_4T_SPECS.zoom_hybrid_max, zoom_level)))

    def slew_gimbal_to_point(self, target_pos: np.ndarray) -> None:
        self.gimbal_tracking_target = np.array(target_pos, dtype=float)
        self._update_gimbal_tracking()

    def _update_gimbal_tracking(self) -> None:
        if self.gimbal_tracking_target is None:
            return
        diff = self.gimbal_tracking_target - self.position
        horiz = math.hypot(float(diff[0]), float(diff[2]))
        if horiz > 1e-3 or abs(float(diff[1])) > 1e-3:
            pitch = math.degrees(math.atan2(float(diff[1]), max(horiz, 1e-3)))
            yaw = math.degrees(math.atan2(float(diff[2]), float(diff[0])))
            self.gimbal_pitch_deg = max(
                EVO_MAX_4T_SPECS.gimbal_pitch_min_deg,
                min(EVO_MAX_4T_SPECS.gimbal_pitch_max_deg, pitch),
            )
            self.gimbal_yaw_deg = ((yaw + 180.0) % 360.0) - 180.0

    def assign_sar_waypoints(self, waypoints: List[List[float]]) -> None:
        self.sar_waypoints = [np.array(wp, dtype=float) for wp in waypoints]
        self.sar_wp_idx = 0
        self.sar_completed_count = 0
        self.sar_total_count = len(self.sar_waypoints)
        self.sar_active = len(self.sar_waypoints) > 0
        if self.sar_active:
            self.flight_mode = "SAR_SWEEP_NADIR"
            self.sensor_mode = "THERMAL"
            self.gimbal_pitch_deg = -90.0
            self.gimbal_tracking_target = None

    def clear_sar_waypoints(self) -> None:
        self.sar_waypoints = []
        self.sar_wp_idx = 0
        self.sar_completed_count = 0
        self.sar_total_count = 0
        self.sar_active = False
        if self.override_target is None:
            self.flight_mode = "MISSION_PATROL"
            self.gimbal_pitch_deg = -28.0

    def get_remaining_sar_waypoints(self) -> List[List[float]]:
        if not self.sar_active or self.sar_wp_idx >= len(self.sar_waypoints):
            return []
        return [[float(wp[0]), float(wp[1]), float(wp[2])] for wp in self.sar_waypoints[self.sar_wp_idx :]]

    def update_perception_and_navigation(
        self,
        dt: float,
        terrain: TacticalTerrain,
        ambient_lux: float,
        in_jamming_zone: bool,
        sim_time: float,
    ) -> None:
        self.ambient_lux = ambient_lux
        self.in_jamming_zone = in_jamming_zone
        self.gnss_jammed = in_jamming_zone

        self.perception_state = terrain.scan_720_obstacles(self.true_position, ambient_lux)
        fisheye_ok = ambient_lux >= EVO_MAX_4T_SPECS.fisheye_min_lux

        if not in_jamming_zone:
            self.nav_mode = "RTK-FIXED"
            self.nav_state = "RTK_GNSS_NOMINAL"
            # Decay any accumulated drift rapidly via A-Mesh UWB + RTK fix
            self.drift_offset *= max(0.0, 1.0 - 4.5 * dt)
            jitter = 0.03 + 0.01 * math.sin(sim_time * 3.1 + hash(self.id) % 7)
            self.position_drift_m = round(float(np.linalg.norm(self.drift_offset)) + jitter, 2)
        elif fisheye_ok:
            self.nav_mode = "V-SLAM"
            self.nav_state = "GNSS_DENIED_VSLAM"
            drift_step = EVO_MAX_4T_SPECS.vslam_drift_rate_ms * dt
            ang = sim_time * 0.7 + (hash(self.id) % 13)
            self.drift_offset += np.array([math.cos(ang) * drift_step, 0.02 * drift_step, math.sin(ang) * drift_step])
            if np.linalg.norm(self.drift_offset) > 1.8:
                self.drift_offset = self.drift_offset / np.linalg.norm(self.drift_offset) * 1.8
            self.position_drift_m = round(float(np.linalg.norm(self.drift_offset)) + 0.15, 2)
        else:
            self.nav_mode = "IMU-DRIFT"
            self.nav_state = "VSLAM_DEGRADED_IMU_ONLY"
            drift_step = EVO_MAX_4T_SPECS.imu_drift_rate_ms * dt
            ang = sim_time * 0.45 + (hash(self.id) % 19)
            self.drift_offset += np.array(
                [math.cos(ang) * drift_step, 0.15 * math.sin(sim_time) * drift_step, math.sin(ang) * drift_step]
            )
            if np.linalg.norm(self.drift_offset) > 18.5:
                self.drift_offset = self.drift_offset / np.linalg.norm(self.drift_offset) * 18.5
            self.position_drift_m = round(float(np.linalg.norm(self.drift_offset)) + 0.45, 2)

        self.estimated_position = self.true_position + self.drift_offset

    def step(
        self,
        dt: float,
        terrain: TacticalTerrain,
        wind_vec: np.ndarray,
        ambient_lux: float = 650.0,
        in_jamming_zone: bool = False,
        sim_time: float = 0.0,
    ) -> None:
        # Determine active target waypoint
        target: Optional[np.ndarray] = None
        desired_speed = 18.5

        if self.override_target is not None:
            target = self.override_target
            desired_speed = 21.0
            if self.sar_active:
                self.flight_mode = "AMESH_RELAY (SAR RETASKED)"
            elif self.in_jamming_zone:
                self.flight_mode = "GNSS_DENIED_MESH_HEAL"
            else:
                self.flight_mode = "AMESH_RELAY_BRIDGE"
        elif self.sar_active and self.sar_wp_idx < len(self.sar_waypoints):
            target = self.sar_waypoints[self.sar_wp_idx]
            desired_speed = 20.5
            self.flight_mode = "SAR_SWEEP_NADIR"
            self.gimbal_pitch_deg = -90.0
        elif self.waypoints:
            target = self.waypoints[self.current_wp_idx]
            if self.in_jamming_zone:
                self.flight_mode = "GNSS_DENIED_VIO_SLAM"
            else:
                self.flight_mode = "MISSION_PATROL"

        if target is not None:
            to_target = target - self.true_position
            dist = float(np.linalg.norm(to_target))
            if dist < 4.5:
                if self.override_target is not None:
                    self.velocity *= 0.6
                elif self.sar_active:
                    self.sar_wp_idx += 1
                    self.sar_completed_count = self.sar_wp_idx
                    if self.sar_wp_idx >= len(self.sar_waypoints):
                        self.sar_active = False
                        self.flight_mode = "SAR_SWEEP_COMPLETE"
                elif self.waypoints:
                    self.current_wp_idx = (self.current_wp_idx + 1) % len(self.waypoints)
            else:
                dir_vec = to_target / max(dist, 1e-6)
                speed = min(desired_speed, max(4.0, dist * 1.35))
                cmd_vel = dir_vec * speed

                # Apply APAS 3D obstacle avoidance vector from 720° sensor fusion
                avoid_list = self.perception_state.get("avoidance_vector", [0.0, 0.0, 0.0])
                avoid_vec = np.array(avoid_list, dtype=float)
                if float(np.linalg.norm(avoid_vec)) > 0.1:
                    cmd_vel += avoid_vec

                # Wind aerodynamic drag compensation (EVO Max 4T resists up to 12 m/s)
                wind_mag = float(np.linalg.norm(wind_vec))
                if wind_mag > EVO_MAX_4T_SPECS.max_wind_resistance_ms:
                    cmd_vel += (wind_vec / wind_mag) * (wind_mag - EVO_MAX_4T_SPECS.max_wind_resistance_ms) * 0.4

                # Clamp horizontal & vertical speeds to EVO Max 4T envelope
                horiz_speed = math.hypot(float(cmd_vel[0]), float(cmd_vel[2]))
                if horiz_speed > EVO_MAX_4T_SPECS.max_horizontal_speed_ms:
                    scale = EVO_MAX_4T_SPECS.max_horizontal_speed_ms / horiz_speed
                    cmd_vel[0] *= scale
                    cmd_vel[2] *= scale
                cmd_vel[1] = max(
                    -EVO_MAX_4T_SPECS.max_descent_speed_ms,
                    min(EVO_MAX_4T_SPECS.max_ascent_speed_ms, float(cmd_vel[1])),
                )

                self.velocity = 0.72 * self.velocity + 0.28 * cmd_vel

        self.true_position = self.true_position + self.velocity * dt

        # Terrain minimum safe AGL floor
        ground_y = terrain.get_elevation(float(self.true_position[0]), float(self.true_position[2]))
        min_safe_y = ground_y + 12.0
        if float(self.true_position[1]) < min_safe_y:
            self.true_position[1] = min_safe_y
            if self.velocity[1] < 0:
                self.velocity[1] = 0.0

        self.position = self.true_position.copy()

        # Update perception & navigation drift
        self.update_perception_and_navigation(dt, terrain, ambient_lux, in_jamming_zone, sim_time)

        # Heading & attitude
        horiz_v = math.hypot(float(self.velocity[0]), float(self.velocity[2]))
        if horiz_v > 0.4:
            self.heading_deg = (math.degrees(math.atan2(float(self.velocity[2]), float(self.velocity[0]))) + 360.0) % 360.0
        self.pitch_deg = round(-min(18.0, horiz_v * 0.65), 1)
        self.roll_deg = round(math.sin(sim_time * 1.5) * 2.2, 1)

        # Battery discharge model (42-min nominal flight endurance)
        speed_factor = 1.0 + (float(np.linalg.norm(self.velocity)) / EVO_MAX_4T_SPECS.max_horizontal_speed_ms) * 0.35
        discharge_per_sec = (100.0 / (EVO_MAX_4T_SPECS.max_flight_time_min * 60.0)) * speed_factor
        self.battery_pct = max(5.0, self.battery_pct - discharge_per_sec * dt)

        # Update gimbal tracking & 1200m Laser Rangefinder readout
        self._update_gimbal_tracking()
        abs_yaw = self.heading_deg + self.gimbal_yaw_deg
        self.lrf_readout = terrain.raycast_lrf(self.true_position, self.gimbal_pitch_deg, abs_yaw)

    def to_telemetry(self, terrain: TacticalTerrain) -> Dict[str, Any]:
        x, y, z = float(self.true_position[0]), float(self.true_position[1]), float(self.true_position[2])
        ground_y = terrain.get_elevation(x, z)
        alt_agl = max(0.0, y - ground_y)
        alt_asl = terrain.origin_alt_asl + y
        lat, lon = terrain.local_to_wgs84(x, z)
        est_lat, est_lon = terrain.local_to_wgs84(float(self.estimated_position[0]), float(self.estimated_position[2]))
        speed_ms = float(np.linalg.norm(self.velocity))

        # Refresh LRF readout against current terrain origin so live datum updates apply immediately
        abs_yaw = self.heading_deg + self.gimbal_yaw_deg
        self.lrf_readout = terrain.raycast_lrf(self.true_position, self.gimbal_pitch_deg, abs_yaw)

        fov_deg = (
            EVO_MAX_4T_SPECS.thermal_fov_deg
            if self.sensor_mode == "THERMAL"
            else round(EVO_MAX_4T_SPECS.wide_fov_deg / max(1.0, min(self.zoom_level, 10.0)), 1)
        )

        return {
            "id": self.id,
            "callsign": self.callsign,
            "role": self.role,
            "position": [round(x, 2), round(y, 2), round(z, 2)],
            "true_position": [round(x, 2), round(y, 2), round(z, 2)],
            "estimated_position": [
                round(float(self.estimated_position[0]), 2),
                round(float(self.estimated_position[1]), 2),
                round(float(self.estimated_position[2]), 2),
            ],
            "position_drift_m": round(self.position_drift_m, 2),
            "velocity": [round(float(v), 2) for v in self.velocity],
            "speed_ms": round(speed_ms, 1),
            "heading_deg": round(self.heading_deg, 1),
            "pitch_deg": self.pitch_deg,
            "roll_deg": self.roll_deg,
            "alt_agl": round(alt_agl, 1),
            "alt_msl": round(alt_asl, 1),
            "alt_asl": round(alt_asl, 1),
            "gps_lat": round(lat, 6),
            "gps_lon": round(lon, 6),
            "estimated_gps_lat": round(est_lat, 6),
            "estimated_gps_lon": round(est_lon, 6),
            "battery_pct": round(self.battery_pct, 1),
            "flight_mode": self.flight_mode,
            "nav_mode": self.nav_mode,
            "nav_state": self.nav_state,
            "gnss_jammed": self.gnss_jammed,
            "in_jamming_zone": self.in_jamming_zone,
            "rssi_dbm": round(self.rssi_dbm, 1),
            "link_quality_pct": round(self.link_quality_pct, 1),
            "connected_via": self.connected_via,
            "sensor_mode": self.sensor_mode,
            "thermal_palette": self.thermal_palette,
            "zoom_level": self.zoom_level,
            "fov_deg": fov_deg,
            "gimbal_pitch_deg": round(self.gimbal_pitch_deg, 1),
            "gimbal_yaw_deg": round(self.gimbal_yaw_deg, 1),
            "lrf": self.lrf_readout,
            "perception_720": self.perception_state,
            "sar_progress": {
                "active": self.sar_active,
                "completed_wp": self.sar_completed_count,
                "total_wp": self.sar_total_count,
                "pct": round(
                    (self.sar_completed_count / self.sar_total_count * 100.0) if self.sar_total_count > 0 else 0.0,
                    1,
                ),
            },
        }
