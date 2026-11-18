import React from 'react';
import {
  Radio,
  Compass,
  Eye,
  Grid,
  Pause,
  Play,
  RotateCcw,
  Sun,
  Wind,
  Zap,
  ShieldAlert,
  Flame,
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
  cameraPreset: 'OVERVIEW' | 'RIDGE_PROFILE' | 'UAV-1' | 'UAV-2';
  draftPolygon: [number, number][];
  polygonLocked: boolean;
  onSelectDrone: (id: string) => void;
  onToggleMissionPlanner: () => void;
  onToggle720Bubble: () => void;
  onToggleFovCones: () => void;
  onToggleGrid: () => void;
  onSelectCameraPreset: (p: 'OVERVIEW' | 'RIDGE_PROFILE' | 'UAV-1' | 'UAV-2') => void;
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
  const selectedDrone = drones.find((d) => d.id === selectedDroneId) || drones[0];
  const latestSarDetection =
    sarDetections.length > 0 ? sarDetections[sarDetections.length - 1] : null;

  return (
    <div className="pointer-events-none absolute inset-0 flex flex-col justify-between p-3 select-none">
      {/* Top Tactical Header Bar */}
      <div className="flex flex-col gap-2">
        <div className="pointer-events-auto flex items-center justify-between rounded-xl bg-slate-950/90 border border-slate-800 px-3.5 py-2 backdrop-blur-md">
          <div className="flex items-center gap-3">
            <div className="px-2.5 py-1 rounded bg-amber-500/15 border border-amber-500/50 text-amber-300 text-[10px] font-bold tracking-wider">
              • AUTEL SMART CONTROLLER V3
            </div>
            <div>
              <div className="text-xs font-bold tracking-wider text-slate-100">
                A-MESH SIM 4T // 720° RADAR + V-SLAM SWARM
              </div>
              <div className="text-[10px] text-slate-400">
                Fisheye 40m (≥15 lx) • 60GHz/24GHz mmWave 50m (15mm wire) • RTK / V-SLAM / IMU
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              id="btn-mission-planner-toggle"
              type="button"
              onClick={onToggleMissionPlanner}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold border flex items-center gap-1.5 cursor-pointer ${
                missionPlannerOpen
                  ? 'bg-cyan-500/20 border-cyan-400 text-cyan-200'
                  : 'bg-slate-900 border-slate-700 text-slate-300'
              }`}
            >
              <Compass className="w-3.5 h-3.5 text-cyan-400" />
              <span>Mission Planner</span>
            </button>

            <button
              id="btn-toggle-720-bubble"
              type="button"
              onClick={onToggle720Bubble}
              className={`px-2.5 py-1.5 rounded-lg text-xs font-bold border cursor-pointer ${
                show720Bubble
                  ? 'bg-amber-500/20 border-amber-400 text-amber-300'
                  : 'bg-slate-900 border-slate-700 text-slate-400'
              }`}
            >
              720° Bubble
            </button>

            <button
              type="button"
              onClick={onToggleFovCones}
              className={`px-2.5 py-1.5 rounded-lg text-xs border flex items-center gap-1 cursor-pointer ${
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
              className={`px-2.5 py-1.5 rounded-lg text-xs border flex items-center gap-1 cursor-pointer ${
                showGrid
                  ? 'bg-cyan-500/20 border-cyan-400 text-cyan-300'
                  : 'bg-slate-900 border-slate-700 text-slate-400'
              }`}
            >
              <Grid className="w-3.5 h-3.5" />
              <span>Grid</span>
            </button>

            <div className="px-2.5 py-1 rounded bg-slate-900 border border-slate-800 text-xs font-mono text-slate-200">
              T+{simTime.toFixed(1)}s
            </div>
            <div className="px-2 py-1 rounded bg-emerald-950/80 border border-emerald-500/50 text-[10px] font-bold text-emerald-300">
              20Hz
            </div>
          </div>

          <div className="flex items-center gap-2">
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

        {/* Camera Preset Bar */}
        <div className="pointer-events-auto self-center flex items-center gap-1.5 rounded-lg bg-slate-950/85 border border-slate-800 px-2.5 py-1">
          <span className="text-[10px] text-slate-400 font-semibold mr-1">CAM:</span>
          {(
            [
              ['OVERVIEW', 'Sector Overview'],
              ['RIDGE_PROFILE', 'Ridge LOS Profile'],
              ['UAV-1', 'Track UAV-1 (Scout)'],
              ['UAV-2', 'Track UAV-2 (Relay)'],
            ] as const
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => onSelectCameraPreset(key)}
              className={`px-2.5 py-0.5 rounded text-[11px] font-semibold cursor-pointer ${
                cameraPreset === key
                  ? 'bg-cyan-500/20 border border-cyan-400 text-cyan-300'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Pulsing SAR Heat Contact Alert Banner */}
        {latestSarDetection && (
          <div
            id="sar-heat-alert-banner"
            className="pointer-events-auto self-center rounded-xl bg-amber-950/90 border border-amber-400 px-4 py-1.5 text-xs font-bold text-amber-200 flex items-center gap-2 shadow-lg"
          >
            <Flame className="w-4 h-4 text-amber-400" />
            <span>
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

      {/* Main Middle Overlay Columns: Left Telemetry Cards | Center Mission Planner | Right Gimbal PiP */}
      <div className="flex-1 flex items-start justify-between gap-3 my-2 overflow-hidden">
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
                      lnk.usable ? 'text-emerald-300 font-bold' : 'text-rose-400 font-bold'
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

      {/* Bottom Environment & Scenario Control Strip */}
      <div className="pointer-events-auto flex items-center justify-between rounded-xl bg-slate-950/90 border border-slate-800 px-3.5 py-2 backdrop-blur-md text-xs mb-12">
        <div className="flex items-center gap-2">
          <button
            id="btn-pause-sim"
            type="button"
            onClick={() => onControlAction({ action: 'toggle_pause' })}
            className="px-3 py-1 rounded-lg bg-amber-950/70 hover:bg-amber-900/80 border border-amber-500/50 text-amber-200 font-bold flex items-center gap-1 cursor-pointer"
          >
            {paused ? <Play className="w-3.5 h-3.5" /> : <Pause className="w-3.5 h-3.5" />}
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
            AMBIENT LUX: <strong className="text-amber-300">{ambientLux.toFixed(0)} lx</strong>
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
            onClick={() => onControlAction({ action: 'environment', ambient_lux: 650 })}
            className="px-2 py-0.5 rounded bg-slate-900 border border-slate-700 text-[10px] text-slate-300 cursor-pointer"
          >
            DAY
          </button>
          <button
            id="btn-lux-dusk"
            type="button"
            onClick={() => onControlAction({ action: 'environment', ambient_lux: 22 })}
            className="px-2 py-0.5 rounded bg-slate-900 border border-slate-700 text-[10px] text-slate-300 cursor-pointer"
          >
            DUSK
          </button>
          <button
            id="btn-lux-night"
            type="button"
            onClick={() => onControlAction({ action: 'environment', ambient_lux: 5 })}
            className="px-2 py-0.5 rounded bg-amber-950/80 border border-amber-500/50 text-[10px] text-amber-300 font-bold cursor-pointer"
          >
            NIGHT 5lx
          </button>
        </div>

        {/* Wind Speed Slider */}
        <div className="flex items-center gap-2">
          <Wind className="w-3.5 h-3.5 text-cyan-400" />
          <span className="text-cyan-300 font-bold">{windSpeedMs.toFixed(1)}m/s</span>
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
    </div>
  );
};
