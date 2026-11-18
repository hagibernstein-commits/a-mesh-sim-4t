export interface GeodeticOrigin {
  lat: number;
  lon: number;
  alt_asl: number;
  origin_lat?: number;
  origin_lon?: number;
  origin_alt_asl?: number;
  gcs_lat?: number;
  gcs_lon?: number;
  gcs_alt_asl?: number;
  polygon_center_wgs84?: {
    lat: number;
    lon: number;
    alt_asl: number;
  };
}

export interface LrfReadout {
  valid: boolean;
  slant_range_m: number;
  target_id: string;
  target_label: string;
  target_temp_c: number;
  target_pos: [number, number, number];
  target_lat: number;
  target_lon: number;
  target_alt_asl: number;
  target_alt_local_m?: number;
}

export interface ObstacleContact {
  id: string;
  label: string;
  type: string;
  distance_m: number;
  wire_diameter_mm?: number;
  position: [number, number, number];
  detected_by: string;
}

export interface Perception720State {
  fisheye_status: string;
  mmwave_status: string;
  ambient_lux: number;
  closest_obstacle_m: number | null;
  apas_active: boolean;
  apas_status: string;
  avoidance_vector: [number, number, number];
  primary_threat: ObstacleContact | null;
  contacts: ObstacleContact[];
}

export interface DroneTelemetry {
  id: string;
  callsign: string;
  role: string;
  position: [number, number, number];
  true_position: [number, number, number];
  estimated_position: [number, number, number];
  position_drift_m: number;
  velocity: [number, number, number];
  speed_ms: number;
  heading_deg: number;
  pitch_deg: number;
  roll_deg: number;
  alt_agl: number;
  alt_msl: number;
  alt_asl: number;
  gps_lat: number;
  gps_lon: number;
  estimated_gps_lat: number;
  estimated_gps_lon: number;
  battery_pct: number;
  flight_mode: string;
  nav_mode: string;
  nav_state: string;
  gnss_jammed: boolean;
  in_jamming_zone: boolean;
  rssi_dbm: number;
  link_quality_pct: number;
  connected_via: string;
  sensor_mode: 'WIDE' | 'ZOOM' | 'THERMAL';
  thermal_palette: 'WHITE_HOT' | 'IRONBOW' | 'BLACK_HOT';
  zoom_level: number;
  fov_deg: number;
  gimbal_pitch_deg: number;
  gimbal_yaw_deg: number;
  lrf: LrfReadout;
  perception_720: Perception720State;
  sar_progress: {
    active: boolean;
    completed_wp: number;
    total_wp: number;
    pct: number;
  };
}

export interface RFLink {
  id: string;
  source: string;
  target: string;
  source_pos: [number, number, number];
  target_pos: [number, number, number];
  distance_m: number;
  has_los: boolean;
  obstruction_m: number;
  obstruction_point: [number, number, number];
  rssi_dbm: number;
  quality_pct: number;
  usable: boolean;
  jammed: boolean;
  active_relay_hop: boolean;
}

export interface ThermalEntityData {
  id: string;
  label: string;
  category: string;
  position: [number, number, number];
  temp_c: number;
  radius_m: number;
  height_m: number;
  lat: number;
  lon: number;
  alt_asl?: number;
}

export interface PinnedTarget {
  id: string;
  pinned_by: string;
  sim_time: number;
  target_id: string;
  label: string;
  temp_c: number;
  slant_range_m: number;
  position: [number, number, number];
  lat: number;
  lon: number;
  alt_asl: number;
}

export interface JammingZone {
  id: string;
  position: [number, number, number];
  radius_m: number;
  power_dbm: number;
}

export interface SarLeg {
  leg_index: number;
  direction: string;
  swath_width_m: number;
  start: [number, number, number];
  end: [number, number, number];
  points: [number, number, number][];
  length_m: number;
}

export interface SarPartition {
  uav_id: string;
  leg_indices: number[];
  legs: SarLeg[];
  waypoints: [number, number, number][];
  total_distance_m: number;
  role_status: string;
}

export interface SarMissionState {
  mission_id: string;
  executing: boolean;
  polygon_xz: [number, number][];
  polygon_wgs84?: { lat: number; lon: number }[];
  polygon_center_wgs84?: { lat: number; lon: number; alt_asl: number };
  gcs_wgs84?: { lat: number; lon: number; alt_asl: number };
  geodetic_origin?: GeodeticOrigin;
  altitude_agl_m: number;
  sensor_mode: string;
  sidelap_pct: number;
  sweep_angle_deg: number;
  area_m2: number;
  swath_width_m: number;
  lane_spacing_m: number;
  total_legs: number;
  total_waypoints: number;
  total_distance_m: number;
  estimated_time_s: number;
  legs: SarLeg[];
  partitions: Record<string, SarPartition>;
  relay_retasked: boolean;
  relay_retask_info: {
    relay_uav_id: string;
    unvisited_count: number;
    reassigned_counts: Record<string, number>;
  } | null;
  last_imported_filename?: string | null;
}

export interface SarDetection {
  id: string;
  entity_id: string;
  label: string;
  category: string;
  temp_c: number;
  detected_by: string;
  sim_time: number;
  position: [number, number, number];
  lat: number;
  lon: number;
  alt_asl: number;
}

export interface TelemetrySnapshot {
  sim_time: number;
  paused: boolean;
  ambient_lux: number;
  wind_speed_ms: number;
  wind_dir_deg: number;
  ew_jamming_active: boolean;
  geodetic_origin: GeodeticOrigin;
  gcs_position: [number, number, number];
  drones: DroneTelemetry[];
  links: RFLink[];
  mesh_summary: {
    topology_mode: string;
    active_route: string[];
    relay_bridged: boolean;
    uav1_direct_los: boolean;
  };
  thermal_entities: ThermalEntityData[];
  pinned_targets: PinnedTarget[];
  jamming_zones: JammingZone[];
  sar_mission: SarMissionState;
  sar_detections: SarDetection[];
  event_log: string[];
  blackbox_frames: number;
  replay_trails?: Record<string, { true: [number, number, number][]; estimated: [number, number, number][] }>;
}

export interface TerrainHeightmap {
  size_m: number;
  resolution: number;
  origin_lat: number;
  origin_lon: number;
  origin_alt_asl: number;
  geodetic_origin: GeodeticOrigin;
  gcs_position: [number, number, number];
  heights: number[][];
  buildings: {
    id: string;
    name: string;
    x: number;
    z: number;
    width: number;
    depth: number;
    height: number;
    base_elevation: number;
  }[];
  thermal_entities: ThermalEntityData[];
  pylons: {
    id: string;
    name: string;
    x: number;
    z: number;
    base_elevation: number;
    height: number;
    crossarm_width: number;
  }[];
  power_lines: {
    id: string;
    name: string;
    pylon_a_id: string;
    pylon_b_id: string;
    start_pos: [number, number, number];
    end_pos: [number, number, number];
    sag_m: number;
    wire_diameter_mm: number;
    voltage_kv: number;
    points: [number, number, number][];
  }[];
  cliff_outcrops: {
    id: string;
    name: string;
    x: number;
    z: number;
    radius: number;
    height: number;
    base_elevation: number;
  }[];
}
