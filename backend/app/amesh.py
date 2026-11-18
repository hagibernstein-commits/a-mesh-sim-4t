"""Autel A-Mesh 1.0 RF Propagation, Knife-Edge Ridge Diffraction & Autonomous Relay Routing."""

from __future__ import annotations
import math
from typing import Dict, List, Any, Tuple
import numpy as np
from .specs import EVO_MAX_4T_SPECS
from .terrain import TacticalTerrain
from .drone import EvoMax4T


class AMeshEngine:
    """Computes RF link matrix, Free-Space Path Loss (FSPL), and autonomous 2-hop relay topology."""

    def __init__(self, terrain: TacticalTerrain) -> None:
        self.terrain = terrain
        self.topology_mode: str = "DIRECT_GCS_LOS"
        self.active_route: List[str] = ["GCS", "UAV-1"]

    def compute_link(
        self,
        source_id: str,
        target_id: str,
        p1: np.ndarray,
        p2: np.ndarray,
        jamming_zones: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        dist_m = max(1.0, float(np.linalg.norm(p2 - p1)))
        has_los, obstruction_m, worst_pt = self.terrain.check_los(p1, p2)

        # Free-Space Path Loss at 2.4 GHz
        fspl_db = 20.0 * math.log10(dist_m) + 20.0 * math.log10(EVO_MAX_4T_SPECS.amesh_freq_ghz * 1e9) - 147.55
        rssi_dbm = EVO_MAX_4T_SPECS.amesh_tx_power_dbm - fspl_db

        # Terrain knife-edge diffraction / ridge shadowing loss
        if not has_los:
            rssi_dbm -= min(58.0, 18.0 + obstruction_m * 0.95)

        # Check EW jamming attenuation along link
        jam_loss_db = 0.0
        for jz in jamming_zones:
            j_pos = np.array(jz["position"], dtype=float)
            j_rad = float(jz.get("radius_m", 110.0))
            mid = 0.5 * (p1 + p2)
            d_end = min(float(np.linalg.norm(p1 - j_pos)), float(np.linalg.norm(p2 - j_pos)), float(np.linalg.norm(mid - j_pos)))
            if d_end < j_rad:
                # A-Mesh 60GHz/2.4GHz frequency-hopping resists jamming better on short UAV-to-UAV links
                is_gcs_link = source_id == "GCS" or target_id == "GCS"
                jam_loss_db += (24.0 if is_gcs_link else 7.5) * (1.0 - d_end / j_rad)

        rssi_dbm -= jam_loss_db
        quality_pct = max(0.0, min(100.0, (rssi_dbm - (-95.0)) / 45.0 * 100.0))
        usable = has_los and rssi_dbm >= -84.0

        return {
            "id": f"{source_id}->{target_id}",
            "source": source_id,
            "target": target_id,
            "source_pos": [round(float(v), 2) for v in p1],
            "target_pos": [round(float(v), 2) for v in p2],
            "distance_m": round(dist_m, 1),
            "has_los": has_los,
            "obstruction_m": obstruction_m,
            "obstruction_point": worst_pt,
            "rssi_dbm": round(rssi_dbm, 1),
            "quality_pct": round(quality_pct, 1),
            "usable": usable,
            "jammed": jam_loss_db > 5.0,
            "active_relay_hop": False,
        }

    def update_mesh(
        self,
        drones: Dict[str, EvoMax4T],
        jamming_zones: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        gcs_pos = self.terrain.gcs_position
        u1 = drones["UAV-1"]
        u2 = drones["UAV-2"]
        u3 = drones["UAV-3"]

        l_gcs_u1 = self.compute_link("GCS", "UAV-1", gcs_pos, u1.true_position, jamming_zones)
        l_gcs_u2 = self.compute_link("GCS", "UAV-2", gcs_pos, u2.true_position, jamming_zones)
        l_gcs_u3 = self.compute_link("GCS", "UAV-3", gcs_pos, u3.true_position, jamming_zones)
        l_u2_u1 = self.compute_link("UAV-2", "UAV-1", u2.true_position, u1.true_position, jamming_zones)
        l_u2_u3 = self.compute_link("UAV-2", "UAV-3", u2.true_position, u3.true_position, jamming_zones)
        l_u3_u1 = self.compute_link("UAV-3", "UAV-1", u3.true_position, u1.true_position, jamming_zones)

        # Determine if UAV-1 (or UAV-3) is behind Diablo Ridge (x > -20m or direct GCS LOS blocked)
        u1_behind_ridge = (not l_gcs_u1["has_los"]) or (float(u1.true_position[0]) > -15.0)

        if u1_behind_ridge:
            # Position UAV-2 at optimal high-altitude relay apex over Diablo Ridge
            apex_x = -38.0
            apex_z = float(u1.true_position[2]) * 0.35
            ridge_h = self.terrain.get_elevation(apex_x, apex_z)
            apex_y = max(178.0, ridge_h + 44.0)
            u2.override_target = np.array([apex_x, apex_y, apex_z], dtype=float)

            self.topology_mode = "2_HOP_AMESH_ACTIVE"
            self.active_route = ["GCS", "UAV-2", "UAV-1"]
            l_gcs_u2["active_relay_hop"] = True
            l_u2_u1["active_relay_hop"] = True

            u2.connected_via = "GCS"
            u2.rssi_dbm = l_gcs_u2["rssi_dbm"]
            u2.link_quality_pct = max(54.0, l_gcs_u2["quality_pct"])

            u1.connected_via = "UAV-2"
            u1.rssi_dbm = l_u2_u1["rssi_dbm"]
            u1.link_quality_pct = max(72.0, l_u2_u1["quality_pct"])
        else:
            u2.override_target = None
            self.topology_mode = "DIRECT_GCS_LOS"
            self.active_route = ["GCS", "UAV-1"]
            l_gcs_u1["active_relay_hop"] = True

            u1.connected_via = "GCS"
            u1.rssi_dbm = l_gcs_u1["rssi_dbm"]
            u1.link_quality_pct = l_gcs_u1["quality_pct"]

            u2.connected_via = "GCS"
            u2.rssi_dbm = l_gcs_u2["rssi_dbm"]
            u2.link_quality_pct = l_gcs_u2["quality_pct"]

        if l_gcs_u3["usable"]:
            u3.connected_via = "GCS"
            u3.rssi_dbm = l_gcs_u3["rssi_dbm"]
            u3.link_quality_pct = l_gcs_u3["quality_pct"]
        else:
            l_u2_u3["active_relay_hop"] = True
            u3.connected_via = "UAV-2"
            u3.rssi_dbm = l_u2_u3["rssi_dbm"]
            u3.link_quality_pct = max(68.0, l_u2_u3["quality_pct"])

        links = [l_gcs_u1, l_gcs_u2, l_gcs_u3, l_u2_u1, l_u2_u3, l_u3_u1]
        summary = {
            "topology_mode": self.topology_mode,
            "active_route": self.active_route,
            "relay_bridged": self.topology_mode == "2_HOP_AMESH_ACTIVE",
            "uav1_direct_los": l_gcs_u1["has_los"],
        }
        return links, summary
