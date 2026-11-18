import React, { useMemo, useRef, useEffect } from 'react';
import { Canvas, useFrame, ThreeEvent } from '@react-three/fiber';
import { OrbitControls, Line } from '@react-three/drei';
import * as THREE from 'three';
import {
  DroneTelemetry,
  JammingZone,
  PinnedTarget,
  RFLink,
  SarDetection,
  SarMissionState,
  TerrainHeightmap,
  ThermalEntityData,
} from '../types/telemetry';

interface TacticalViewportProps {
  terrain: TerrainHeightmap | null;
  drones: DroneTelemetry[];
  links: RFLink[];
  thermalEntities: ThermalEntityData[];
  pinnedTargets: PinnedTarget[];
  jammingZones: JammingZone[];
  sarMission: SarMissionState | null;
  sarDetections: SarDetection[];
  draftPolygon: [number, number][];
  missionPlannerOpen: boolean;
  show720Bubble: boolean;
  showFovCones: boolean;
  showGrid: boolean;
  cameraPreset: 'OVERVIEW' | 'RIDGE_PROFILE' | 'UAV-1' | 'UAV-2' | 'UAV-3';
  replayTrails?: Record<
    string,
    { true: [number, number, number][]; estimated: [number, number, number][] }
  >;
  onTerrainStakeClick?: (xz: [number, number]) => void;
}

const TerrainMesh3D: React.FC<{
  terrain: TerrainHeightmap;
  missionPlannerOpen: boolean;
  onTerrainStakeClick?: (xz: [number, number]) => void;
}> = ({ terrain, missionPlannerOpen, onTerrainStakeClick }) => {
  const geometry = useMemo(() => {
    const res = terrain.resolution;
    const size = terrain.size_m;
    const geom = new THREE.PlaneGeometry(size, size, res - 1, res - 1);
    geom.rotateX(-Math.PI / 2);

    const posAttr = geom.attributes.position;
    const colors = new Float32Array(posAttr.count * 3);

    for (let zIdx = 0; zIdx < res; zIdx++) {
      const row = terrain.heights[zIdx] || [];
      for (let xIdx = 0; xIdx < res; xIdx++) {
        const idx = zIdx * res + xIdx;
        const h = row[xIdx] ?? 16.0;
        posAttr.setY(idx, h);

        // Tactical elevation coloring
        const t = Math.min(1, Math.max(0, (h - 10) / 130));
        const r = 0.05 + t * 0.22;
        const g = 0.11 + t * 0.28;
        const b = 0.18 + (1 - t) * 0.14;
        colors[idx * 3] = r;
        colors[idx * 3 + 1] = g;
        colors[idx * 3 + 2] = b;
      }
    }
    geom.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    geom.computeVertexNormals();
    return geom;
  }, [terrain]);

  const handlePointerDown = (e: ThreeEvent<PointerEvent>) => {
    if (!missionPlannerOpen || !onTerrainStakeClick) return;
    e.stopPropagation();
    const pt = e.point;
    onTerrainStakeClick([Math.round(pt.x * 10) / 10, Math.round(pt.z * 10) / 10]);
  };

  return (
    <group>
      <mesh geometry={geometry} onPointerDown={handlePointerDown} receiveShadow>
        <meshStandardMaterial
          vertexColors
          roughness={0.85}
          metalness={0.15}
        />
      </mesh>
      <mesh geometry={geometry}>
        <meshBasicMaterial
          color="#22d3ee"
          wireframe
          transparent
          opacity={0.08}
        />
      </mesh>
    </group>
  );
};

const CameraRig: React.FC<{
  preset: 'OVERVIEW' | 'RIDGE_PROFILE' | 'UAV-1' | 'UAV-2' | 'UAV-3';
  drones: DroneTelemetry[];
}> = ({ preset, drones }) => {
  const controlsRef = useRef<any>(null);

  useEffect(() => {
    if (!controlsRef.current) return;
    const cam = controlsRef.current.object as THREE.PerspectiveCamera;
    if (preset === 'OVERVIEW') {
      cam.position.set(40, 290, 380);
      controlsRef.current.target.set(30, 35, 0);
    } else if (preset === 'RIDGE_PROFILE') {
      cam.position.set(-40, 145, 420);
      controlsRef.current.target.set(-30, 65, 0);
    }
    controlsRef.current.update();
  }, [preset]);

  useFrame(() => {
    if (!controlsRef.current) return;
    if (preset === 'UAV-1' || preset === 'UAV-2' || preset === 'UAV-3') {
      const targetDrone = drones.find((d) => d.id === preset);
      if (targetDrone) {
        const [x, y, z] = targetDrone.true_position;
        controlsRef.current.target.lerp(new THREE.Vector3(x, y, z), 0.15);
      }
    }
  });

  return <OrbitControls ref={controlsRef} makeDefault maxPolarAngle={Math.PI * 0.48} />;
};

export const TacticalViewport: React.FC<TacticalViewportProps> = ({
  terrain,
  drones,
  links,
  thermalEntities,
  pinnedTargets,
  jammingZones,
  sarMission,
  sarDetections,
  draftPolygon,
  missionPlannerOpen,
  show720Bubble,
  showFovCones,
  showGrid,
  cameraPreset,
  replayTrails,
  onTerrainStakeClick,
}) => {
  const polyPoints3D = useMemo(() => {
    const poly =
      draftPolygon.length >= 2
        ? draftPolygon
        : sarMission?.polygon_xz || [];
    if (poly.length < 2) return [];
    const pts = poly.map(([x, z]) => [x, 28, z] as [number, number, number]);
    if (poly.length >= 3) {
      pts.push([poly[0][0], 28, poly[0][1]]);
    }
    return pts;
  }, [draftPolygon, sarMission]);

  return (
    <div id="tactical-3d-viewport" className="w-full h-full relative bg-[#050911]">
      <Canvas
        camera={{ position: [40, 290, 380], fov: 50, near: 1, far: 3000 }}
        gl={{ antialias: true }}
      >
        <color attach="background" args={['#050911']} />
        <fog attach="fog" args={['#050911', 650, 1850]} />
        <ambientLight intensity={0.65} />
        <directionalLight position={[180, 360, 140]} intensity={1.15} />

        <CameraRig preset={cameraPreset} drones={drones} />

        {showGrid && (
          <gridHelper
            args={[1000, 40, '#0e7490', '#0f172a']}
            position={[0, 8.2, 0]}
          />
        )}

        {terrain && (
          <TerrainMesh3D
            terrain={terrain}
            missionPlannerOpen={missionPlannerOpen}
            onTerrainStakeClick={onTerrainStakeClick}
          />
        )}

        {/* GCS-GIVOT-EDEN Hilltop Command Station */}
        {terrain && (
          <group position={terrain.gcs_position}>
            <mesh position={[0, 4, 0]}>
              <cylinderGeometry args={[1.5, 4, 12, 8]} />
              <meshStandardMaterial color="#10b981" emissive="#059669" emissiveIntensity={0.6} />
            </mesh>
          </group>
        )}

        {/* Giv'ot Eden Outer Security Perimeter Fence Line */}
        {terrain?.perimeter_fence_xz && terrain.perimeter_fence_xz.length >= 3 && (
          <Line
            points={[
              ...terrain.perimeter_fence_xz.map(([x, z]) => [x, 34, z] as [number, number, number]),
              [terrain.perimeter_fence_xz[0][0], 34, terrain.perimeter_fence_xz[0][1]],
            ]}
            color="#10b981"
            lineWidth={1.5}
            dashed
            dashSize={6}
            gapSize={4}
          />
        )}

        {/* Route 375 / Emek HaEla Valley Road Corridor */}
        {terrain?.valley_road_xz && terrain.valley_road_xz.length >= 2 && (
          <Line
            points={terrain.valley_road_xz.map(([x, z]) => [x, 16.5, z] as [number, number, number])}
            color="#94a3b8"
            lineWidth={3.5}
          />
        )}

        {/* HaEla Limestone Ridge Cliff Outcrops */}
        {terrain?.cliff_outcrops?.map((c) => (
          <mesh
            key={c.id}
            position={[c.x, c.base_elevation + c.height * 0.45, c.z]}
          >
            <coneGeometry args={[c.radius, c.height, 7]} />
            <meshStandardMaterial
              color="#334155"
              roughness={0.92}
              metalness={0.08}
            />
          </mesh>
        ))}

        {/* Giv'ot Eden & Emek HaEla Structures */}
        {terrain?.buildings.map((b) => (
          <mesh
            key={b.id}
            position={[b.x, b.base_elevation + b.height / 2, b.z]}
          >
            <boxGeometry args={[b.width, b.height, b.depth]} />
            <meshStandardMaterial
              color="#1e293b"
              emissive="#0f172a"
              roughness={0.7}
            />
          </mesh>
        ))}

        {/* HV Transmission Pylons & 15mm Catenary Power Lines */}
        {terrain?.pylons.map((p) => (
          <mesh
            key={p.id}
            position={[p.x, p.base_elevation + p.height / 2, p.z]}
          >
            <cylinderGeometry args={[0.8, 2.5, p.height, 4]} />
            <meshStandardMaterial color="#f59e0b" wireframe />
          </mesh>
        ))}
        {terrain?.power_lines.map((span) =>
          span.points.length >= 2 ? (
            <Line
              key={span.id}
              points={span.points}
              color="#fbbf24"
              lineWidth={1.6}
            />
          ) : null
        )}

        {/* Thermal Entities */}
        {thermalEntities.map((ent) => (
          <mesh
            key={ent.id}
            position={[
              ent.position[0],
              ent.position[1] + ent.height_m * 0.5,
              ent.position[2],
            ]}
          >
            <boxGeometry args={[ent.radius_m, ent.height_m, ent.radius_m]} />
            <meshStandardMaterial
              color="#f97316"
              emissive="#ea580c"
              emissiveIntensity={0.85}
            />
          </mesh>
        ))}

        {/* GNSS Jamming Domes */}
        {jammingZones.map((jz) => (
          <mesh key={jz.id} position={jz.position}>
            <sphereGeometry args={[jz.radius_m, 24, 16]} />
            <meshBasicMaterial
              color="#f43f5e"
              transparent
              opacity={0.14}
              wireframe
            />
          </mesh>
        ))}

        {/* Pinned LRF Targets */}
        {pinnedTargets.map((pin) => (
          <group key={pin.id} position={pin.position}>
            <mesh position={[0, 8, 0]}>
              <cylinderGeometry args={[0.6, 0.6, 16, 12]} />
              <meshBasicMaterial color="#f43f5e" />
            </mesh>
            <mesh position={[0, 17, 0]}>
              <octahedronGeometry args={[3.2]} />
              <meshBasicMaterial color="#fb7185" />
            </mesh>
          </group>
        ))}

        {/* SAR Polygon & Partitioned Lawnmower Paths */}
        {polyPoints3D.length >= 2 && (
          <Line points={polyPoints3D} color="#22d3ee" lineWidth={2.5} />
        )}
        {(draftPolygon.length > 0
          ? draftPolygon
          : sarMission?.polygon_xz || []
        ).map(([x, z], idx) => (
          <mesh key={`stake-${idx}`} position={[x, 26, z]}>
            <cylinderGeometry args={[1.4, 1.4, 24, 12]} />
            <meshBasicMaterial color="#06b6d4" />
          </mesh>
        ))}

        {sarMission &&
          (['UAV-1', 'UAV-2', 'UAV-3'] as const).map((uid) => {
            const wps = sarMission.partitions?.[uid]?.waypoints || [];
            if (wps.length < 2) return null;
            const col =
              uid === 'UAV-1'
                ? '#10b981'
                : uid === 'UAV-2'
                ? '#06b6d4'
                : '#a855f7';
            return (
              <Line
                key={`sar-path-${uid}`}
                points={wps}
                color={col}
                lineWidth={2.2}
              />
            );
          })}

        {/* SAR Heat Detections Beacons */}
        {sarDetections.map((det) => (
          <group key={det.id} position={det.position}>
            <mesh position={[0, 12, 0]}>
              <sphereGeometry args={[3.8, 16, 16]} />
              <meshBasicMaterial color="#f59e0b" />
            </mesh>
          </group>
        ))}

        {/* A-Mesh RF Links */}
        {links.map((lnk) => {
          const color = lnk.active_relay_hop
            ? '#22d3ee'
            : lnk.usable
            ? '#10b981'
            : '#f43f5e';
          return (
            <Line
              key={lnk.id}
              points={[lnk.source_pos, lnk.target_pos]}
              color={color}
              lineWidth={lnk.active_relay_hop ? 2.6 : 1.4}
              dashed={!lnk.usable}
              dashSize={8}
              gapSize={6}
            />
          );
        })}

        {/* Replay Trails */}
        {replayTrails &&
          Object.entries(replayTrails).map(([uid, tr]) => (
            <group key={`trail-${uid}`}>
              {tr.true.length >= 2 && (
                <Line points={tr.true} color="#22d3ee" lineWidth={2.2} />
              )}
              {tr.estimated.length >= 2 && (
                <Line
                  points={tr.estimated}
                  color="#f59e0b"
                  lineWidth={1.6}
                  dashed
                  dashSize={5}
                  gapSize={4}
                />
              )}
            </group>
          ))}

        {/* UAV Airframes & 720° Perception Bubbles */}
        {drones.map((d) => {
          const color =
            d.id === 'UAV-1'
              ? '#10b981'
              : d.id === 'UAV-2'
              ? '#06b6d4'
              : '#a855f7';
          return (
            <group key={d.id}>
              <group position={d.true_position}>
                <mesh>
                  <octahedronGeometry args={[3.5, 0]} />
                  <meshStandardMaterial
                    color={color}
                    emissive={color}
                    emissiveIntensity={0.6}
                  />
                </mesh>

                {show720Bubble && (
                  <>
                    {d.perception_720?.fisheye_status === 'ACTIVE' && (
                      <mesh>
                        <sphereGeometry args={[40, 16, 12]} />
                        <meshBasicMaterial
                          color="#10b981"
                          wireframe
                          transparent
                          opacity={0.08}
                        />
                      </mesh>
                    )}
                    <mesh>
                      <sphereGeometry args={[50, 16, 12]} />
                      <meshBasicMaterial
                        color={
                          d.perception_720?.fisheye_status === 'ACTIVE'
                            ? '#38bdf8'
                            : '#f59e0b'
                        }
                        wireframe
                        transparent
                        opacity={0.07}
                      />
                    </mesh>
                  </>
                )}

                {showFovCones && d.lrf?.target_pos && (
                  <Line
                    points={[[0, 0, 0], [
                      d.lrf.target_pos[0] - d.true_position[0],
                      d.lrf.target_pos[1] - d.true_position[1],
                      d.lrf.target_pos[2] - d.true_position[2],
                    ]]}
                    color="#fb7185"
                    lineWidth={1.2}
                    dashed
                    dashSize={4}
                    gapSize={4}
                  />
                )}
              </group>

              {/* Estimated Ghost Position when drifting */}
              {d.position_drift_m > 0.25 && (
                <mesh position={d.estimated_position}>
                  <octahedronGeometry args={[3.2, 0]} />
                  <meshBasicMaterial color="#f59e0b" wireframe />
                </mesh>
              )}
            </group>
          );
        })}
      </Canvas>
    </div>
  );
};
