import React, { useState, useEffect } from 'react';
import {
  Radio,
  Compass,
  Eye,
  EyeOff,
  Grid,
  Pause,
  Play,
  RotateCcw,
  Sun,
  Wind,
  Zap,
  ShieldAlert,
  Flame,
  Crosshair,
  Sliders,
} from 'lucide-react';
import {
  DroneTelemetry,
  GeodeticOrigin,
  RFLink,
  SarDetection,
  SarMissionState,
  ThermalEntityData,
} from '../types/telemetry';
import { MissionPlannerPanel } from './MissionPlannerPanel';
import { GimbalPiPViewport } from './GimbalPiPViewport';

interface SmartControllerHUDProps {
  simTime: number;
  paused: boolean;
  ambientLux: number;
  windSpeedMs: number;
  ewJammingActive: boolean;
  geodeticOrigin: GeodeticOrigin | null;
  gcsPosition: [number, number, number];
  drones: DroneTelemetry[];
  links: RFLink[];
  meshSummary: {
    topology_mode: string;
    active_route: string[];
    relay_bridged: boolean;
    uav1_direct_los: boolean;
  };
  thermalEntities: ThermalEntityData[];
  sarMission: SarMissionState | null;
  sarDetections: SarDetection[];
  eventLog: string[];
  selectedDroneId: string;
  missionPlannerOpen: boolean;
  show720Bubble: boolean;
  showFovCones: boolean;
  showGrid: boolean;
  cameraPreset: 'OVERVIEW' | 'RIDGE_PROFILE' | 'UAV-1' | 'UAV-2' | 'UAV-3';
  draftPolygon: [number, number][];
  polygonLocked: boolean;
  onSelectDrone: (id: string) => void;
  onToggleMissionPlanner: () => void;
  onToggle720Bubble: () => void;
  onToggleFovCones: () => void;
  onToggleGrid: () => void;
  onSelectCameraPreset: (
    p: 'OVERVIEW' | 'RIDGE_PROFILE' | 'UAV-1' | 'UAV-2' | 'UAV-3'
  ) => void;
  onControlAction: (body: any) => void;
  onGimbalChange: (params: any) => void;
  onPinTarget: (droneId: string) => void;
  onUpdateDraftPolygon: (pts: [number, number][], locked: boolean) => void;
  onMissionUpdated: (mission: SarMissionState) => void;
  onOriginUpdated: (origin: GeodeticOrigin) => void;
}

export const SmartControllerHUD: React.FC<SmartControllerHUDProps> = ({
  simTime,
  paused,
  ambientLux,
  windSpeedMs,
  ewJammingActive,
  geodeticOrigin,
  gcsPosition,
  drones,
  links,
  meshSummary,
  thermalEntities,
  sarMission,
  sarDetections,
  eventLog,
  selectedDroneId,
  missionPlannerOpen,
  show720Bubble,
  showFovCones,
  showGrid,
  cameraPreset,
  draftPolygon,
  polygonLocked,
  onSelectDrone,
  onToggleMissionPlanner,
  onToggle720Bubble,
  onToggleFovCones,
  onToggleGrid,
  onSelectCameraPreset,
  onControlAction,
  onGimbalChange,
  onPinTarget,
  onUpdateDraftPolygon,
  onMissionUpdated,
  onOriginUpdated,
}) => {
  const [isMobile, setIsMobile] = useState<boolean>(() =>
    typeof window !== 'undefined' ? window.innerWidth < 768 : false
  );
  const [mobileHudVisible, setMobileHudVisible] = useState<boolean>(true);
  const [mobileTab, setMobileTab] = useState<'SWARM' | 'GIMBAL' | 'ENV'>('SWARM');

  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth < 768);
    };
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const selectedDrone = drones.find((d) => d.id === selectedDroneId) || drones[0];
  const latestSarDetection =
    sarDetections.length > 0 ? sarDetections[sarDetections.length - 1] : null;

  return (
    <div className="pointer-events-none absolute inset-0 flex flex-col justify-between p-2 md:p-3 select-none overflow-hidden">
      {/* Top Tactical Header Bar */}
      <div className="flex flex-col gap-1.5 md:gap-2 w-full max-w-full">
        <div
          id="hud-top-bar"
          className="pointer-events-auto flex items-center justify-between gap-1.5 md:gap-2 rounded-xl bg-slate-950/90 border border-slate-800 px-2.5 md:px-3.5 py-1.5 md:py-2 backdrop-blur-md w-full max-w-full overflow-hidden"
        >
          {/* Left Branding / Badge */}
          <div className="flex items-center gap-2 md:gap-3 min-w-0 shrink-0">
            <div className="px-2 md:px-2.5 py-1 rounded bg-amber-500/15 border border-amber-500/50 text-amber-300 text-[10px] font-bold tracking-wider whitespace-nowrap">
              <span className="md:hidden">• AUTEL V3</span>
              <span className="hidden md:inline">• AUTEL SMART CONTROLLER V3</span>
            </div>
            <div className="hidden md:block">
              <div className="text-xs font-bold tracking-wider text-slate-100">
                A-MESH SIM 4T // 720° RADAR + V-SLAM SWARM
              </div>
              <div className="text-[10px] text-slate-400">
                Fisheye 40m (≥15 lx) • 60GHz/24GHz mmWave 50m (15mm wire) • RTK / V-SLAM / IMU
              </div>
            </div>
          </div>

          {/* Center / Action Buttons */}
          <div className="flex items-center gap-1.5 md:gap-2 shrink-0">
            <button
              id="btn-mission-planner-toggle"
              type="button"
              onClick={onToggleMissionPlanner}
              className={`px-2 md:px-3 py-1 md:py-1.5 rounded-lg text-[11px] md:text-xs font-bold border flex items-center gap-1 md:gap-1.5 cursor-pointer whitespace-nowrap ${
                missionPlannerOpen
                  ? 'bg-cyan-500/20 border-cyan-400 text-cyan-200'
                  : 'bg-slate-900 border-slate-700 text-slate-300'
              }`}
            >
              <Compass className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
              <span className="md:hidden">Planner</span>
              <span className="hidden md:inline">Mission Planner</span>
            </button>

            <button
              id="btn-toggle-720-bubble"
              type="button"
              onClick={onToggle720Bubble}
              className={`px-2 md:px-2.5 py-1 md:py-1.5 rounded-lg text-[11px] md:text-xs font-bold border cursor-pointer whitespace-nowrap ${
                show720Bubble
                  ? 'bg-amber-500/20 border-amber-400 text-amber-300'
                  : 'bg-slate-900 border-slate-700 text-slate-400'
              }`}
            >
              <span className="md:hidden">720°</span>
              <span className="hidden md:inline">720° Bubble</span>
            </button>

            {/* Mobile HUD Show/Hide Toggle Button */}
            <button
              id="btn-mobile-hud-toggle"
              type="button"
              onClick={() => setMobileHudVisible((v) => !v)}
              className={`md:hidden px-2 py-1 rounded-lg text-[11px] font-bold border flex items-center gap-1 cursor-pointer whitespace-nowrap ${
                mobileHudVisible
                  ? 'bg-cyan-500/20 border-cyan-400 text-cyan-200'
                  : 'bg-slate-900 border-slate-700 text-slate-400'
              }`}
            >
              {mobileHudVisible ? (
                <Eye className="w-3.5 h-3.5 text-cyan-300" />
              ) : (
                <EyeOff className="w-3.5 h-3.5 text-slate-400" />
              )}
              <span>HUD</span>
            </button>

            {/* Desktop-only quick toggles */}
            <button
              type="button"
              onClick={onToggleFovCones}
              className={`hidden md:flex px-2.5 py-1.5 rounded-lg text-xs border items-center gap-1 cursor-pointer ${
                showFovCones
                  ? 'bg-cyan-500/20 border-cyan-400 text-cyan-300'
                  : 'bg-slate-900 border-slate-700 text-slate-400'
              }`}
            >
              <Eye className="w-3.5 h-3.5" />
              <span>FOV</span>
            </button>

            <button
              type="button"
              onClick={onToggleGrid}
              className={`hidden md:flex px-2.5 py-1.5 rounded-lg text-xs border items-center gap-1 cursor-pointer ${
                showGrid
                  ? 'bg-cyan-500/20 border-cyan-400 text-cyan-300'
                  : 'bg-slate-900 border-slate-700 text-slate-400'
              }`}
            >
              <Grid className="w-3.5 h-3.5" />
              <span>Grid</span>
            </button>

            <div className="hidden md:block px-2.5 py-1 rounded bg-slate-900 border border-slate-800 text-xs font-mono text-slate-200">
              T+{simTime.toFixed(1)}s
            </div>
            <div className="hidden md:block px-2 py-1 rounded bg-emerald-950/80 border border-emerald-500/50 text-[10px] font-bold text-emerald-300">
              20Hz
            </div>
          </div>

          {/* Right A-Mesh Route Status (Desktop) */}
          <div className="hidden md:flex items-center gap-2 shrink-0">
            <div className="px-3 py-1 rounded-lg bg-slate-900 border border-cyan-500/40 flex items-center gap-2 text-xs">
              <Radio className="w-3.5 h-3.5 text-cyan-400" />
              <span className="text-slate-300 font-semibold">
                A-MESH ROUTE: {meshSummary.active_route.join(' ↔ ')}
              </span>
              <span
                className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                  meshSummary.relay_bridged
                    ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-400/50'
                    : 'bg-emerald-500/20 text-emerald-300 border border-emerald-400/50'
                }`}
              >
                {meshSummary.relay_bridged ? '2-HOP RELAY BRIDGED' : 'DIRECT LOS'}
              </span>
            </div>
          </div>
        </div>

        {/* Camera Preset Bar — Horizontally Scrollable on Mobile */}
        <div
          id="camera-switcher-strip"
          className="pointer-events-auto self-center w-full md:w-auto max-w-full overflow-x-auto whitespace-nowrap no-scrollbar flex items-center gap-1.5 rounded-lg bg-slate-950/85 border border-slate-800 px-2.5 py-1"
        >
          <span className="text-[10px] text-slate-400 font-semibold mr-0.5 shrink-0">
            CAM:
          </span>
          {(
            [
              ['OVERVIEW', 'Sector Overview', 'Sector Overview'],
              ['RIDGE_PROFILE', 'Ridge LOS Profile', 'Ridge LOS'],
              ['UAV-1', 'Track UAV-1 (Scout)', 'UAV-1'],
              ['UAV-2', 'Track UAV-2 (Relay)', 'UAV-2'],
              ['UAV-3', 'Track UAV-3 (Overwatch)', 'UAV-3'],
            ] as const
          ).map(([key, desktopLabel, mobileLabel]) => (
            <button
              key={key}
              type="button"
              onClick={() => onSelectCameraPreset(key)}
              className={`px-2.5 py-0.5 rounded text-[11px] font-semibold cursor-pointer shrink-0 ${
                cameraPreset === key
                  ? 'bg-cyan-500/20 border border-cyan-400 text-cyan-300'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <span className="md:hidden">{mobileLabel}</span>
              <span className="hidden md:inline">{desktopLabel}</span>
            </button>
          ))}
        </div>

        {/* Pulsing SAR Heat Contact Alert Banner */}
        {latestSarDetection && (
          <div
            id="sar-heat-alert-banner"
            className="pointer-events-auto self-center max-w-full rounded-xl bg-amber-950/90 border border-amber-400 px-3 md:px-4 py-1 md:py-1.5 text-[10px] md:text-xs font-bold text-amber-200 flex items-center gap-2 shadow-lg truncate"
          >
            <Flame className="w-4 h-4 text-amber-400 shrink-0" />
            <span className="truncate">
              SAR HEAT CONTACT [{latestSarDetection.id}] •{' '}
              {latestSarDetection.entity_id} {latestSarDetection.label} (
              {latestSarDetection.temp_c.toFixed(1)}°C) captured by{' '}
              {latestSarDetection.detected_by} (-90° nadir) @{' '}
              {latestSarDetection.lat.toFixed(5)}°N,{' '}
              {latestSarDetection.lon.toFixed(5)}°E • Total Contacts:{' '}
              {sarDetections.length}
            </span>
          </div>
        )}
      </div>

      {/* =====================================================================
          DESKTOP MIDDLE OVERLAY COLUMNS & BOTTOM BAR (>= 768px)
         ===================================================================== */}
      {!isMobile && (
        <>
          <div className="hidden md:flex flex-1 items-start justify-between gap-3 my-2 overflow-hidden">
            {/* Left Column: 3 UAV Telemetry Cards + 720° Perception Card */}
            <div className="pointer-events-auto flex flex-col gap-2 w-[285px]">
              {drones.map((d) => {
                const isSelected = d.id === selectedDrone?.id;
                return (
                  <div
                    key={d.id}
                    onClick={() => onSelectDrone(d.id)}
                    className={`rounded-xl bg-slate-950/90 border p-2.5 flex flex-col gap-1.5 text-xs cursor-pointer transition ${
                      isSelected
                        ? 'border-cyan-400/70 shadow-lg'
                        : 'border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5 font-bold">
                        <span
                          className={`w-2 h-2 rounded-full ${
                            d.id === 'UAV-1'
                              ? 'bg-emerald-400'
                              : d.id === 'UAV-2'
                              ? 'bg-cyan-400'
                              : 'bg-purple-400'
                          }`}
                        />
                        <span>{d.id}</span>
                        <span className="text-[10px] text-slate-400 font-normal">
                          {d.role}
                        </span>
                      </div>
                      <div className="flex items-center gap-1">
                        <span
                          className={`px-1.5 py-0.5 rounded text-[9px] font-bold border ${
                            d.nav_mode === 'RTK-FIXED'
                              ? 'bg-emerald-950/80 border-emerald-500/50 text-emerald-300'
                              : d.nav_mode === 'V-SLAM'
                              ? 'bg-cyan-950/80 border-cyan-500/50 text-cyan-300'
                              : 'bg-rose-950/80 border-rose-500/50 text-rose-300'
                          }`}
                        >
                          {d.nav_mode}
                        </span>
                        <span className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-700 text-[9px] text-cyan-300">
                          A-MESH → {d.connected_via}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between text-[10px] text-slate-400">
                      <span className="truncate max-w-[150px]">{d.flight_mode}</span>
                      <span className="font-mono text-emerald-300">
                        {d.rssi_dbm.toFixed(1)} dBm ({d.link_quality_pct.toFixed(0)}%)
                      </span>
                    </div>

                    <div className="grid grid-cols-4 gap-1 pt-1 border-t border-slate-800/80 text-[10px]">
                      <div>
                        <div className="text-[8px] text-slate-400">BATTERY</div>
                        <div className="font-bold text-emerald-300">
                          {d.battery_pct.toFixed(1)}%
                        </div>
                      </div>
                      <div>
                        <div className="text-[8px] text-slate-400">ALT AGL</div>
                        <div className="font-bold text-slate-100">
                          {d.alt_agl.toFixed(0)}m
                        </div>
                      </div>
                      <div>
                        <div className="text-[8px] text-slate-400">GND SPD</div>
                        <div className="font-bold text-cyan-300">
                          {d.speed_ms.toFixed(1)}m/s
                        </div>
                      </div>
                      <div>
                        <div className="text-[8px] text-slate-400">GIMBAL</div>
                        <div className="font-bold text-amber-300">
                          {d.gimbal_pitch_deg.toFixed(0)}°/{d.gimbal_yaw_deg.toFixed(0)}°
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center justify-between text-[9px] font-mono text-slate-400 pt-0.5">
                      <span>
                        WGS84: {d.gps_lat.toFixed(5)}°N, {d.gps_lon.toFixed(5)}°E
                      </span>
                      <span>{d.alt_asl.toFixed(1)}m ASL</span>
                    </div>
                  </div>
                );
              })}

              {/* 720° Fusion & V-SLAM Card */}
              {selectedDrone && (
                <div className="rounded-xl bg-slate-950/90 border border-slate-800 p-2.5 flex flex-col gap-1.5 text-xs">
                  <div className="flex items-center justify-between font-bold text-cyan-300 text-[11px]">
                    <span>{selectedDrone.id} // 720° FUSION & V-SLAM</span>
                    <span className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-700 text-[9px] text-slate-300">
                      FISHEYE+RADAR
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-1.5 text-[10px]">
                    <div className="rounded bg-slate-900/80 border border-slate-800 p-1.5">
                      <div className="text-[9px] text-slate-400">
                        BINOCULAR FISHEYE (40m)
                      </div>
                      <div
                        className={`font-bold ${
                          selectedDrone.perception_720?.fisheye_status === 'ACTIVE'
                            ? 'text-emerald-300'
                            : 'text-rose-400'
                        }`}
                      >
                        {selectedDrone.perception_720?.fisheye_status || 'ACTIVE'} (
                        {ambientLux.toFixed(0)} lx)
                      </div>
                    </div>
                    <div className="rounded bg-slate-900/80 border border-slate-800 p-1.5">
                      <div className="text-[9px] text-slate-400">
                        60GHz/24GHz mmWAVE (50m)
                      </div>
                      <div className="font-bold text-cyan-300">
                        {selectedDrone.perception_720?.mmwave_status ||
                          'ACTIVE (≥12.7mm WIRE)'}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center justify-between text-[10px] pt-0.5">
                    <span className="text-slate-400">TRUE POS / EST GHOST:</span>
                    <span className="font-bold text-amber-300">
                      DRIFT {selectedDrone.position_drift_m.toFixed(2)}m
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-[10px]">
                    <span className="text-slate-400">APAS REACTIVE:</span>
                    <span className="font-bold text-amber-300 truncate max-w-[165px]">
                      {selectedDrone.perception_720?.apas_status || 'NOMINAL'}
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Center Floating Mission Planner Modal */}
            <div className="flex-1 flex items-center justify-center">
              <MissionPlannerPanel
                visible={missionPlannerOpen}
                sarMission={sarMission}
                sarDetections={sarDetections}
                geodeticOrigin={geodeticOrigin}
                gcsPosition={gcsPosition}
                draftPolygon={draftPolygon}
                polygonLocked={polygonLocked}
                onUpdateDraftPolygon={onUpdateDraftPolygon}
                onMissionUpdated={onMissionUpdated}
                onOriginUpdated={onOriginUpdated}
              />
            </div>

            {/* Right Column: Gimbal PiP + RF Link Matrix + Telemetry Log */}
            <div className="flex flex-col gap-2">
              <GimbalPiPViewport
                selectedDrone={selectedDrone}
                drones={drones}
                thermalEntities={thermalEntities}
                onSelectDrone={onSelectDrone}
                onGimbalChange={onGimbalChange}
                onPinTarget={onPinTarget}
              />

              <div className="pointer-events-auto rounded-xl bg-slate-950/90 border border-slate-800 p-2.5 flex flex-col gap-1.5 text-xs w-[350px]">
                <div className="flex items-center justify-between text-[10px] font-bold text-cyan-300">
                  <span>A-MESH RF LINK MATRIX</span>
                  <span className="px-1.5 py-0.5 rounded bg-cyan-950 border border-cyan-500/40 text-[9px]">
                    {meshSummary.topology_mode}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-1 text-[10px] font-mono">
                  {links.slice(0, 4).map((lnk) => (
                    <div
                      key={lnk.id}
                      className="rounded bg-slate-900/90 border border-slate-800 px-2 py-1 flex items-center justify-between"
                    >
                      <span className="text-slate-300">{lnk.id}</span>
                      <span
                        className={
                          lnk.usable
                            ? 'text-emerald-300 font-bold'
                            : 'text-rose-400 font-bold'
                        }
                      >
                        {lnk.usable ? `${lnk.rssi_dbm.toFixed(1)}dBm` : 'OCC'}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="pointer-events-auto rounded-xl bg-slate-950/90 border border-slate-800 p-2.5 flex flex-col gap-1 text-[10px] w-[350px] max-h-28 overflow-y-auto font-mono text-slate-300">
                <div className="text-cyan-300 font-bold">
                  AUTONOMOUS MESH & APAS TELEMETRY LOG
                </div>
                {eventLog.slice(-3).map((line, i) => (
                  <div key={i} className="text-slate-400 leading-tight">
                    {line}
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Desktop Bottom Environment & Scenario Control Strip */}
          <div className="hidden md:flex pointer-events-auto items-center justify-between rounded-xl bg-slate-950/90 border border-slate-800 px-3.5 py-2 backdrop-blur-md text-xs mb-12">
            <div className="flex items-center gap-2">
              <button
                id="btn-pause-sim"
                type="button"
                onClick={() => onControlAction({ action: 'toggle_pause' })}
                className="px-3 py-1 rounded-lg bg-amber-950/70 hover:bg-amber-900/80 border border-amber-500/50 text-amber-200 font-bold flex items-center gap-1 cursor-pointer"
              >
                {paused ? (
                  <Play className="w-3.5 h-3.5" />
                ) : (
                  <Pause className="w-3.5 h-3.5" />
                )}
                <span>{paused ? 'RESUME' : 'PAUSE'}</span>
              </button>

              <button
                id="btn-reset-mission"
                type="button"
                onClick={() => onControlAction({ action: 'reset' })}
                className="px-3 py-1 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-200 font-bold flex items-center gap-1 cursor-pointer"
              >
                <RotateCcw className="w-3.5 h-3.5 text-cyan-400" />
                <span>REPLAY</span>
              </button>
            </div>

            {/* Ambient Lux Controls */}
            <div className="flex items-center gap-2">
              <Sun className="w-3.5 h-3.5 text-amber-400" />
              <span className="text-slate-400 text-[11px]">
                AMBIENT LUX:{' '}
                <strong className="text-amber-300">{ambientLux.toFixed(0)} lx</strong>
              </span>
              <input
                type="range"
                min={2}
                max={1000}
                value={ambientLux}
                onChange={(e) =>
                  onControlAction({
                    action: 'environment',
                    ambient_lux: Number(e.target.value),
                  })
                }
                className="w-24 accent-amber-400 cursor-pointer"
              />
              <button
                id="btn-lux-day"
                type="button"
                onClick={() =>
                  onControlAction({ action: 'environment', ambient_lux: 650 })
                }
                className="px-2 py-0.5 rounded bg-slate-900 border border-slate-700 text-[10px] text-slate-300 cursor-pointer"
              >
                DAY
              </button>
              <button
                id="btn-lux-dusk"
                type="button"
                onClick={() =>
                  onControlAction({ action: 'environment', ambient_lux: 22 })
                }
                className="px-2 py-0.5 rounded bg-slate-900 border border-slate-700 text-[10px] text-slate-300 cursor-pointer"
              >
                DUSK
              </button>
              <button
                id="btn-lux-night"
                type="button"
                onClick={() =>
                  onControlAction({ action: 'environment', ambient_lux: 5 })
                }
                className="px-2 py-0.5 rounded bg-amber-950/80 border border-amber-500/50 text-[10px] text-amber-300 font-bold cursor-pointer"
              >
                NIGHT 5lx
              </button>
            </div>

            {/* Wind Speed Slider */}
            <div className="flex items-center gap-2">
              <Wind className="w-3.5 h-3.5 text-cyan-400" />
              <span className="text-cyan-300 font-bold">
                {windSpeedMs.toFixed(1)}m/s
              </span>
              <input
                type="range"
                min={0}
                max={18}
                step={0.5}
                value={windSpeedMs}
                onChange={(e) =>
                  onControlAction({
                    action: 'environment',
                    wind_speed_ms: Number(e.target.value),
                  })
                }
                className="w-20 accent-cyan-400 cursor-pointer"
              />
            </div>

            {/* EW Jamming & Valley Dome Scenario Buttons */}
            <div className="flex items-center gap-2">
              <button
                id="btn-drop-jamming-zone"
                type="button"
                onClick={() => onControlAction({ action: 'drop_jamming_zone' })}
                className="px-2.5 py-1 rounded-lg bg-rose-950/70 hover:bg-rose-900/80 border border-rose-500/50 text-rose-200 font-bold text-[11px] flex items-center gap-1 cursor-pointer"
              >
                <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
                <span>DROP JAMMING ZONE</span>
              </button>

              <button
                id="btn-valley-dome-scenario"
                type="button"
                onClick={() => onControlAction({ action: 'valley_dome_wire_run' })}
                className="px-2.5 py-1 rounded-lg bg-amber-950/70 hover:bg-amber-900/80 border border-amber-500/50 text-amber-200 font-bold text-[11px] flex items-center gap-1 cursor-pointer"
              >
                <Zap className="w-3.5 h-3.5 text-amber-400" />
                <span>VALLEY DOME + WIRE RUN</span>
              </button>

              <button
                id="btn-ew-jamming"
                type="button"
                onClick={() => onControlAction({ action: 'ew_jamming' })}
                className={`px-2.5 py-1 rounded-lg font-bold text-[11px] border cursor-pointer ${
                  ewJammingActive
                    ? 'bg-rose-600/30 border-rose-400 text-rose-200'
                    : 'bg-slate-900 border-slate-700 text-slate-300'
                }`}
              >
                EW JAM
              </button>
            </div>
          </div>
        </>
      )}

      {/* =====================================================================
          MOBILE TABBED BOTTOM SHEET & MISSION PLANNER SHEET (< 768px)
         ===================================================================== */}
      {isMobile && (
        <div className="md:hidden flex flex-col justify-end w-full max-w-full mb-9 gap-2">
          {/* Mobile Scrollable Mission Planner Bottom Sheet when opened */}
          {missionPlannerOpen ? (
            <div className="w-full max-w-full">
              <MissionPlannerPanel
                visible={missionPlannerOpen}
                sarMission={sarMission}
                sarDetections={sarDetections}
                geodeticOrigin={geodeticOrigin}
                gcsPosition={gcsPosition}
                draftPolygon={draftPolygon}
                polygonLocked={polygonLocked}
                onUpdateDraftPolygon={onUpdateDraftPolygon}
                onMissionUpdated={onMissionUpdated}
                onOriginUpdated={onOriginUpdated}
              />
            </div>
          ) : (
            mobileHudVisible && (
              <div
                id="mobile-control-sheet"
                className="pointer-events-auto w-full max-w-full rounded-xl bg-slate-950/92 border border-slate-800 shadow-2xl backdrop-blur-md p-2 flex flex-col gap-2 max-h-[42dvh] overflow-y-auto"
              >
                {/* 3-Tab Switcher Header */}
                <div className="grid grid-cols-3 gap-1 rounded-lg bg-slate-900/90 p-1 border border-slate-800 shrink-0">
                  <button
                    id="tab-mobile-swarm"
                    type="button"
                    onClick={() => setMobileTab('SWARM')}
                    className={`py-1 px-2 rounded-md text-[11px] font-bold flex items-center justify-center gap-1 cursor-pointer transition ${
                      mobileTab === 'SWARM'
                        ? 'bg-cyan-500/20 border border-cyan-400/70 text-cyan-200'
                        : 'text-slate-400 hover:text-slate-200 border border-transparent'
                    }`}
                  >
                    <Radio className="w-3 h-3 text-cyan-400 shrink-0" />
                    <span>Swarm</span>
                  </button>

                  <button
                    id="tab-mobile-gimbal"
                    type="button"
                    onClick={() => setMobileTab('GIMBAL')}
                    className={`py-1 px-2 rounded-md text-[11px] font-bold flex items-center justify-center gap-1 cursor-pointer transition ${
                      mobileTab === 'GIMBAL'
                        ? 'bg-amber-500/20 border border-amber-400/70 text-amber-200'
                        : 'text-slate-400 hover:text-slate-200 border border-transparent'
                    }`}
                  >
                    <Crosshair className="w-3 h-3 text-amber-400 shrink-0" />
                    <span>Gimbal / LRF</span>
                  </button>

                  <button
                    id="tab-mobile-env"
                    type="button"
                    onClick={() => setMobileTab('ENV')}
                    className={`py-1 px-2 rounded-md text-[11px] font-bold flex items-center justify-center gap-1 cursor-pointer transition ${
                      mobileTab === 'ENV'
                        ? 'bg-emerald-500/20 border border-emerald-400/70 text-emerald-200'
                        : 'text-slate-400 hover:text-slate-200 border border-transparent'
                    }`}
                  >
                    <Sliders className="w-3 h-3 text-emerald-400 shrink-0" />
                    <span>Env / Sim</span>
                  </button>
                </div>

                {/* TAB 1: SWARM TELEMETRY (Horizontal Swipeable Cards) */}
                {mobileTab === 'SWARM' && (
                  <div className="flex flex-col gap-1.5 w-full overflow-hidden">
                    <div className="flex items-center justify-between px-2 py-1 rounded bg-slate-900/90 border border-cyan-500/30 text-[10px]">
                      <span className="text-slate-300 font-semibold truncate">
                        ROUTE: {meshSummary.active_route.join(' ↔ ')}
                      </span>
                      <span
                        className={`px-1.5 py-0.5 rounded text-[9px] font-bold shrink-0 ${
                          meshSummary.relay_bridged
                            ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-400/50'
                            : 'bg-emerald-500/20 text-emerald-300 border border-emerald-400/50'
                        }`}
                      >
                        {meshSummary.relay_bridged ? '2-HOP RELAY' : 'DIRECT LOS'}
                      </span>
                    </div>

                    <div className="flex items-stretch gap-2 overflow-x-auto no-scrollbar pb-0.5">
                      {drones.map((d) => {
                        const isSelected = d.id === selectedDrone?.id;
                        return (
                          <div
                            key={d.id}
                            onClick={() => onSelectDrone(d.id)}
                            className={`min-w-[215px] shrink-0 rounded-lg bg-slate-900/95 border p-2 flex flex-col gap-1 text-[10px] cursor-pointer ${
                              isSelected
                                ? 'border-cyan-400/80'
                                : 'border-slate-800'
                            }`}
                          >
                            <div className="flex items-center justify-between gap-1">
                              <div className="flex items-center gap-1 font-bold text-slate-100">
                                <span
                                  className={`w-2 h-2 rounded-full ${
                                    d.id === 'UAV-1'
                                      ? 'bg-emerald-400'
                                      : d.id === 'UAV-2'
                                      ? 'bg-cyan-400'
                                      : 'bg-purple-400'
                                  }`}
                                />
                                <span>{d.id}</span>
                              </div>
                              <span
                                className={`px-1.5 py-0.5 rounded text-[9px] font-bold border ${
                                  d.nav_mode === 'RTK-FIXED'
                                    ? 'bg-emerald-950/80 border-emerald-500/50 text-emerald-300'
                                    : d.nav_mode === 'V-SLAM'
                                    ? 'bg-cyan-950/80 border-cyan-500/50 text-cyan-300'
                                    : 'bg-rose-950/80 border-rose-500/50 text-rose-300'
                                }`}
                              >
                                {d.nav_mode}
                              </span>
                            </div>

                            <div className="flex items-center justify-between text-[9px] text-slate-400">
                              <span>A-MESH → {d.connected_via}</span>
                              <span className="font-mono text-emerald-300">
                                {d.rssi_dbm.toFixed(0)}dBm
                              </span>
                            </div>

                            <div className="grid grid-cols-3 gap-1 pt-1 border-t border-slate-800 text-[9px]">
                              <div>
                                <div className="text-slate-400">BAT</div>
                                <div className="font-bold text-emerald-300">
                                  {d.battery_pct.toFixed(0)}%
                                </div>
                              </div>
                              <div>
                                <div className="text-slate-400">ALT</div>
                                <div className="font-bold text-slate-100">
                                  {d.alt_agl.toFixed(0)}m
                                </div>
                              </div>
                              <div>
                                <div className="text-slate-400">SPD</div>
                                <div className="font-bold text-cyan-300">
                                  {d.speed_ms.toFixed(1)}m/s
                                </div>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* TAB 2: GIMBAL / LRF VIEWPORT */}
                {mobileTab === 'GIMBAL' && (
                  <div className="w-full max-w-full overflow-x-hidden">
                    <GimbalPiPViewport
                      selectedDrone={selectedDrone}
                      drones={drones}
                      thermalEntities={thermalEntities}
                      onSelectDrone={onSelectDrone}
                      onGimbalChange={onGimbalChange}
                      onPinTarget={onPinTarget}
                    />
                  </div>
                )}

                {/* TAB 3: ENVIRONMENT & SIMULATION CONTROLS */}
                {mobileTab === 'ENV' && (
                  <div className="flex flex-col gap-2 text-[11px] w-full">
                    {/* Pause / Reset / Scenarios */}
                    <div className="grid grid-cols-2 gap-1.5">
                      <button
                        id="btn-pause-sim"
                        type="button"
                        onClick={() => onControlAction({ action: 'toggle_pause' })}
                        className="py-1.5 px-2 rounded-lg bg-amber-950/70 border border-amber-500/50 text-amber-200 font-bold flex items-center justify-center gap-1 cursor-pointer"
                      >
                        {paused ? (
                          <Play className="w-3.5 h-3.5" />
                        ) : (
                          <Pause className="w-3.5 h-3.5" />
                        )}
                        <span>{paused ? 'RESUME' : 'PAUSE'}</span>
                      </button>

                      <button
                        id="btn-reset-mission"
                        type="button"
                        onClick={() => onControlAction({ action: 'reset' })}
                        className="py-1.5 px-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-200 font-bold flex items-center justify-center gap-1 cursor-pointer"
                      >
                        <RotateCcw className="w-3.5 h-3.5 text-cyan-400" />
                        <span>RESET SIM</span>
                      </button>
                    </div>

                    {/* Jamming & Valley Dome */}
                    <div className="grid grid-cols-3 gap-1.5">
                      <button
                        id="btn-drop-jamming-zone"
                        type="button"
                        onClick={() =>
                          onControlAction({ action: 'drop_jamming_zone' })
                        }
                        className="py-1.5 px-2 rounded-lg bg-rose-950/70 border border-rose-500/50 text-rose-200 font-bold text-[10px] flex items-center justify-center gap-1 cursor-pointer"
                      >
                        <ShieldAlert className="w-3 h-3 text-rose-400 shrink-0" />
                        <span>JAM ZONE</span>
                      </button>

                      <button
                        id="btn-valley-dome-scenario"
                        type="button"
                        onClick={() =>
                          onControlAction({ action: 'valley_dome_wire_run' })
                        }
                        className="py-1.5 px-2 rounded-lg bg-amber-950/70 border border-amber-500/50 text-amber-200 font-bold text-[10px] flex items-center justify-center gap-1 cursor-pointer"
                      >
                        <Zap className="w-3 h-3 text-amber-400 shrink-0" />
                        <span>VALLEY WIRE</span>
                      </button>

                      <button
                        id="btn-ew-jamming"
                        type="button"
                        onClick={() => onControlAction({ action: 'ew_jamming' })}
                        className={`py-1.5 px-2 rounded-lg font-bold text-[10px] border cursor-pointer ${
                          ewJammingActive
                            ? 'bg-rose-600/30 border-rose-400 text-rose-200'
                            : 'bg-slate-900 border-slate-700 text-slate-300'
                        }`}
                      >
                        EW JAM
                      </button>
                    </div>

                    {/* Ambient Lux & Wind Speed */}
                    <div className="grid grid-cols-2 gap-2 rounded-lg bg-slate-900/90 border border-slate-800 p-2">
                      <div className="flex flex-col gap-1">
                        <div className="flex items-center justify-between text-[10px]">
                          <span className="text-slate-400 flex items-center gap-1">
                            <Sun className="w-3 h-3 text-amber-400" /> LUX
                          </span>
                          <span className="font-bold text-amber-300">
                            {ambientLux.toFixed(0)} lx
                          </span>
                        </div>
                        <input
                          type="range"
                          min={2}
                          max={1000}
                          value={ambientLux}
                          onChange={(e) =>
                            onControlAction({
                              action: 'environment',
                              ambient_lux: Number(e.target.value),
                            })
                          }
                          className="w-full accent-amber-400 cursor-pointer"
                        />
                        <div className="flex items-center justify-between gap-1">
                          <button
                            id="btn-lux-day"
                            type="button"
                            onClick={() =>
                              onControlAction({
                                action: 'environment',
                                ambient_lux: 650,
                              })
                            }
                            className="flex-1 py-0.5 rounded bg-slate-950 border border-slate-700 text-[9px] text-slate-300"
                          >
                            DAY
                          </button>
                          <button
                            id="btn-lux-dusk"
                            type="button"
                            onClick={() =>
                              onControlAction({
                                action: 'environment',
                                ambient_lux: 22,
                              })
                            }
                            className="flex-1 py-0.5 rounded bg-slate-950 border border-slate-700 text-[9px] text-slate-300"
                          >
                            DUSK
                          </button>
                          <button
                            id="btn-lux-night"
                            type="button"
                            onClick={() =>
                              onControlAction({
                                action: 'environment',
                                ambient_lux: 5,
                              })
                            }
                            className="flex-1 py-0.5 rounded bg-amber-950/80 border border-amber-500/50 text-[9px] text-amber-300 font-bold"
                          >
                            5lx
                          </button>
                        </div>
                      </div>

                      <div className="flex flex-col justify-between gap-1">
                        <div className="flex items-center justify-between text-[10px]">
                          <span className="text-slate-400 flex items-center gap-1">
                            <Wind className="w-3 h-3 text-cyan-400" /> WIND
                          </span>
                          <span className="font-bold text-cyan-300">
                            {windSpeedMs.toFixed(1)}m/s
                          </span>
                        </div>
                        <input
                          type="range"
                          min={0}
                          max={18}
                          step={0.5}
                          value={windSpeedMs}
                          onChange={(e) =>
                            onControlAction({
                              action: 'environment',
                              wind_speed_ms: Number(e.target.value),
                            })
                          }
                          className="w-full accent-cyan-400 cursor-pointer"
                        />
                        <div className="flex items-center gap-1">
                          <button
                            type="button"
                            onClick={onToggleFovCones}
                            className={`flex-1 py-0.5 rounded border text-[9px] font-bold ${
                              showFovCones
                                ? 'bg-cyan-500/20 border-cyan-400 text-cyan-300'
                                : 'bg-slate-950 border-slate-700 text-slate-400'
                            }`}
                          >
                            FOV
                          </button>
                          <button
                            type="button"
                            onClick={onToggleGrid}
                            className={`flex-1 py-0.5 rounded border text-[9px] font-bold ${
                              showGrid
                                ? 'bg-cyan-500/20 border-cyan-400 text-cyan-300'
                                : 'bg-slate-950 border-slate-700 text-slate-400'
                            }`}
                          >
                            GRID
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )
          )}
        </div>
      )}
    </div>
  );
};
