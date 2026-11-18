import React, { useState, useEffect, useMemo } from 'react';
import {
  Compass,
  MapPin,
  Trash2,
  Play,
  Download,
  Upload,
  FileArchive,
  Flame,
  Zap,
  Globe,
  Check,
} from 'lucide-react';
import { GeodeticOrigin, SarDetection, SarMissionState } from '../types/telemetry';

const VALLEY_PRESET: [number, number][] = [
  [60, -70],
  [220, -70],
  [220, 70],
  [60, 70],
];

const METERS_PER_DEG_LAT = 111320.0;

export function localToWgs84Frontend(
  x: number,
  z: number,
  originLat: number,
  originLon: number
): { lat: number; lon: number } {
  const cosLat = Math.max(Math.cos((originLat * Math.PI) / 180.0), 1e-6);
  const dLat = -z / METERS_PER_DEG_LAT;
  const dLon = x / (METERS_PER_DEG_LAT * cosLat);
  return {
    lat: originLat + dLat,
    lon: originLon + dLon,
  };
}

interface MissionPlannerPanelProps {
  visible: boolean;
  sarMission: SarMissionState | null;
  sarDetections: SarDetection[];
  geodeticOrigin: GeodeticOrigin | null;
  gcsPosition: [number, number, number];
  draftPolygon: [number, number][];
  polygonLocked: boolean;
  onUpdateDraftPolygon: (pts: [number, number][], locked: boolean) => void;
  onMissionUpdated: (mission: SarMissionState) => void;
  onOriginUpdated?: (origin: GeodeticOrigin) => void;
}

export const MissionPlannerPanel: React.FC<MissionPlannerPanelProps> = ({
  visible,
  sarMission,
  sarDetections,
  geodeticOrigin,
  gcsPosition,
  draftPolygon,
  polygonLocked,
  onUpdateDraftPolygon,
  onMissionUpdated,
  onOriginUpdated,
}) => {
  const [originLatStr, setOriginLatStr] = useState<string>('31.691500');
  const [originLonStr, setOriginLonStr] = useState<string>('34.978500');
  const [originAltStr, setOriginAltStr] = useState<string>('320.0');
  const [originDirty, setOriginDirty] = useState<boolean>(false);

  const [sensorMode, setSensorMode] = useState<'THERMAL' | 'WIDE'>('THERMAL');
  const [altitudeAgl, setAltitudeAgl] = useState<number>(60);
  const [sidelapPct, setSidelapPct] = useState<number>(70);
  const [sweepAngleDeg, setSweepAngleDeg] = useState<number>(0);
  const [statusMsg, setStatusMsg] = useState<string>(
    'Ready — configure WGS84 Site Origin or generate SAR sweep grid.'
  );
  const [busy, setBusy] = useState<boolean>(false);

  // Sync from backend geodeticOrigin when not actively editing
  useEffect(() => {
    if (!geodeticOrigin || originDirty) return;
    const lat = geodeticOrigin.lat ?? geodeticOrigin.origin_lat ?? 31.6915;
    const lon = geodeticOrigin.lon ?? geodeticOrigin.origin_lon ?? 34.9785;
    const alt = geodeticOrigin.alt_asl ?? geodeticOrigin.origin_alt_asl ?? 320.0;
    setOriginLatStr(lat.toFixed(6));
    setOriginLonStr(lon.toFixed(6));
    setOriginAltStr(alt.toFixed(1));
  }, [geodeticOrigin?.lat, geodeticOrigin?.lon, geodeticOrigin?.alt_asl, originDirty]);

  const parsedOrigin = useMemo(() => {
    const lat = Number.parseFloat(originLatStr);
    const lon = Number.parseFloat(originLonStr);
    const alt = Number.parseFloat(originAltStr);
    return {
      lat: Number.isFinite(lat) ? Math.max(-90, Math.min(90, lat)) : 31.6915,
      lon: Number.isFinite(lon) ? Math.max(-180, Math.min(180, lon)) : 34.9785,
      alt_asl: Number.isFinite(alt) ? alt : 320.0,
    };
  }, [originLatStr, originLonStr, originAltStr]);

  const activePolygon = useMemo(() => {
    if (draftPolygon.length >= 3) return draftPolygon;
    if (sarMission?.polygon_xz && sarMission.polygon_xz.length >= 3) {
      return sarMission.polygon_xz;
    }
    return VALLEY_PRESET;
  }, [draftPolygon, sarMission]);

  // Live Origin Corner Readout: exact WGS84 coordinates of GCS and currently drawn polygon's center
  const cornerReadout = useMemo(() => {
    const gcsX = gcsPosition?.[0] ?? -340.0;
    const gcsY = gcsPosition?.[1] ?? 25.0;
    const gcsZ = gcsPosition?.[2] ?? 40.0;
    const gcsWgs = localToWgs84Frontend(gcsX, gcsZ, parsedOrigin.lat, parsedOrigin.lon);
    const gcsAltAsl = parsedOrigin.alt_asl + gcsY;

    const n = activePolygon.length || 1;
    const cx = activePolygon.reduce((acc, p) => acc + p[0], 0) / n;
    const cz = activePolygon.reduce((acc, p) => acc + p[1], 0) / n;
    const polyCenterWgs = localToWgs84Frontend(cx, cz, parsedOrigin.lat, parsedOrigin.lon);
    const polyAltAsl = parsedOrigin.alt_asl + altitudeAgl;

    return {
      gcsLat: gcsWgs.lat,
      gcsLon: gcsWgs.lon,
      gcsAltAsl,
      polyLat: polyCenterWgs.lat,
      polyLon: polyCenterWgs.lon,
      polyAltAsl,
      cx,
      cz,
    };
  }, [gcsPosition, activePolygon, parsedOrigin, altitudeAgl]);

  if (!visible) return null;

  const applyOriginToBackend = async (): Promise<GeodeticOrigin | null> => {
    const lat = Number.parseFloat(originLatStr);
    const lon = Number.parseFloat(originLonStr);
    const alt_asl = Number.parseFloat(originAltStr);
    if (!Number.isFinite(lat) || lat < -90 || lat > 90) {
      setStatusMsg('Error: Latitude must be between -90° and 90°.');
      return null;
    }
    if (!Number.isFinite(lon) || lon < -180 || lon > 180) {
      setStatusMsg('Error: Longitude must be between -180° and 180°.');
      return null;
    }
    const payload = {
      lat,
      lon,
      alt_asl: Number.isFinite(alt_asl) ? alt_asl : 320.0,
    };
    const res = await fetch('/api/mission/origin', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const errText = await res.text();
      setStatusMsg(`Failed to apply WGS84 Origin: ${errText}`);
      return null;
    }
    const data = await res.json();
    setOriginDirty(false);
    if (data.geodetic_origin && onOriginUpdated) {
      onOriginUpdated(data.geodetic_origin);
    }
    if (data.sar_mission) {
      onMissionUpdated(data.sar_mission);
    }
    setStatusMsg(
      `Applied WGS84 Site Origin: ${payload.lat.toFixed(6)}°N, ${payload.lon.toFixed(6)}°E @ ${payload.alt_asl.toFixed(1)}m ASL`
    );
    return data.geodetic_origin;
  };

  const handleApplyOriginClick = async () => {
    setBusy(true);
    try {
      await applyOriginToBackend();
    } finally {
      setBusy(false);
    }
  };

  const handlePresetValley = () => {
    onUpdateDraftPolygon(VALLEY_PRESET, true);
    setStatusMsg('Loaded East Tactical Valley 4-stake polygon (160m × 140m).');
  };

  const handleClosePolygon = () => {
    if (draftPolygon.length >= 3) {
      onUpdateDraftPolygon(draftPolygon, true);
      setStatusMsg(`Polygon locked with ${draftPolygon.length} corner stakes.`);
    }
  };

  const handleClearPolygon = async () => {
    onUpdateDraftPolygon([], false);
    await fetch('/api/mission/clear', { method: 'POST' });
    setStatusMsg('Cleared SAR polygon & waypoints.');
  };

  const handleGenerateGrid = async () => {
    setBusy(true);
    try {
      if (originDirty) {
        await applyOriginToBackend();
      }
      const poly = draftPolygon.length >= 3 ? draftPolygon : VALLEY_PRESET;
      onUpdateDraftPolygon(poly, true);
      const res = await fetch('/api/mission/sar-grid', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          polygon_xz: poly,
          altitude_agl_m: altitudeAgl,
          sensor_mode: sensorMode,
          sidelap_pct: sidelapPct,
          sweep_angle_deg: sweepAngleDeg,
        }),
      });
      if (res.ok) {
        const data: SarMissionState = await res.json();
        onMissionUpdated(data);
        setStatusMsg(
          `Generated ${data.total_legs} legs (${data.total_waypoints} WP) across 3 UAVs.`
        );
      }
    } finally {
      setBusy(false);
    }
  };

  const handleExecuteMission = async () => {
    setBusy(true);
    try {
      if (originDirty) {
        await applyOriginToBackend();
      }
      const res = await fetch('/api/mission/execute', { method: 'POST' });
      if (res.ok) {
        const data: SarMissionState = await res.json();
        onMissionUpdated(data);
        setStatusMsg(`Executing cooperative 3-UAV SAR sweep (${data.mission_id}).`);
      }
    } finally {
      setBusy(false);
    }
  };

  const triggerDownload = async (format: 'kml' | 'wpml_kmz') => {
    setBusy(true);
    try {
      // Ensure any edited WGS84 Site Origin inputs are synced to backend before exporting
      await applyOriginToBackend();
      const res = await fetch(`/api/mission/export-kml?format=${format}`);
      if (!res.ok) {
        setStatusMsg(`Export failed (${res.status})`);
        return;
      }
      const blob = await res.blob();
      const disp = res.headers.get('Content-Disposition') || '';
      const match = disp.match(/filename="([^"]+)"/);
      const missionId = sarMission?.mission_id || 'SAR-001';
      const fallbackName =
        format === 'wpml_kmz'
          ? `amesh_sim_4t_${missionId}_wpml.kmz`
          : `amesh_sim_4t_${missionId}.kml`;
      const filename = match ? match[1] : fallbackName;

      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);

      setStatusMsg(
        format === 'wpml_kmz'
          ? `Exported Autel WPML (.kmz): ${filename}`
          : `Exported Autel KML: ${filename}`
      );
    } finally {
      setBusy(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch('/api/mission/upload-kml', {
        method: 'POST',
        body: formData,
      });
      if (res.ok) {
        const data = await res.json();
        onMissionUpdated(data);
        if (data.polygon_xz) {
          onUpdateDraftPolygon(data.polygon_xz, true);
        }
        if (data.geodetic_origin) {
          setOriginDirty(false);
          setOriginLatStr(Number(data.geodetic_origin.lat).toFixed(6));
          setOriginLonStr(Number(data.geodetic_origin.lon).toFixed(6));
          setOriginAltStr(Number(data.geodetic_origin.alt_asl ?? 320).toFixed(1));
          if (onOriginUpdated) {
            onOriginUpdated(data.geodetic_origin);
          }
        }
        const gType = data.imported?.is_wpml
          ? 'WPML .kmz'
          : data.imported?.geometry_type || 'POLYGON';
        setStatusMsg(
          `Imported ${file.name} (${gType}): ${data.total_waypoints} WP loaded.`
        );
      } else {
        setStatusMsg(`Failed to import ${file.name}`);
      }
    } finally {
      setBusy(false);
      e.target.value = '';
    }
  };

  const areaStr = sarMission
    ? `${(sarMission.area_m2 / 1000).toFixed(1)}k m²`
    : '22.4k m²';
  const swathStr = sarMission
    ? `${sarMission.swath_width_m.toFixed(1)}m / ${sarMission.lane_spacing_m.toFixed(1)}m`
    : '46.1m / 13.8m';
  const wpStr = sarMission ? `${sarMission.total_waypoints} WP` : '88 WP';
  const etaStr = sarMission ? `${Math.round(sarMission.estimated_time_s)}s` : '77s';

  return (
    <div
      id="mission-planner-panel"
      className="pointer-events-auto w-full md:w-[420px] max-w-full rounded-xl bg-slate-950/95 md:bg-slate-950/90 border border-cyan-500/40 shadow-2xl backdrop-blur-md p-3 md:p-3.5 text-xs text-slate-200 flex flex-col gap-2.5 max-h-[65dvh] md:max-h-[82vh] overflow-y-auto"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <div className="flex items-center gap-2 font-bold tracking-wider text-cyan-300">
          <Compass className="w-4 h-4 text-cyan-400" />
          <span>COOPERATIVE SAR GRID PLANNER</span>
        </div>
        <span
          className={`px-2 py-0.5 rounded text-[10px] font-semibold tracking-wider border ${
            sarMission?.executing
              ? 'bg-emerald-950/80 border-emerald-500/60 text-emerald-300'
              : 'bg-slate-900 border-slate-700 text-slate-400'
          }`}
        >
          {sarMission?.executing ? 'SWEEPING ACTIVE' : 'PLANNER READY'}
        </span>
      </div>

      {/* Compact WGS84 Site Origin Input Bar */}
      <div
        id="wgs84-site-origin-bar"
        className="rounded-lg bg-slate-900/95 border border-cyan-500/30 p-2.5 flex flex-col gap-2"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-[11px] font-bold tracking-wider text-cyan-300">
            <Globe className="w-3.5 h-3.5 text-cyan-400" />
            <span>WGS84 SITE ORIGIN</span>
          </div>
          <button
            id="btn-apply-origin"
            type="button"
            disabled={busy}
            onClick={handleApplyOriginClick}
            className="px-2.5 py-1 rounded bg-cyan-600/30 hover:bg-cyan-500/40 border border-cyan-400/60 text-cyan-200 font-semibold text-[10px] tracking-wider flex items-center gap-1 cursor-pointer transition"
          >
            <Check className="w-3 h-3" />
            Apply Datum
          </button>
        </div>

        <div className="grid grid-cols-3 gap-1.5">
          <label className="flex flex-col gap-0.5">
            <span className="text-[9px] text-slate-400 uppercase tracking-wider">
              Latitude (°)
            </span>
            <input
              id="input-origin-lat"
              type="number"
              step="0.0001"
              min="-90"
              max="90"
              value={originLatStr}
              onChange={(e) => {
                setOriginLatStr(e.target.value);
                setOriginDirty(true);
              }}
              className="w-full rounded bg-slate-950 border border-slate-700 px-1.5 py-1 text-[11px] font-mono text-cyan-200 focus:border-cyan-400 focus:outline-none"
            />
          </label>
          <label className="flex flex-col gap-0.5">
            <span className="text-[9px] text-slate-400 uppercase tracking-wider">
              Longitude (°)
            </span>
            <input
              id="input-origin-lon"
              type="number"
              step="0.0001"
              min="-180"
              max="180"
              value={originLonStr}
              onChange={(e) => {
                setOriginLonStr(e.target.value);
                setOriginDirty(true);
              }}
              className="w-full rounded bg-slate-950 border border-slate-700 px-1.5 py-1 text-[11px] font-mono text-cyan-200 focus:border-cyan-400 focus:outline-none"
            />
          </label>
          <label className="flex flex-col gap-0.5">
            <span className="text-[9px] text-slate-400 uppercase tracking-wider">
              Base Elev ASL (m)
            </span>
            <input
              id="input-origin-alt"
              type="number"
              step="1"
              value={originAltStr}
              onChange={(e) => {
                setOriginAltStr(e.target.value);
                setOriginDirty(true);
              }}
              className="w-full rounded bg-slate-950 border border-slate-700 px-1.5 py-1 text-[11px] font-mono text-cyan-200 focus:border-cyan-400 focus:outline-none"
            />
          </label>
        </div>

        {/* Live Origin Corner Readout */}
        <div
          id="origin-corner-readout"
          className="rounded bg-slate-950/90 border border-slate-800 px-2 py-1.5 text-[10px] font-mono flex flex-col gap-0.5"
        >
          <div className="flex items-center justify-between text-slate-300">
            <span className="text-slate-400">GCS WGS84:</span>
            <span id="readout-gcs-wgs84" className="text-emerald-300">
              {cornerReadout.gcsLat.toFixed(6)}°N, {cornerReadout.gcsLon.toFixed(6)}°E •{' '}
              {cornerReadout.gcsAltAsl.toFixed(1)}m ASL
            </span>
          </div>
          <div className="flex items-center justify-between text-slate-300">
            <span className="text-slate-400">POLY CENTER:</span>
            <span id="readout-poly-center-wgs84" className="text-cyan-300">
              {cornerReadout.polyLat.toFixed(6)}°N, {cornerReadout.polyLon.toFixed(6)}°E •{' '}
              {cornerReadout.polyAltAsl.toFixed(1)}m ASL
            </span>
          </div>
        </div>
      </div>

      {/* Polygon Stakes Controls */}
      <div className="flex items-center justify-between rounded-lg bg-slate-900/80 border border-slate-800 px-2.5 py-2">
        <div className="flex items-center gap-2">
          <MapPin className="w-4 h-4 text-cyan-400 shrink-0" />
          <span className="text-[11px] text-cyan-200">
            {polygonLocked
              ? `Polygon locked (${activePolygon.length} stakes)`
              : `Drawing polygon (${draftPolygon.length} stakes)`}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            id="btn-preset-valley-polygon"
            type="button"
            onClick={handlePresetValley}
            className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 border border-slate-600 text-[10px] text-slate-200 cursor-pointer"
          >
            Valley Box
          </button>
          <button
            id="btn-close-polygon"
            type="button"
            onClick={handleClosePolygon}
            className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 border border-slate-600 text-[10px] text-slate-200 cursor-pointer"
          >
            Close Polygon
          </button>
          <button
            id="btn-clear-polygon"
            type="button"
            onClick={handleClearPolygon}
            title="Clear SAR Polygon"
            className="p-1.5 rounded bg-rose-950/60 hover:bg-rose-900/70 border border-rose-500/40 text-rose-300 cursor-pointer"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Sensor Payload Selector */}
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-semibold tracking-wider text-slate-400">
          SENSOR PAYLOAD:
        </span>
        <div className="flex items-center gap-1.5">
          <button
            id="btn-sar-sensor-thermal"
            type="button"
            onClick={() => setSensorMode('THERMAL')}
            className={`px-2.5 py-1 rounded text-[10px] font-semibold border cursor-pointer ${
              sensorMode === 'THERMAL'
                ? 'bg-amber-500/20 border-amber-400 text-amber-300'
                : 'bg-slate-900 border-slate-700 text-slate-400'
            }`}
          >
            Thermal 42° FOV
          </button>
          <button
            id="btn-sar-sensor-wide"
            type="button"
            onClick={() => setSensorMode('WIDE')}
            className={`px-2.5 py-1 rounded text-[10px] font-semibold border cursor-pointer ${
              sensorMode === 'WIDE'
                ? 'bg-cyan-500/20 border-cyan-400 text-cyan-300'
                : 'bg-slate-900 border-slate-700 text-slate-400'
            }`}
          >
            Wide 85° FOV
          </button>
        </div>
      </div>

      {/* Sliders: Altitude AGL, Sidelap, Sweep Azimuth */}
      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-lg bg-slate-900/70 border border-slate-800 p-2">
          <div className="flex justify-between text-[10px] mb-1">
            <span className="text-slate-400">ALTITUDE AGL</span>
            <span className="text-cyan-300 font-bold">{altitudeAgl}m</span>
          </div>
          <input
            id="slider-sar-altitude"
            type="range"
            min={30}
            max={150}
            step={5}
            value={altitudeAgl}
            onChange={(e) => setAltitudeAgl(Number(e.target.value))}
            className="w-full accent-cyan-400 cursor-pointer"
          />
        </div>
        <div className="rounded-lg bg-slate-900/70 border border-slate-800 p-2">
          <div className="flex justify-between text-[10px] mb-1">
            <span className="text-slate-400">SIDELAP</span>
            <span className="text-cyan-300 font-bold">{sidelapPct}%</span>
          </div>
          <input
            id="slider-sar-sidelap"
            type="range"
            min={50}
            max={85}
            step={5}
            value={sidelapPct}
            onChange={(e) => setSidelapPct(Number(e.target.value))}
            className="w-full accent-cyan-400 cursor-pointer"
          />
        </div>
      </div>

      <div className="rounded-lg bg-slate-900/70 border border-slate-800 p-2">
        <div className="flex justify-between text-[10px] mb-1">
          <span className="text-slate-400">SWEEP AZIMUTH ANGLE</span>
          <span className="text-cyan-300 font-bold">{sweepAngleDeg}°</span>
        </div>
        <input
          id="slider-sar-azimuth"
          type="range"
          min={0}
          max={180}
          step={15}
          value={sweepAngleDeg}
          onChange={(e) => setSweepAngleDeg(Number(e.target.value))}
          className="w-full accent-cyan-400 cursor-pointer"
        />
      </div>

      {/* Computed Grid Metrics */}
      <div className="grid grid-cols-4 gap-1.5 rounded-lg bg-slate-900/90 border border-slate-800 p-2 text-center">
        <div>
          <div className="text-[9px] text-slate-400">AREA</div>
          <div id="sar-metric-area" className="text-[11px] font-bold text-slate-100">
            {areaStr}
          </div>
        </div>
        <div>
          <div className="text-[9px] text-slate-400">SWATH / ΔD</div>
          <div id="sar-metric-swath" className="text-[11px] font-bold text-amber-300">
            {swathStr}
          </div>
        </div>
        <div>
          <div className="text-[9px] text-slate-400">WAYPOINTS</div>
          <div id="sar-metric-waypoints" className="text-[11px] font-bold text-emerald-300">
            {wpStr}
          </div>
        </div>
        <div>
          <div className="text-[9px] text-slate-400">EST. TIME</div>
          <div id="sar-metric-eta" className="text-[11px] font-bold text-cyan-300">
            {etaStr}
          </div>
        </div>
      </div>

      {/* Per-UAV Partition Cards */}
      <div className="grid grid-cols-3 gap-1.5">
        {(['UAV-1', 'UAV-2', 'UAV-3'] as const).map((uid) => {
          const part = sarMission?.partitions?.[uid];
          const wpCount = part?.waypoints?.length ?? 0;
          const isRetasked =
            uid === 'UAV-2' && Boolean(sarMission?.relay_retasked);
          const dotColor =
            uid === 'UAV-1'
              ? 'bg-emerald-400'
              : uid === 'UAV-2'
              ? 'bg-cyan-400'
              : 'bg-purple-400';
          return (
            <div
              key={uid}
              className="rounded-lg bg-slate-900/80 border border-slate-800 p-2 flex flex-col gap-0.5"
            >
              <div className="flex items-center gap-1.5 font-bold text-[10px]">
                <span className={`w-2 h-2 rounded-full ${dotColor}`} />
                <span>{uid}</span>
              </div>
              <div className="text-[10px] text-slate-400">
                {isRetasked ? (
                  <span className="text-cyan-300 font-semibold">
                    A-MESH RELAY (RETASKED)
                  </span>
                ) : (
                  `${wpCount} WP ASSIGNED`
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Relay Failover Re-task Banner */}
      {sarMission?.relay_retasked && sarMission.relay_retask_info && (
        <div
          id="sar-relay-retask-banner"
          className="rounded-lg bg-cyan-950/70 border border-cyan-400/50 px-2.5 py-1.5 text-[10px] text-cyan-200 flex items-center gap-2"
        >
          <Zap className="w-4 h-4 text-cyan-400 shrink-0" />
          <span>
            UAV-2 pulled to A-Mesh Relay —{' '}
            {sarMission.relay_retask_info.unvisited_count} unvisited WP
            reassigned (UAV-1: +
            {sarMission.relay_retask_info.reassigned_counts?.['UAV-1'] ?? 0},
            UAV-3: +
            {sarMission.relay_retask_info.reassigned_counts?.['UAV-3'] ?? 0})
          </span>
        </div>
      )}

      {/* Primary Action Buttons */}
      <div className="grid grid-cols-2 gap-2">
        <button
          id="btn-generate-sar-grid"
          type="button"
          disabled={busy}
          onClick={handleGenerateGrid}
          className="py-2 rounded-lg bg-cyan-950/80 hover:bg-cyan-900/80 border border-cyan-400/60 text-cyan-200 font-bold tracking-wider flex items-center justify-center gap-1.5 cursor-pointer"
        >
          <Compass className="w-3.5 h-3.5" />
          GENERATE GRID
        </button>
        <button
          id="btn-execute-sar-mission"
          type="button"
          disabled={busy}
          onClick={handleExecuteMission}
          className="py-2 rounded-lg bg-emerald-950/80 hover:bg-emerald-900/80 border border-emerald-400/60 text-emerald-200 font-bold tracking-wider flex items-center justify-center gap-1.5 cursor-pointer"
        >
          <Play className="w-3.5 h-3.5" />
          {sarMission?.executing ? 'RESTART SWEEP' : 'EXECUTE MISSION'}
        </button>
      </div>

      {/* Autel V3 Mission KML / WPML (.kmz) I/O */}
      <div className="border-t border-slate-800 pt-2 flex flex-col gap-1.5">
        <div className="flex items-center justify-between text-[10px] text-slate-400">
          <span className="font-semibold tracking-wider">
            AUTEL V3 MISSION I/O ({sarDetections.length} CONTACTS)
          </span>
          <div className="flex items-center gap-1">
            <span className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-700 text-[9px]">
              OGC KML 2.2
            </span>
            <span className="px-1.5 py-0.5 rounded bg-cyan-950/70 border border-cyan-500/40 text-cyan-300 text-[9px]">
              WPML 1.0 KMZ
            </span>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-1.5">
          <label
            htmlFor="input-kml-upload"
            className="py-1.5 px-2 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-200 font-semibold text-[10px] flex items-center justify-center gap-1 cursor-pointer text-center"
          >
            <Upload className="w-3.5 h-3.5 text-slate-400 shrink-0" />
            <span>Import KML/KMZ</span>
            <input
              id="input-kml-upload"
              type="file"
              accept=".kml,.kmz,.xml"
              onChange={handleFileUpload}
              className="hidden"
            />
          </label>

          <button
            id="btn-export-kml"
            type="button"
            disabled={busy}
            onClick={() => triggerDownload('kml')}
            className="py-1.5 px-2 rounded-lg bg-amber-950/60 hover:bg-amber-900/70 border border-amber-500/50 text-amber-200 font-semibold text-[10px] flex items-center justify-center gap-1 cursor-pointer"
          >
            <Download className="w-3.5 h-3.5 text-amber-400 shrink-0" />
            <span>Export Autel KML</span>
          </button>

          <button
            id="btn-export-wpml-kmz"
            type="button"
            disabled={busy}
            onClick={() => triggerDownload('wpml_kmz')}
            className="py-1.5 px-2 rounded-lg bg-cyan-950/70 hover:bg-cyan-900/80 border border-cyan-400/50 text-cyan-200 font-semibold text-[10px] flex items-center justify-center gap-1 cursor-pointer"
          >
            <FileArchive className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
            <span>Export WPML (.kmz)</span>
          </button>
        </div>

        <div
          id="sar-planner-status"
          className="rounded bg-slate-900/90 border border-slate-800 px-2 py-1 text-[10px] text-slate-400 truncate"
        >
          {statusMsg}
        </div>
      </div>

      {/* Recent SAR Thermal Detections List */}
      {sarDetections.length > 0 && (
        <div className="rounded-lg bg-amber-950/40 border border-amber-500/40 p-2 flex flex-col gap-1">
          <div className="flex items-center gap-1.5 text-[10px] font-bold text-amber-300">
            <Flame className="w-3.5 h-3.5 text-amber-400" />
            <span>CAPTURED SAR HEAT CONTACTS ({sarDetections.length})</span>
          </div>
          {sarDetections.slice(-3).map((det) => (
            <div
              key={det.id}
              className="flex items-center justify-between text-[10px] text-amber-200/90 font-mono"
            >
              <span>
                [{det.id}] {det.label} ({det.temp_c.toFixed(1)}°C)
              </span>
              <span>
                {det.lat.toFixed(5)}°N, {det.lon.toFixed(5)}°E
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
