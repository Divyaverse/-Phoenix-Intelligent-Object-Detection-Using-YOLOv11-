import React, { useEffect, useState } from 'react';
import type { 
  RouteRecommendationResponse, 
  IncidentResponse, 
  FloorplanModelResponse,
  SpatialRegionSchema,
  NavigationNodeSchema,
  NavigationEdgeSchema,
} from '../types/phoenix';
import { ApiClient } from '../services/apiClient';

interface EvacuationMapProps {
  buildingId?: string;
  floorId?: string;
  route: RouteRecommendationResponse | null;
  incident: IncidentResponse | null;
  floorplan?: FloorplanModelResponse | null;
  nodeRisks?: Record<string, number>;
  origin?: string;
  userRole?: string;
  onSelectNode?: (nodeId: string) => void;
}

export const EvacuationMap: React.FC<EvacuationMapProps> = ({ 
  buildingId = 'bldg-hq-01',
  floorId = 'fl-01',
  route, 
  incident,
  floorplan: externalFloorplan,
  nodeRisks = {},
  origin,
  userRole,
  onSelectNode,
}) => {
  const [floorplan, setFloorplan] = useState<FloorplanModelResponse | null>(externalFloorplan || null);
  const [, setLoading] = useState<boolean>(!externalFloorplan);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);

  useEffect(() => {
    if (externalFloorplan) {
      setFloorplan(externalFloorplan);
      return;
    }

    let isMounted = true;
    ApiClient.getFloorplan(buildingId, floorId)
      .then((fp) => {
        if (isMounted && fp) {
          setFloorplan(fp);
        }
      })
      .catch((err) => {
        console.warn('Could not fetch dynamic floorplan:', err);
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [buildingId, floorId, externalFloorplan]);

  // Coordinate bounds
  const rawWidth = floorplan?.width_meters || floorplan?.physical_width_meters || 32;
  const rawHeight = floorplan?.height_meters || floorplan?.physical_height_meters || 30;
  const hasDimensions = Boolean(floorplan?.width_meters && floorplan?.height_meters);

  // SVG viewBox with breathing room padding
  const padX = 2.0;
  const padY = 2.0;
  const vbX = -padX;
  const vbY = -padY;
  const vbW = rawWidth + padX * 2;
  const vbH = rawHeight + padY * 2;

  const nodes: NavigationNodeSchema[] = floorplan?.nodes || [];
  const edges: NavigationEdgeSchema[] = floorplan?.edges || [];
  const regions: SpatialRegionSchema[] = floorplan?.regions || [];

  const isEdgeInRoute = (from: string, to: string) => {
    if (!route || !route.path_nodes) return false;
    const path = route.path_nodes;
    for (let i = 0; i < path.length - 1; i++) {
      if ((path[i] === from && path[i + 1] === to) || (path[i] === to && path[i + 1] === from)) {
        return true;
      }
    }
    return false;
  };

  const isHazardActive = Boolean(incident && incident.status !== 'CLOSED' && incident.status !== 'RESOLVED');

  const getRegionFill = (regionType: string) => {
    switch (regionType) {
      case 'ROOM':
        return 'rgba(30, 41, 59, 0.4)';
      case 'CORRIDOR':
        return 'rgba(15, 23, 42, 0.7)';
      case 'LOBBY':
        return 'rgba(24, 36, 60, 0.45)';
      case 'EXIT':
        return 'rgba(16, 185, 129, 0.15)';
      case 'STAIRWELL':
        return 'rgba(51, 65, 85, 0.35)';
      default:
        return 'rgba(255, 255, 255, 0.03)';
    }
  };

  const provenance = floorplan?.provenance || 'MEASURED';

  // Format clean shortened label for map display
  const getNodeShortLabel = (n: NavigationNodeSchema) => {
    if (n.node_id === 'exit_south') return 'EXIT SOUTH';
    if (n.node_id === 'exit_north') return 'EXIT NORTH';
    if (n.node_id === 'node_corridor_south') return 'South Corridor';
    if (n.node_id === 'node_corridor_mid') return 'Central Junction';
    if (n.node_id === 'node_corridor_north') return 'North Corridor';
    if (n.node_id === 'node_east_alcove') return 'East Office (Hazard Origin)';
    if (n.node_id === 'node_west_suites') return 'West Suites';
    return n.label?.split('(')[0].trim() || n.name || n.node_id;
  };

  // Smart label placement offsets (to ensure zero text collisions)
  const getNodeLabelPos = (n: NavigationNodeSchema): { x: number; y: number; align: 'middle' | 'end' | 'start' } => {
    if (n.node_id === 'exit_south') {
      return { x: n.x, y: n.y - 1.4, align: 'middle' };
    }
    if (n.node_id === 'node_corridor_south') {
      return { x: n.x, y: n.y + 1.8, align: 'middle' };
    }
    if (n.node_id === 'node_corridor_mid') {
      return { x: n.x - 2.8, y: n.y - 0.2, align: 'end' };
    }
    if (n.node_id === 'node_corridor_north') {
      return { x: n.x - 2.8, y: n.y, align: 'end' };
    }
    if (n.node_id === 'exit_north') {
      return { x: n.x, y: n.y + 1.8, align: 'middle' };
    }
    if (n.node_id === 'node_east_alcove') {
      return { x: n.x, y: n.y + 2.0, align: 'middle' };
    }
    if (n.node_id === 'node_west_suites') {
      return { x: n.x, y: n.y + 2.0, align: 'middle' };
    }
    return { x: n.x, y: n.y + 1.6, align: 'middle' };
  };

  // Region text position tweaks to avoid corridor overlap
  const getRegionTextPos = (r: SpatialRegionSchema) => {
    const pts = r.polygon_points || r.polygon || [];
    const center = r.centroid || r.center || (pts.length > 0 ? pts[0] : { x: 0, y: 0 });
    if (r.region_id === 'reg_corridor_main' || r.name.toLowerCase().includes('corridor')) {
      return { x: center.x, y: 9.8 }; // Offset from node_corridor_mid (16, 14)
    }
    if (r.region_id === 'reg_west_suites' || r.name.toLowerCase().includes('west')) {
      return { x: center.x, y: 21.0 };
    }
    if (r.region_id === 'reg_east_alcove' || r.name.toLowerCase().includes('east')) {
      return { x: center.x, y: 20.8 };
    }
    return center;
  };

  const hoveredNode = nodes.find((n) => n.node_id === hoveredNodeId);

  if (nodes.length === 0) {
    return (
      <div
        style={{
          background: '#13161c',
          borderRadius: '6px',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          padding: '24px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          textAlign: 'center',
          minHeight: '280px',
          height: '100%',
          boxSizing: 'border-box',
        }}
      >
        <div style={{ width: '40px', height: '40px', borderRadius: '50%', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#f87171', fontSize: '18px', marginBottom: '12px' }}>
          📍
        </div>
        <div style={{ fontSize: '14px', fontWeight: 700, color: '#fca5a5', marginBottom: '6px' }}>
          Spatial Mapping Calibration Initializing
        </div>
        <p style={{ fontSize: '12px', color: '#a1a1aa', margin: '0 0 14px 0', maxWidth: '380px', lineHeight: 1.5 }}>
          Retrieving verified architectural floorplan coordinates and corridor navigation graph...
        </p>
      </div>
    );
  }

  return (
    <div
      style={{
        background: '#13161c',
        borderRadius: '6px',
        border: '1px solid rgba(255, 255, 255, 0.1)',
        padding: '14px',
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        boxSizing: 'border-box',
        boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
      }}
    >
      {/* Map Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '10px', fontWeight: 800, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.8px' }}>
              SPATIAL EVACUATION TOPOLOGY
            </span>
            <span
              style={{
                fontSize: '9px',
                fontWeight: 700,
                padding: '2px 7px',
                borderRadius: '3px',
                background: provenance === 'CALIBRATED' || provenance === 'MEASURED' ? 'rgba(34, 197, 94, 0.15)' : 'rgba(148, 163, 184, 0.15)',
                color: provenance === 'CALIBRATED' || provenance === 'MEASURED' ? '#4ade80' : '#94a3b8',
                border: `1px solid ${provenance === 'CALIBRATED' || provenance === 'MEASURED' ? 'rgba(34, 197, 94, 0.3)' : 'rgba(148, 163, 184, 0.2)'}`,
              }}
            >
              PROVENANCE: {provenance}
            </span>
            {userRole && (
              <span style={{ fontSize: '9px', fontWeight: 700, color: '#38bdf8', background: 'rgba(56, 189, 248, 0.12)', border: '1px solid rgba(56, 189, 248, 0.25)', padding: '2px 6px', borderRadius: '3px' }}>
                {userRole} VIEW
              </span>
            )}
          </div>
          <h4 style={{ margin: '3px 0 0', fontSize: '14px', color: '#f4f4f5', fontWeight: 700 }}>
            {floorplan?.name || 'Corporate Central Corridor & Offices'} · {hasDimensions ? `${rawWidth.toFixed(1)}m × ${rawHeight.toFixed(1)}m (Ground-Calibrated)` : '32.0m × 30.0m'}
          </h4>
        </div>

        <div style={{ fontSize: '11px', color: '#a1a1aa', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span
            style={{
              padding: '3px 8px',
              borderRadius: '3px',
              backgroundColor: isHazardActive ? 'rgba(220, 38, 38, 0.2)' : 'rgba(34, 197, 94, 0.15)',
              color: isHazardActive ? '#fca5a5' : '#86efac',
              border: `1px solid ${isHazardActive ? 'rgba(220, 38, 38, 0.4)' : 'rgba(34, 197, 94, 0.3)'}`,
              fontWeight: 700,
              fontSize: '10px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: isHazardActive ? '#ef4444' : '#22c55e' }} />
            {isHazardActive ? 'ACTIVE EMERGENCY OVERLAY' : 'NORMAL MONITORING'}
          </span>
        </div>
      </div>

      {/* SVG Blueprint Floorplan Area */}
      <div
        style={{
          position: 'relative',
          width: '100%',
          flex: 1,
          minHeight: '320px',
          background: '#090a0d',
          borderRadius: '6px',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          overflow: 'hidden',
        }}
      >
        <svg
          viewBox={`${vbX} ${vbY} ${vbW} ${vbH}`}
          style={{ width: '100%', height: '100%', display: 'block' }}
        >
          {/* Architectural Blueprint Grid and Definitions */}
          <defs>
            <pattern id="gridPattern" width="2" height="2" patternUnits="userSpaceOnUse">
              <path d="M 2 0 L 0 0 0 2" fill="none" stroke="rgba(255, 255, 255, 0.035)" strokeWidth="0.08" />
            </pattern>

            {/* Glowing filter for evacuation route */}
            <filter id="routeGlow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="0.4" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>

            {/* Hazard alert glow */}
            <filter id="hazardGlow" x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur stdDeviation="0.8" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/* Background Grid */}
          <rect x={vbX} y={vbY} width={vbW} height={vbH} fill="#090a0d" />
          <rect x="0" y="0" width={rawWidth} height={rawHeight} fill="url(#gridPattern)" />

          {/* Exterior Building Perimeter Wall */}
          <rect
            x="0"
            y="0"
            width={rawWidth}
            height={rawHeight}
            fill="none"
            stroke="rgba(255, 255, 255, 0.25)"
            strokeWidth="0.4"
            rx="0.4"
          />

          {/* Render Spatial Regions / Rooms / Corridors */}
          {regions.map((region) => {
            const pts = region.polygon_points || region.polygon || [];
            const textPos = getRegionTextPos(region);
            const pointsStr = pts.map((p) => `${p.x},${p.y}`).join(' ');

            return (
              <g key={region.region_id}>
                {pts.length > 0 && (
                  <polygon
                    points={pointsStr}
                    fill={getRegionFill(region.region_type)}
                    stroke={region.is_exit ? '#10b981' : 'rgba(255, 255, 255, 0.16)'}
                    strokeWidth={region.is_exit ? '0.35' : '0.2'}
                    strokeDasharray={region.region_type === 'CORRIDOR' ? '0.5 0.5' : undefined}
                  />
                )}
                {/* Subtle architectural region watermark text */}
                <text
                  x={textPos.x}
                  y={textPos.y}
                  fontSize="0.7"
                  fill="rgba(255, 255, 255, 0.22)"
                  fontWeight="700"
                  letterSpacing="0.08em"
                  textAnchor="middle"
                  dominantBaseline="middle"
                  style={{ pointerEvents: 'none', userSelect: 'none' }}
                >
                  {region.name.toUpperCase()}
                </text>
              </g>
            );
          })}

          {/* Non-Route Topological Graph Edges */}
          {edges.map((e) => {
            const n1 = nodes.find((n) => n.node_id === e.from_node);
            const n2 = nodes.find((n) => n.node_id === e.to_node);
            if (!n1 || !n2) return null;
            const inRoute = isEdgeInRoute(e.from_node, e.to_node);
            if (inRoute) return null; // Rendered separately for glowing route

            const isHazardOriginEdge = isHazardActive && (
              (e.from_node === incident?.hazard_origin_node && e.to_node === 'node_corridor_mid') ||
              (e.to_node === incident?.hazard_origin_node && e.from_node === 'node_corridor_mid')
            );

            return (
              <line
                key={e.edge_id}
                x1={n1.x}
                y1={n1.y}
                x2={n2.x}
                y2={n2.y}
                stroke={isHazardOriginEdge ? '#ef4444' : 'rgba(255, 255, 255, 0.12)'}
                strokeWidth={isHazardOriginEdge ? 0.6 : 0.4}
                strokeDasharray={isHazardOriginEdge ? '0.6 0.6' : '0.8 0.8'}
              />
            );
          })}

          {/* Active Evacuation Route (Rendered with Neon Green Glow + Animated Directional Dashes) */}
          {edges.map((e) => {
            const n1 = nodes.find((n) => n.node_id === e.from_node);
            const n2 = nodes.find((n) => n.node_id === e.to_node);
            if (!n1 || !n2) return null;
            const inRoute = isEdgeInRoute(e.from_node, e.to_node);
            if (!inRoute) return null;

            return (
              <g key={`route_${e.edge_id}`}>
                {/* Route Glow Halo */}
                <line
                  x1={n1.x}
                  y1={n1.y}
                  x2={n2.x}
                  y2={n2.y}
                  stroke="rgba(34, 197, 94, 0.4)"
                  strokeWidth="2.0"
                  strokeLinecap="round"
                />
                {/* Core Neon Green Line with Animated Flow */}
                <line
                  x1={n1.x}
                  y1={n1.y}
                  x2={n2.x}
                  y2={n2.y}
                  stroke="#22c55e"
                  strokeWidth="0.9"
                  strokeLinecap="round"
                  strokeDasharray="1.4 0.8"
                >
                  <animate
                    attributeName="stroke-dashoffset"
                    values="4.4;0"
                    dur="1.2s"
                    repeatCount="indefinite"
                  />
                </line>
              </g>
            );
          })}

          {/* Hazard Danger Zone (Pulsing Radial Dispersion Halo around Hazard Origin) */}
          {isHazardActive && incident?.hazard_origin_node && (
            (() => {
              const hNode = nodes.find((n) => n.node_id === incident.hazard_origin_node);
              if (!hNode) return null;
              return (
                <g key="hazard_dispersion_zone">
                  {/* Expanding Pulsing Hazard Rings */}
                  <circle cx={hNode.x} cy={hNode.y} r="6.0" fill="rgba(239, 68, 68, 0.12)" stroke="#ef4444" strokeWidth="0.2" strokeDasharray="0.6 0.6">
                    <animate attributeName="r" values="3.0;7.5;3.0" dur="3s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.8;0.15;0.8" dur="3s" repeatCount="indefinite" />
                  </circle>
                  <circle cx={hNode.x} cy={hNode.y} r="3.8" fill="rgba(220, 38, 38, 0.22)" stroke="#dc2626" strokeWidth="0.3" filter="url(#hazardGlow)">
                    <animate attributeName="r" values="2.0;4.5;2.0" dur="2s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.9;0.3;0.9" dur="2s" repeatCount="indefinite" />
                  </circle>
                </g>
              );
            })()
          )}

          {/* Destination Exit Pulse Ring */}
          {route && (
            (() => {
              const destNode = nodes.find((n) => n.node_id === route.destination_node);
              if (!destNode) return null;
              return (
                <g key="dest_exit_beacon">
                  <circle cx={destNode.x} cy={destNode.y} r="4.0" fill="none" stroke="#22c55e" strokeWidth="0.35" opacity="0.8">
                    <animate attributeName="r" values="1.8;5.0;1.8" dur="2s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.9;0.1;0.9" dur="2s" repeatCount="indefinite" />
                  </circle>
                </g>
              );
            })()
          )}

          {/* Topological Nodes & Exit Badges */}
          {nodes.map((n) => {
            const nodeRisk = nodeRisks[n.node_id] || 0;
            const isHazardOrigin = isHazardActive && incident?.hazard_origin_node === n.node_id;
            const isAffectedNode = isHazardActive && incident?.affected_nodes?.includes(n.node_id);
            const isInRoute = Boolean(route?.path_nodes?.includes(n.node_id));
            const isDestExit = Boolean(route && route.destination_node === n.node_id);
            const isCurrentOrigin = origin === n.node_id;
            const isHovered = hoveredNodeId === n.node_id;

            let fillColor = '#475569';
            let strokeColor = '#334155';

            if (n.is_exit) {
              fillColor = isDestExit ? '#16a34a' : '#15803d';
              strokeColor = isDestExit ? '#4ade80' : '#22c55e';
            } else if (isHazardOrigin) {
              fillColor = '#dc2626';
              strokeColor = '#f87171';
            } else if (isAffectedNode || nodeRisk >= 0.7) {
              fillColor = '#ef4444';
              strokeColor = '#fca5a5';
            } else if (nodeRisk >= 0.3) {
              fillColor = '#ea580c';
              strokeColor = '#fdba74';
            } else if (isCurrentOrigin) {
              fillColor = '#0284c7';
              strokeColor = '#38bdf8';
            } else if (isInRoute) {
              fillColor = '#16a34a';
              strokeColor = '#86efac';
            }

            const labelPos = getNodeLabelPos(n);
            const shortLabel = getNodeShortLabel(n);
            const approxTextWidth = Math.max(3.8, shortLabel.length * 0.42);

            return (
              <g 
                key={n.node_id}
                style={{ cursor: 'pointer' }}
                onMouseEnter={() => setHoveredNodeId(n.node_id)}
                onMouseLeave={() => setHoveredNodeId(null)}
                onClick={() => onSelectNode && onSelectNode(n.node_id)}
              >
                {/* Node marker: Exit Door Badge vs Circular Node */}
                {n.is_exit ? (
                  <g>
                    {/* Exit Door Box */}
                    <rect
                      x={n.x - 1.4}
                      y={n.y - 0.9}
                      width="2.8"
                      height="1.8"
                      rx="0.3"
                      fill={isDestExit ? '#15803d' : '#1e293b'}
                      stroke={isDestExit ? '#4ade80' : '#22c55e'}
                      strokeWidth={isDestExit ? '0.35' : '0.2'}
                    />
                    <text
                      x={n.x}
                      y={n.y + 0.3}
                      fontSize="0.65"
                      fill="#ffffff"
                      fontWeight="800"
                      textAnchor="middle"
                      dominantBaseline="middle"
                    >
                      EXIT
                    </text>
                  </g>
                ) : (
                  <g>
                    {/* Circular Node Dot */}
                    <circle
                      cx={n.x}
                      cy={n.y}
                      r={isHovered ? 1.2 : 0.9}
                      fill={fillColor}
                      stroke={strokeColor}
                      strokeWidth={isHovered ? '0.35' : '0.25'}
                    />
                    {isCurrentOrigin && (
                      <circle cx={n.x} cy={n.y} r="1.8" fill="none" stroke="#38bdf8" strokeWidth="0.25" strokeDasharray="0.5 0.5" />
                    )}
                  </g>
                )}

                {/* Clean Label Pill with Translucent Dark Background */}
                <g>
                  <rect
                    x={labelPos.align === 'end' ? labelPos.x - approxTextWidth - 0.4 : labelPos.align === 'start' ? labelPos.x - 0.2 : labelPos.x - approxTextWidth / 2 - 0.3}
                    y={labelPos.y - 0.45}
                    width={approxTextWidth + 0.6}
                    height="0.9"
                    rx="0.25"
                    fill={isHazardOrigin ? 'rgba(220, 38, 38, 0.85)' : isDestExit ? 'rgba(21, 128, 61, 0.85)' : isCurrentOrigin ? 'rgba(2, 132, 199, 0.85)' : 'rgba(12, 15, 20, 0.88)'}
                    stroke={isHazardOrigin ? '#f87171' : isDestExit ? '#4ade80' : isCurrentOrigin ? '#38bdf8' : 'rgba(255, 255, 255, 0.15)'}
                    strokeWidth="0.1"
                  />
                  <text
                    x={labelPos.x}
                    y={labelPos.y + 0.05}
                    fontSize="0.6"
                    textAnchor={labelPos.align}
                    dominantBaseline="middle"
                    fill="#ffffff"
                    fontWeight="700"
                  >
                    {shortLabel}
                  </text>
                </g>

                {/* Risk Tag (if hazard > 0 and not origin) */}
                {nodeRisk > 0 && (
                  <g>
                    <rect
                      x={n.x - 1.2}
                      y={n.y - 1.5}
                      width="2.4"
                      height="0.7"
                      rx="0.2"
                      fill={nodeRisk >= 0.7 ? '#dc2626' : nodeRisk >= 0.3 ? '#ea580c' : '#ca8a04'}
                    />
                    <text
                      x={n.x}
                      y={n.y - 1.15}
                      fontSize="0.45"
                      fill="#ffffff"
                      fontWeight="800"
                      textAnchor="middle"
                      dominantBaseline="middle"
                    >
                      {(nodeRisk * 100).toFixed(0)}% RISK
                    </text>
                  </g>
                )}

                {/* You Are Here Pin */}
                {isCurrentOrigin && (
                  <g>
                    <rect
                      x={n.x - 1.6}
                      y={n.y - 1.7}
                      width="3.2"
                      height="0.75"
                      rx="0.2"
                      fill="#0284c7"
                    />
                    <text
                      x={n.x}
                      y={n.y - 1.3}
                      fontSize="0.45"
                      fill="#ffffff"
                      fontWeight="800"
                      textAnchor="middle"
                      dominantBaseline="middle"
                    >
                      YOU ARE HERE
                    </text>
                  </g>
                )}
              </g>
            );
          })}
        </svg>

        {/* Hovered Node Quick Tooltip HUD */}
        {hoveredNode && (
          <div
            style={{
              position: 'absolute',
              bottom: '10px',
              left: '10px',
              backgroundColor: 'rgba(15, 23, 42, 0.95)',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              borderRadius: '4px',
              padding: '8px 12px',
              fontSize: '11px',
              color: '#f4f4f5',
              boxShadow: '0 4px 12px rgba(0,0,0,0.6)',
              backdropFilter: 'blur(6px)',
              pointerEvents: 'none',
              maxWidth: '320px',
            }}
          >
            <div style={{ fontWeight: 800, color: hoveredNode.is_exit ? '#4ade80' : '#f4f4f5', marginBottom: '2px' }}>
              {hoveredNode.label || hoveredNode.node_id}
            </div>
            <div style={{ fontSize: '10px', color: '#94a3b8' }}>
              Node ID: <code>{hoveredNode.node_id}</code> · Type: {hoveredNode.node_type?.toUpperCase()}
            </div>
            <div style={{ fontSize: '10px', color: '#cbd5e1', marginTop: '2px' }}>
              Coordinates: X={hoveredNode.x.toFixed(1)}m, Y={hoveredNode.y.toFixed(1)}m · Risk: <strong>{((nodeRisks[hoveredNode.node_id] || 0) * 100).toFixed(0)}%</strong>
            </div>
          </div>
        )}
      </div>

      {/* Legend & Provenance Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '10px', fontSize: '11px', color: '#a1a1aa' }}>
        <div style={{ display: 'flex', gap: '14px', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#dc2626' }} /> Hazard Danger Zone
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#22c55e' }} /> Safe Egress Path
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#0284c7' }} /> Current Origin
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '2px', background: '#16a34a' }} /> Emergency Exit
          </div>
        </div>
        <div style={{ fontSize: '10px', color: '#71717a' }}>
          Click any corridor node to simulate evacuation origin
        </div>
      </div>
    </div>
  );
};
