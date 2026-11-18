---
title: A-Mesh Sim 4T
emoji: 🛸
colorFrom: blue
colorTo: cyan
sdk: docker
app_port: 8000
---

# A-Mesh Sim 4T — Autel EVO Max 4T Tactical Swarm & A-Mesh Simulator

**A-Mesh Sim 4T** is a full-stack 3D tactical swarm and **Autel A-Mesh** dual-band (`900MHz / 2.4GHz / 5.2GHz / 5.8GHz`) mesh networking simulator modeled on the **Autel Robotics EVO Max 4T** platform and **Autel Smart Controller V3** HUD.

## Key Capabilities

1. **Dynamic A-Mesh Multi-Hop Relay & LOS Occlusion (`20Hz` Physics & RF Engine)**
   - Procedural 3D tactical ridge and urban valley terrain (`Diablo Ridge` + `East Tactical Valley` + 12 urban structures + 3-span `230kV` catenary HV transmission lines).
   - Real-time 3D ray-marched line-of-sight (LOS) attenuation and automatic **A-Mesh 2-Hop Relay** election (`GCS -> UAV-2 -> UAV-1`) when `UAV-1` crosses behind terrain cover or enters an Electronic Warfare (EW) jamming zone.

2. **Tri-Mode Gimbal Payload (`640×512` Thermal / `8K` Zoom / Wide) & `1200m` Laser Rangefinder (LRF)**
   - Picture-in-Picture (PiP) viewport with **Ironbow**, **White Hot**, and **Black Hot** thermal shaders, `1x–160x` hybrid zoom, live LRF slant-range raycasting, and **A-Mesh Target Pin** broadcasting that automatically slews `UAV-3` overwatch onto the pinned coordinates.

3. **720° All-Around Binocular Fisheye + `60GHz/24GHz` Millimeter-Wave Radar & GNSS-Denied Navigation**
   - Simulates day/night ambient illumination (`5 lux` to `1000+ lux`): when ambient light drops below `15 lux`, optical fisheye degrades (`LOW-LIGHT BLIND`) while `60GHz` mmWave radar continues detecting `12.7mm` high-voltage power lines (`APAS 3D Bypass`).
   - Simulates **RTK-FIX** -> **V-SLAM** -> **IMU-DRIFT** state transitions inside GNSS/RF jamming domes with ghost-drone drift visualization and snap-back recovery.

4. **Flight Data Blackbox Recorder, Interactive Timeline Scrubber & Debrief Export**
   - Continuous `20Hz` ring-buffer recording with automatic mission event markers (`GNSS_JAMMING_ENTER`, `RELAY_FAILOVER`, `LRF_TARGET_PINNED`, `SAR_HEAT_CONTACT`, `VSLAM_LOW_LIGHT_DEGRADED`), interactive `0.5x / 1x / 2x / 4x` 3D replay trails, and one-click CSV/JSON debrief export.

5. **Cooperative 3-UAV Search & Rescue (SAR) Grid Planner, Configurable WGS84 Origin & Autel KML/WPML (`.kmz`) I/O**
   - Configurable real-world **WGS84 Site Origin** (`Latitude`, `Longitude`, `Base Elevation ASL`) with automatic centroid re-centering on external `.kml`/`.kmz` imports.
   - Boustrophedon (lawnmower) sweep generation partitioned across `UAV-1`, `UAV-2`, and `UAV-3` with automatic waypoint reassignment when `UAV-2` is pulled to high-altitude A-Mesh relay duty.
   - Full **OGC KML 2.2 (`.kml`)** and **Autel Explorer V3 WPML 1.0 (`.kmz`)** import & export.

---

## Single-Container Deployment (Hugging Face Spaces / Railway / Render)

The root [`Dockerfile`](Dockerfile) builds the React + Three.js frontend into `/app/static` and serves both the SPA and `/api/*` + `/ws/telemetry` from FastAPI on port `8000` (or `${PORT}`):

```bash
docker build -t amesh-sim-4t .
docker run -p 8000:8000 amesh-sim-4t
```

Health check endpoint: `GET /api/health` -> `{"status": "ok"}`.

---

## Local Development

### Backend (`FastAPI` + `uv`)
```bash
cd backend
uv run pytest -v
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Frontend (`Vite` + `React` + `Three.js`)
```bash
cd frontend
npm install
npm run dev
```
