import React, { useEffect, useState, useRef, useCallback } from 'react';
import {
  GeodeticOrigin,
  SarMissionState,
  TelemetrySnapshot,
  TerrainHeightmap,
} from './types/telemetry';
import { TacticalViewport } from './components/TacticalViewport';
import { SmartControllerHUD } from './components/SmartControllerHUD';
import { FlightBlackboxDrawer } from './components/FlightBlackboxDrawer';

export const App: React.FC = () => {
  const [terrain, setTerrain] = useState<TerrainHeightmap | null>(null);
  const [liveSnapshot, setLiveSnapshot] = useState<TelemetrySnapshot | null>(null);
  const [replaySnapshot, setReplaySnapshot] = useState<TelemetrySnapshot | null>(null);
  const [replayMode, setReplayMode] = useState<boolean>(false);

  const [selectedDroneId, setSelectedDroneId] = useState<string>('UAV-1');
  const [missionPlannerOpen, setMissionPlannerOpen] = useState<boolean>(false);
  const [show720Bubble, setShow720Bubble] = useState<boolean>(true);
  const [showFovCones, setShowFovCones] = useState<boolean>(true);
  const [showGrid, setShowGrid] = useState<boolean>(true);
  const [cameraPreset, setCameraPreset] = useState<
    'OVERVIEW' | 'RIDGE_PROFILE' | 'UAV-1' | 'UAV-2' | 'UAV-3'
  >('OVERVIEW');

  const [draftPolygon, setDraftPolygon] = useState<[number, number][]>([
    [60, -70],
    [220, -70],
    [220, 70],
    [60, 70],
  ]);
  const [polygonLocked, setPolygonLocked] = useState<boolean>(true);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    fetch('/api/terrain')
      .then((r) => r.json())
      .then((data: TerrainHeightmap) => setTerrain(data))
      .catch(() => {});

    fetch('/api/state')
      .then((r) => r.json())
      .then((data: TelemetrySnapshot) => setLiveSnapshot(data))
      .catch(() => {});
  }, []);

  useEffect(() => {
    let closed = false;
    let ws: WebSocket | null = null;
    const timer = window.setTimeout(() => {
      if (closed) return;
      const wsUrl = `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/ws/telemetry`;
      ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onmessage = (evt) => {
        if (closed) return;
        try {
          const snap: TelemetrySnapshot = JSON.parse(evt.data);
          setLiveSnapshot(snap);
        } catch {
          // ignore malformed frame
        }
      };
    }, 25);

    return () => {
      closed = true;
      window.clearTimeout(timer);
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    };
  }, []);

  const activeSnapshot = replayMode && replaySnapshot ? replaySnapshot : liveSnapshot;

  const handleControlAction = useCallback(async (body: any) => {
    const res = await fetch('/api/control', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (res.ok) {
      const snap = await res.json();
      setLiveSnapshot(snap);
    }
  }, []);

  const handleGimbalChange = useCallback(async (params: any) => {
    await fetch('/api/gimbal', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
  }, []);

  const handlePinTarget = useCallback(async (droneId: string) => {
    await fetch('/api/pin-target', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ drone_id: droneId }),
    });
  }, []);

  const handleTerrainStakeClick = useCallback(
    (xz: [number, number]) => {
      setDraftPolygon((prev) => {
        if (polygonLocked) {
          setPolygonLocked(false);
          return [xz];
        }
        const next = [...prev, xz];
        if (next.length >= 4) {
          setPolygonLocked(true);
        }
        return next;
      });
    },
    [polygonLocked]
  );

  const handleUpdateDraftPolygon = useCallback(
    (pts: [number, number][], locked: boolean) => {
      setDraftPolygon(pts);
      setPolygonLocked(locked);
    },
    []
  );

  const handleMissionUpdated = useCallback((mission: SarMissionState) => {
    setLiveSnapshot((prev) => (prev ? { ...prev, sar_mission: mission } : prev));
  }, []);

  const handleOriginUpdated = useCallback((origin: GeodeticOrigin) => {
    setLiveSnapshot((prev) =>
      prev ? { ...prev, geodetic_origin: origin } : prev
    );
  }, []);

  return (
    <div className="relative w-full h-[100dvh] overflow-hidden bg-[#050911] select-none">
      <TacticalViewport
        terrain={terrain}
        drones={activeSnapshot?.drones || []}
        links={activeSnapshot?.links || []}
        thermalEntities={activeSnapshot?.thermal_entities || []}
        pinnedTargets={activeSnapshot?.pinned_targets || []}
        jammingZones={activeSnapshot?.jamming_zones || []}
        sarMission={activeSnapshot?.sar_mission || null}
        sarDetections={activeSnapshot?.sar_detections || []}
        draftPolygon={draftPolygon}
        missionPlannerOpen={missionPlannerOpen}
        show720Bubble={show720Bubble}
        showFovCones={showFovCones}
        showGrid={showGrid}
        cameraPreset={cameraPreset}
        replayTrails={activeSnapshot?.replay_trails}
        onTerrainStakeClick={handleTerrainStakeClick}
      />

      <SmartControllerHUD
        simTime={activeSnapshot?.sim_time ?? 0}
        paused={activeSnapshot?.paused ?? false}
        ambientLux={activeSnapshot?.ambient_lux ?? 650}
        windSpeedMs={activeSnapshot?.wind_speed_ms ?? 4.5}
        ewJammingActive={activeSnapshot?.ew_jamming_active ?? false}
        geodeticOrigin={
          activeSnapshot?.geodetic_origin || terrain?.geodetic_origin || null
        }
        gcsPosition={
          activeSnapshot?.gcs_position ||
          terrain?.gcs_position || [-215.0, 42.0, 12.0]
        }
        drones={activeSnapshot?.drones || []}
        links={activeSnapshot?.links || []}
        meshSummary={
          activeSnapshot?.mesh_summary || {
            topology_mode: 'DIRECT_GCS_LOS',
            active_route: ['GCS', 'UAV-1'],
            relay_bridged: false,
            uav1_direct_los: true,
          }
        }
        thermalEntities={activeSnapshot?.thermal_entities || []}
        sarMission={activeSnapshot?.sar_mission || null}
        sarDetections={activeSnapshot?.sar_detections || []}
        eventLog={activeSnapshot?.event_log || []}
        selectedDroneId={selectedDroneId}
        missionPlannerOpen={missionPlannerOpen}
        show720Bubble={show720Bubble}
        showFovCones={showFovCones}
        showGrid={showGrid}
        cameraPreset={cameraPreset}
        draftPolygon={draftPolygon}
        polygonLocked={polygonLocked}
        onSelectDrone={setSelectedDroneId}
        onToggleMissionPlanner={() => setMissionPlannerOpen((p) => !p)}
        onToggle720Bubble={() => setShow720Bubble((p) => !p)}
        onToggleFovCones={() => setShowFovCones((p) => !p)}
        onToggleGrid={() => setShowGrid((p) => !p)}
        onSelectCameraPreset={setCameraPreset}
        onControlAction={handleControlAction}
        onGimbalChange={handleGimbalChange}
        onPinTarget={handlePinTarget}
        onUpdateDraftPolygon={handleUpdateDraftPolygon}
        onMissionUpdated={handleMissionUpdated}
        onOriginUpdated={handleOriginUpdated}
      />

      <div className="absolute bottom-0 inset-x-0 z-30">
        <FlightBlackboxDrawer
          simTime={activeSnapshot?.sim_time ?? 0}
          totalFrames={activeSnapshot?.blackbox_frames ?? 1}
          replayMode={replayMode}
          onToggleReplayMode={setReplayMode}
          onReplayFrameLoaded={setReplaySnapshot}
        />
      </div>
    </div>
  );
};

export default App;
