"""Official Autel EVO Max 4T Airframe, Payload, Perception & A-Mesh RF Specifications."""

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, Any


@dataclass(frozen=True)
class EvoMax4TSpecs:
    """Hardware specification profile for the Autel Robotics EVO Max 4T."""

    model_name: str = "Autel EVO Max 4T"
    mass_kg: float = 1.62
    max_horizontal_speed_ms: float = 23.0
    max_ascent_speed_ms: float = 8.0
    max_descent_speed_ms: float = 6.0
    max_wind_resistance_ms: float = 12.0
    max_flight_time_min: float = 42.0
    max_service_ceiling_m: float = 7000.0

    # Gimbal & Fusion 4T Payload
    wide_fov_deg: float = 85.0
    wide_equivalent_focal_mm: float = 23.0
    thermal_fov_deg: float = 42.0
    thermal_resolution: str = "640x512 @ 30fps"
    thermal_focal_mm: float = 13.0
    zoom_optical_max: float = 10.0
    zoom_hybrid_max: float = 160.0
    lrf_max_range_m: float = 1200.0
    lrf_min_range_m: float = 5.0
    lrf_accuracy_m: float = 1.0
    gimbal_pitch_min_deg: float = -90.0
    gimbal_pitch_max_deg: float = 30.0

    # 720° Omnidirectional Perception (Binocular Fisheye + 60GHz/24GHz mmWave Radar)
    fisheye_range_m: float = 40.0
    fisheye_min_lux: float = 15.0
    mmwave_range_m: float = 50.0
    mmwave_min_wire_diameter_mm: float = 12.7
    apas_safety_margin_m: float = 12.0

    # Navigation & Drift Regimes (RTK / V-SLAM / IMU)
    rtk_horizontal_accuracy_m: float = 0.03
    vslam_drift_rate_ms: float = 0.08
    imu_drift_rate_ms: float = 1.45

    # A-Mesh 1.0 Dual-Band RF Networking
    amesh_tx_power_dbm: float = 26.0
    amesh_freq_ghz: float = 2.4
    amesh_max_range_km: float = 20.0
    amesh_sensitivity_dbm: float = -96.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


EVO_MAX_4T_SPECS = EvoMax4TSpecs()
