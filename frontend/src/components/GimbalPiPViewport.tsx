import React from 'react';
import { Crosshair, Maximize2, Pin, Flame } from 'lucide-react';
import { DroneTelemetry, ThermalEntityData } from '../types/telemetry';

interface GimbalPiPViewportProps {
  selectedDrone: DroneTelemetry | undefined;
  drones: DroneTelemetry[];
  thermalEntities: ThermalEntityData[];
  onSelectDrone: (id: string) => void;
  onGimbalChange: (params: {
    drone_id: string;
    pitch_deg?: number;
    yaw_deg?: number;
    sensor_mode?: 'WIDE' | 'ZOOM' | 'THERMAL';
    thermal_palette?: 'WHITE_HOT' | 'IRONBOW' | 'BLACK_HOT';
    zoom_level?: number;
    slew_to_entity_id?: string;
  }) => void;
  onPinTarget: (droneId: string) => void;
  swappedMain?: boolean;
  onToggleSwap?: () => void;
}

export const GimbalPiPViewport: React.FC<GimbalPiPViewportProps> = ({
  selectedDrone,
  drones,
  thermalEntities,
  onSelectDrone,
  onGimbalChange,
  onPinTarget,
  swappedMain = false,
  onToggleSwap,
}) => {
  const drone = selectedDrone || drones[0];
  if (!drone) return null;

  const lrf = drone.lrf;
  const isThermal = drone.sensor_mode === 'THERMAL';
  const bgGradient =
    isThermal && drone.thermal_palette === 'IRONBOW'
      ? 'from-[#1a0526] via-[#4a0e2e] to-[#0f061c]'
      : isThermal && drone.thermal_palette === 'BLACK_HOT'
      ? 'from-slate-200 via-slate-400 to-slate-600 text-slate-900'
      : isThermal
      ? 'from-slate-900 via-slate-800 to-black'
      : 'from-[#081526] via-[#0c2238] to-[#050d17]';

  return (
    <div className="pointer-events-auto flex flex-col gap-2.5 w-[350px]">
      {/* Gimbal PiP Card */}
      <div
        id="gimbal-pip-card"
        className="rounded-xl bg-slate-950/90 border border-slate-800 shadow-2xl backdrop-blur-md p-3 flex flex-col gap-2 text-xs"
      >
        {/* Top bar */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 font-bold text-amber-400 text-[11px]">
            <Flame className="w-3.5 h-3.5" />
            <span>GIMBAL PIP:</span>
          </div>
          <div className="flex items-center gap-1">
            {drones.map((d) => (
              <button
                key={d.id}
                type="button"
                onClick={() => onSelectDrone(d.id)}
                className={`px-2 py-0.5 rounded text-[10px] font-bold border cursor-pointer ${
                  d.id === drone.id
                    ? 'bg-cyan-500/20 border-cyan-400 text-cyan-300'
                    : 'bg-slate-900 border-slate-700 text-slate-400'
                }`}
              >
                {d.id}
              </button>
            ))}
            {onToggleSwap && (
              <button
                id="btn-swap-pip"
                type="button"
                onClick={onToggleSwap}
                className="px-2 py-0.5 rounded bg-slate-900 hover:bg-slate-800 border border-slate-700 text-[10px] text-slate-300 flex items-center gap-1 cursor-pointer"
              >
                <Maximize2 className="w-3 h-3" />
                {swappedMain ? 'DOCK PIP' : 'EXPAND MAIN'}
              </button>
            )}
          </div>
        </div>

        {/* Simulated Optical / Thermal Gimbal Reticle Viewport */}
        <div
          className={`relative h-40 rounded-lg border border-rose-500/40 bg-gradient-to-b ${bgGradient} overflow-hidden flex items-center justify-center`}
        >
          <div className="absolute top-2 left-2 px-1.5 py-0.5 rounded bg-slate-950/80 border border-slate-800 text-[10px] text-cyan-300 font-mono">
            PITCH {drone.gimbal_pitch_deg.toFixed(1)}° • YAW{' '}
            {drone.gimbal_yaw_deg >= 0 ? '+' : ''}
            {drone.gimbal_yaw_deg.toFixed(1)}°
          </div>
          <div className="absolute top-2 right-2 px-1.5 py-0.5 rounded bg-slate-950/80 border border-amber-500/40 text-[10px] text-amber-300 font-mono">
            {drone.zoom_level}x • {drone.sensor_mode} ({drone.fov_deg.toFixed(1)}°)
          </div>

          {/* Center LRF Crosshair */}
          <div className="relative flex items-center justify-center">
            <div className="w-12 h-12 border border-rose-400/70 rounded-sm flex items-center justify-center">
              <Crosshair className="w-5 h-5 text-rose-400/80" />
            </div>
            {lrf && (
              <div className="ml-3 px-2 py-1 rounded bg-slate-950/90 border border-amber-500/50 text-[10px] font-mono">
                <div className="text-amber-200 font-bold truncate max-w-[125px]">
                  {lrf.target_label}
                </div>
                <div className="text-amber-400">
                  TEMP: {lrf.target_temp_c.toFixed(1)}°C
                </div>
              </div>
            )}
          </div>

          {/* Bottom LRF Coordinate Bar */}
          {lrf && (
            <div
              id="lrf-readout-bar"
              className="absolute bottom-1.5 inset-x-2 px-2 py-1 rounded bg-slate-950/90 border border-rose-500/40 flex items-center justify-between text-[10px] font-mono"
            >
              <span className="text-rose-400 font-bold">
                • LRF: {lrf.slant_range_m.toFixed(1)} m
              </span>
              <span id="lrf-target-wgs84" className="text-slate-200">
                {lrf.target_lat.toFixed(6)}°N, {lrf.target_lon.toFixed(6)}°E •{' '}
                {lrf.target_alt_asl.toFixed(1)}m ASL
              </span>
            </div>
          )}
        </div>

        {/* Sensor & Thermal Palette Controls */}
        <div className="flex items-center justify-between gap-1">
          <div className="flex items-center gap-1">
            {(['WIDE', 'ZOOM', 'THERMAL'] as const).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => onGimbalChange({ drone_id: drone.id, sensor_mode: m })}
                className={`px-2 py-0.5 rounded text-[10px] font-bold border cursor-pointer ${
                  drone.sensor_mode === m
                    ? 'bg-amber-500/20 border-amber-400 text-amber-300'
                    : 'bg-slate-900 border-slate-700 text-slate-400'
                }`}
              >
                {m}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-1">
            {(['WHITE_HOT', 'IRONBOW', 'BLACK_HOT'] as const).map((pal) => (
              <button
                key={pal}
                type="button"
                onClick={() =>
                  onGimbalChange({
                    drone_id: drone.id,
                    sensor_mode: 'THERMAL',
                    thermal_palette: pal,
                  })
                }
                className={`px-1.5 py-0.5 rounded text-[9px] font-semibold border cursor-pointer ${
                  drone.thermal_palette === pal
                    ? 'bg-amber-500/20 border-amber-400 text-amber-300'
                    : 'bg-slate-900 border-slate-700 text-slate-400'
                }`}
              >
                {pal.replace('_', ' ')}
              </button>
            ))}
          </div>
        </div>

        {/* Zoom Selector */}
        <div className="flex items-center justify-between text-[10px]">
          <span className="text-slate-400">ZOOM:</span>
          <div className="flex items-center gap-1">
            {[1, 10, 40, 80, 160].map((z) => (
              <button
                key={z}
                type="button"
                onClick={() => onGimbalChange({ drone_id: drone.id, zoom_level: z })}
                className={`px-1.5 py-0.5 rounded border cursor-pointer ${
                  drone.zoom_level === z
                    ? 'bg-cyan-500/20 border-cyan-400 text-cyan-300 font-bold'
                    : 'bg-slate-900 border-slate-700 text-slate-400'
                }`}
              >
                {z === 1 ? '1x' : z === 10 ? '10x OPT' : `${z}x HYB`}
              </button>
            ))}
          </div>
        </div>

        {/* Pitch & Yaw Sliders */}
        <div className="grid grid-cols-2 gap-2 text-[10px]">
          <div>
            <div className="flex justify-between mb-0.5">
              <span className="text-slate-400">
                PITCH ({drone.gimbal_pitch_deg.toFixed(0)}°)
              </span>
              <button
                type="button"
                onClick={() => onGimbalChange({ drone_id: drone.id, pitch_deg: -28 })}
                className="text-[9px] text-cyan-300 underline cursor-pointer"
              >
                VALLEY -28°
              </button>
            </div>
            <input
              type="range"
              min={-90}
              max={30}
              step={1}
              value={drone.gimbal_pitch_deg}
              onChange={(e) =>
                onGimbalChange({
                  drone_id: drone.id,
                  pitch_deg: Number(e.target.value),
                })
              }
              className="w-full accent-cyan-400 cursor-pointer"
            />
          </div>
          <div>
            <div className="flex justify-between mb-0.5">
              <span className="text-slate-400">
                YAW ({drone.gimbal_yaw_deg.toFixed(0)}°)
              </span>
              <button
                type="button"
                onClick={() => onGimbalChange({ drone_id: drone.id, yaw_deg: 0 })}
                className="text-[9px] text-cyan-300 underline cursor-pointer"
              >
                0° CENTER
              </button>
            </div>
            <input
              type="range"
              min={-180}
              max={180}
              step={2}
              value={drone.gimbal_yaw_deg}
              onChange={(e) =>
                onGimbalChange({
                  drone_id: drone.id,
                  yaw_deg: Number(e.target.value),
                })
              }
              className="w-full accent-cyan-400 cursor-pointer"
            />
          </div>
        </div>

        {/* Pin Target Button */}
        <button
          id="btn-pin-lrf-target"
          type="button"
          onClick={() => onPinTarget(drone.id)}
          className="w-full py-1.5 rounded-lg bg-rose-950/70 hover:bg-rose-900/80 border border-rose-500/60 text-rose-200 font-bold tracking-wider flex items-center justify-center gap-1.5 cursor-pointer"
        >
          <Pin className="w-3.5 h-3.5 text-rose-400" />
          PIN TARGET TO A-MESH [SPACE]
        </button>
      </div>

      {/* Valley Thermal Signatures Quick Slew Card */}
      <div className="rounded-xl bg-slate-950/90 border border-slate-800 p-3 flex flex-col gap-1.5 text-xs">
        <div className="flex items-center justify-between text-[10px] font-bold text-amber-300">
          <span>VALLEY THERMAL SIGNATURES ({thermalEntities.length} ACTIVE)</span>
          <span className="text-[9px] text-slate-400">CLICK TO SLEW GIMBAL</span>
        </div>
        <div className="grid grid-cols-2 gap-1.5">
          {thermalEntities.map((ent) => (
            <button
              key={ent.id}
              type="button"
              onClick={() =>
                onGimbalChange({
                  drone_id: drone.id,
                  slew_to_entity_id: ent.id,
                })
              }
              className="p-1.5 rounded bg-slate-900/90 hover:bg-slate-800 border border-slate-800 text-left flex flex-col gap-0.5 cursor-pointer"
            >
              <div className="flex items-center justify-between font-bold text-[10px]">
                <span className="text-amber-400">{ent.id}</span>
                <span className="text-rose-300">{ent.temp_c.toFixed(1)}°C</span>
              </div>
              <div className="text-[9px] text-slate-400 truncate">{ent.label}</div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};
