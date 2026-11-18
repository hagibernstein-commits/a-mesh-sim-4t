import React, { useState, useEffect } from 'react';
import { Activity, ChevronUp, ChevronDown, Play, Pause, Download } from 'lucide-react';
import { TelemetrySnapshot } from '../types/telemetry';

interface FlightBlackboxDrawerProps {
  simTime: number;
  totalFrames: number;
  replayMode: boolean;
  onToggleReplayMode: (replay: boolean) => void;
  onReplayFrameLoaded: (snapshot: TelemetrySnapshot | null) => void;
}

export const FlightBlackboxDrawer: React.FC<FlightBlackboxDrawerProps> = ({
  simTime,
  totalFrames,
  replayMode,
  onToggleReplayMode,
  onReplayFrameLoaded,
}) => {
  const [expanded, setExpanded] = useState<boolean>(false);
  const [summary, setSummary] = useState<any>(null);
  const [scrubFrame, setScrubFrame] = useState<number>(0);
  const [playingReplay, setPlayingReplay] = useState<boolean>(false);
  const [speed, setSpeed] = useState<number>(1);

  useEffect(() => {
    const fetchSummary = async () => {
      try {
        const res = await fetch('/api/blackbox/summary');
        if (res.ok) {
          const data = await res.json();
          setSummary(data);
          if (!replayMode) {
            setScrubFrame(Math.max(0, (data.total_frames || 1) - 1));
          }
        }
      } catch {
        // ignore transient network errors
      }
    };
    fetchSummary();
    const timer = setInterval(fetchSummary, 1500);
    return () => clearInterval(timer);
  }, [replayMode]);

  const loadReplayFrame = async (idx: number) => {
    setScrubFrame(idx);
    if (!replayMode) {
      onToggleReplayMode(true);
    }
    const res = await fetch(`/api/blackbox/frame/${idx}`);
    if (res.ok) {
      const snap = await res.json();
      onReplayFrameLoaded(snap);
    }
  };

  useEffect(() => {
    if (!replayMode || !playingReplay) return;
    const maxF = Math.max(1, (summary?.total_frames || totalFrames) - 1);
    const timer = setInterval(() => {
      setScrubFrame((prev) => {
        const next = Math.min(maxF, prev + Math.max(1, Math.round(speed * 2)));
        loadReplayFrame(next);
        return next;
      });
    }, 150);
    return () => clearInterval(timer);
  }, [replayMode, playingReplay, speed, summary?.total_frames, totalFrames]);

  const maxFrame = Math.max(1, (summary?.total_frames || totalFrames) - 1);
  const events: any[] = summary?.events || [];

  return (
    <div
      id="flight-blackbox-drawer"
      className="pointer-events-auto w-full bg-slate-950/95 border-t border-slate-800 px-4 py-2 text-xs flex flex-col gap-2"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <button
            id="btn-toggle-blackbox-drawer"
            type="button"
            onClick={() => setExpanded((prev) => !prev)}
            className="px-2.5 py-1 rounded bg-slate-900 hover:bg-slate-800 border border-slate-700 text-cyan-300 font-bold flex items-center gap-1.5 cursor-pointer"
          >
            <Activity className="w-3.5 h-3.5" />
            <span>FLIGHT BLACKBOX {totalFrames} FRM</span>
            {expanded ? (
              <ChevronDown className="w-3.5 h-3.5" />
            ) : (
              <ChevronUp className="w-3.5 h-3.5" />
            )}
          </button>

          <button
            id="btn-blackbox-mode-toggle"
            type="button"
            onClick={() => {
              const next = !replayMode;
              onToggleReplayMode(next);
              if (!next) {
                setPlayingReplay(false);
                onReplayFrameLoaded(null);
              } else {
                loadReplayFrame(scrubFrame);
              }
            }}
            className={`px-2.5 py-1 rounded font-bold border cursor-pointer ${
              replayMode
                ? 'bg-amber-950/80 border-amber-500/60 text-amber-300'
                : 'bg-emerald-950/80 border-emerald-500/60 text-emerald-300'
            }`}
          >
            {replayMode ? 'REPLAY MODE (PAUSED LIVE)' : 'LIVE 20Hz REC'}
          </button>

          <button
            id="btn-blackbox-play-replay"
            type="button"
            onClick={() => {
              if (!replayMode) {
                onToggleReplayMode(true);
                loadReplayFrame(Math.max(0, scrubFrame - 20));
              }
              setPlayingReplay((p) => !p);
            }}
            className="px-2.5 py-1 rounded bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-200 flex items-center gap-1 cursor-pointer"
          >
            {playingReplay ? (
              <Pause className="w-3 h-3" />
            ) : (
              <Play className="w-3 h-3" />
            )}
            <span>{playingReplay ? 'PAUSE REPLAY' : 'PLAY REPLAY'}</span>
          </button>

          <div className="flex items-center gap-1">
            {[0.5, 1, 2, 4].map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setSpeed(s)}
                className={`px-1.5 py-0.5 rounded text-[10px] border cursor-pointer ${
                  speed === s
                    ? 'bg-cyan-500/20 border-cyan-400 text-cyan-300 font-bold'
                    : 'bg-slate-900 border-slate-800 text-slate-400'
                }`}
              >
                {s}x
              </button>
            ))}
          </div>
        </div>

        <div className="font-mono text-[11px] text-slate-300">
          T+{simTime.toFixed(1)}s [FRM #{scrubFrame}/{maxFrame}]
        </div>

        <div className="flex items-center gap-2">
          <a
            id="btn-export-csv-debrief"
            href="/api/blackbox/export/csv"
            download="amesh_sim_4t_debrief.csv"
            className="px-2.5 py-1 rounded bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-200 flex items-center gap-1"
          >
            <Download className="w-3.5 h-3.5 text-cyan-400" />
            <span>Export CSV Debrief</span>
          </a>
          <a
            id="btn-export-json-blackbox"
            href="/api/blackbox/export/json"
            download="amesh_sim_4t_debrief.json"
            className="px-2.5 py-1 rounded bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-200 flex items-center gap-1"
          >
            <Download className="w-3.5 h-3.5 text-amber-400" />
            <span>Export JSON Blackbox</span>
          </a>
        </div>
      </div>

      {/* Timeline Scrubber with MissionEvent Markers */}
      <div className="relative h-5 flex items-center">
        <input
          id="slider-blackbox-scrubber"
          type="range"
          min={0}
          max={maxFrame}
          value={Math.min(scrubFrame, maxFrame)}
          onChange={(e) => loadReplayFrame(Number(e.target.value))}
          className="w-full accent-cyan-400 cursor-pointer z-10"
        />
        {events.map((ev) => {
          const pct = Math.min(
            99.5,
            Math.max(0.5, ((ev.frame_index || 0) / maxFrame) * 100)
          );
          return (
            <button
              key={ev.id}
              id={`event-marker-${ev.id}`}
              type="button"
              title={`[${ev.event_type}] T+${ev.sim_time}s (${ev.drone_id}): ${ev.message}`}
              onClick={() => loadReplayFrame(ev.frame_index || 0)}
              style={{ left: `${pct}%` }}
              className="blackbox-event-marker absolute top-0 bottom-0 -translate-x-1/2 w-2.5 h-2.5 rounded-full bg-amber-400 border border-slate-950 z-20 cursor-pointer"
            />
          );
        })}
      </div>

      {expanded && (
        <div className="grid grid-cols-3 gap-3 pt-1 border-t border-slate-800 text-[10px]">
          <div className="rounded bg-slate-900/80 border border-slate-800 p-2">
            <div className="font-bold text-cyan-300 mb-1">
              A-MESH RSSI (dBm) TELEMETRY
            </div>
            <div className="text-slate-400">
              Recorded frames: {summary?.total_frames || totalFrames} • Active
              Events: {events.length}
            </div>
          </div>
          <div className="rounded bg-slate-900/80 border border-slate-800 p-2">
            <div className="font-bold text-amber-300 mb-1">
              RTK / V-SLAM / IMU DRIFT (m)
            </div>
            <div className="text-slate-400">
              WGS84 Origin: {summary?.geodetic_origin?.lat?.toFixed(5)}°N,{' '}
              {summary?.geodetic_origin?.lon?.toFixed(5)}°E
            </div>
          </div>
          <div className="rounded bg-slate-900/80 border border-slate-800 p-2 max-h-24 overflow-y-auto">
            <div className="font-bold text-emerald-300 mb-1">
              RECENT MISSION EVENTS
            </div>
            {events.slice(-4).map((ev) => (
              <div key={ev.id} className="text-slate-300 truncate">
                [{ev.id}] {ev.message}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
