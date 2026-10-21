import React from 'react';

interface LandingPageProps {
  onEnterControlRoom: () => void;
}

export const LandingPage: React.FC<LandingPageProps> = ({ onEnterControlRoom }) => {
  return (
    <div
      style={{
        minHeight: '100vh',
        backgroundColor: '#0c0e12',
        color: '#f4f4f5',
        fontFamily: 'Inter, system-ui, -apple-system, BlinkMacSystemFont, sans-serif',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Top Header Bar */}
      <header
        style={{
          height: '64px',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          padding: '0 32px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          backgroundColor: '#090a0d',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            style={{
              padding: '4px 8px',
              backgroundColor: '#dc2626',
              color: '#ffffff',
              fontWeight: 800,
              fontSize: '13px',
              borderRadius: '2px',
              letterSpacing: '1px',
            }}
          >
            PHOENIX
          </div>
          <span style={{ fontSize: '13px', color: '#a1a1aa', fontWeight: 500 }}>
            Life-Safety Emergency Intelligence
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#71717a' }}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#22c55e' }} />
            SYSTEM CORE: READY
          </div>
          <button
            onClick={onEnterControlRoom}
            style={{
              padding: '7px 14px',
              backgroundColor: '#27272a',
              border: '1px solid rgba(255, 255, 255, 0.12)',
              borderRadius: '4px',
              color: '#ffffff',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'background 0.2s',
            }}
          >
            Control Room Access →
          </button>
        </div>
      </header>

      {/* Hero Section */}
      <main style={{ flex: 1, padding: '48px 32px', maxWidth: '1100px', margin: '0 auto', width: '100%', boxSizing: 'border-box' }}>
        <div style={{ maxWidth: '780px', marginBottom: '40px' }}>
          <div
            style={{
              display: 'inline-block',
              fontSize: '11px',
              fontWeight: 700,
              color: '#f87171',
              backgroundColor: 'rgba(220, 38, 38, 0.12)',
              border: '1px solid rgba(220, 38, 38, 0.25)',
              padding: '3px 8px',
              borderRadius: '3px',
              letterSpacing: '1px',
              marginBottom: '16px',
            }}
          >
            AUTONOMOUS PERCEPTION & DECISION PIPELINE
          </div>

          <h1
            style={{
              fontSize: '36px',
              fontWeight: 800,
              lineHeight: 1.15,
              color: '#fafafa',
              margin: '0 0 12px 0',
              letterSpacing: '-0.5px',
            }}
          >
            PHOENIX
          </h1>
          <h2
            style={{
              fontSize: '18px',
              fontWeight: 600,
              color: '#d4d4d8',
              margin: '0 0 16px 0',
            }}
          >
            Predictive Heat Observation and Emergency Navigation Intelligence System
          </h2>

          <p
            style={{
              fontSize: '15px',
              lineHeight: 1.6,
              color: '#a1a1aa',
              margin: '0 0 28px 0',
            }}
          >
            PHOENIX transforms continuous facility surveillance video into real-time fire and smoke perception,
            deterministic spatial risk assessment, and dynamic risk-aware evacuation routing recommendations.
          </p>

          <button
            onClick={onEnterControlRoom}
            style={{
              padding: '12px 24px',
              backgroundColor: '#dc2626',
              color: '#ffffff',
              border: 'none',
              borderRadius: '4px',
              fontSize: '14px',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '10px',
              boxShadow: '0 2px 8px rgba(220, 38, 38, 0.3)',
            }}
          >
            ENTER PHOENIX CONTROL ROOM
            <span style={{ fontSize: '16px' }}>→</span>
          </button>
        </div>

        {/* Operational Intelligence Pipeline Flow */}
        <div
          style={{
            backgroundColor: '#12151b',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: '6px',
            padding: '24px',
            marginBottom: '40px',
          }}
        >
          <div style={{ fontSize: '11px', fontWeight: 700, color: '#71717a', letterSpacing: '1px', textTransform: 'uppercase', marginBottom: '16px' }}>
            OPERATIONAL INTELLIGENCE PIPELINE
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(5, 1fr)',
              gap: '12px',
              alignItems: 'stretch',
            }}
          >
            <div style={{ background: '#181b22', padding: '14px', borderRadius: '4px', border: '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ fontSize: '10px', color: '#60a5fa', fontWeight: 700, marginBottom: '4px' }}>STAGE 01</div>
              <div style={{ fontSize: '13px', fontWeight: 700, color: '#ffffff', marginBottom: '6px' }}>Surveillance</div>
              <p style={{ fontSize: '11px', color: '#94a3b8', margin: 0, lineHeight: 1.4 }}>
                Continuous multi-camera video frame ingestion from facility CCTV feeds.
              </p>
            </div>

            <div style={{ background: '#181b22', padding: '14px', borderRadius: '4px', border: '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ fontSize: '10px', color: '#f87171', fontWeight: 700, marginBottom: '4px' }}>STAGE 02</div>
              <div style={{ fontSize: '13px', fontWeight: 700, color: '#ffffff', marginBottom: '6px' }}>Perception</div>
              <p style={{ fontSize: '11px', color: '#94a3b8', margin: 0, lineHeight: 1.4 }}>
                Dual YOLOv11 thermal/smoke models with temporal growth rate analysis.
              </p>
            </div>

            <div style={{ background: '#181b22', padding: '14px', borderRadius: '4px', border: '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ fontSize: '10px', color: '#fbbf24', fontWeight: 700, marginBottom: '4px' }}>STAGE 03</div>
              <div style={{ fontSize: '13px', fontWeight: 700, color: '#ffffff', marginBottom: '6px' }}>Spatial Risk</div>
              <p style={{ fontSize: '11px', color: '#94a3b8', margin: 0, lineHeight: 1.4 }}>
                Planar Homography mapping camera detections to architectural corridor nodes.
              </p>
            </div>

            <div style={{ background: '#181b22', padding: '14px', borderRadius: '4px', border: '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ fontSize: '10px', color: '#a78bfa', fontWeight: 700, marginBottom: '4px' }}>STAGE 04</div>
              <div style={{ fontSize: '13px', fontWeight: 700, color: '#ffffff', marginBottom: '6px' }}>Prediction</div>
              <p style={{ fontSize: '11px', color: '#94a3b8', margin: 0, lineHeight: 1.4 }}>
                Extrapolating hazard propagation, corridor blockage, and occupancy density.
              </p>
            </div>

            <div style={{ background: '#181b22', padding: '14px', borderRadius: '4px', border: '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ fontSize: '10px', color: '#4ade80', fontWeight: 700, marginBottom: '4px' }}>STAGE 05</div>
              <div style={{ fontSize: '13px', fontWeight: 700, color: '#ffffff', marginBottom: '6px' }}>Routing & ETA</div>
              <p style={{ fontSize: '11px', color: '#94a3b8', margin: 0, lineHeight: 1.4 }}>
                Multi-factor deterministic graph optimization and real-time egress calculation.
              </p>
            </div>
          </div>
        </div>

        {/* Operational Modes Guide */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
          <div
            style={{
              backgroundColor: '#12151b',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '6px',
              padding: '20px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#22c55e' }} />
              <h3 style={{ fontSize: '14px', fontWeight: 700, color: '#f4f4f5', margin: 0 }}>
                LAYER 1: Normal Surveillance
              </h3>
            </div>
            <p style={{ fontSize: '12px', color: '#a1a1aa', lineHeight: 1.5, margin: 0 }}>
              The default operational state. Multi-camera CCTV feeds run continuously under live AI perception.
              Architectural topology remains on active standby without intrusive alerts.
            </p>
          </div>

          <div
            style={{
              backgroundColor: '#12151b',
              border: '1px solid rgba(220, 38, 38, 0.3)',
              borderRadius: '6px',
              padding: '20px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#dc2626' }} />
              <h3 style={{ fontSize: '14px', fontWeight: 700, color: '#fca5a5', margin: 0 }}>
                LAYER 2: Emergency Decision-Support
              </h3>
            </div>
            <p style={{ fontSize: '12px', color: '#a1a1aa', lineHeight: 1.5, margin: 0 }}>
              Triggered exclusively when the backend pipeline genuinely confirms fire or smoke above threshold.
              Focuses the hazard camera, reveals the affected nodes, and visualizes the computed evacuation route.
            </p>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer
        style={{
          borderTop: '1px solid rgba(255, 255, 255, 0.08)',
          padding: '16px 32px',
          textAlign: 'center',
          fontSize: '11px',
          color: '#52525b',
          backgroundColor: '#090a0d',
        }}
      >
        PHOENIX Emergency Navigation Intelligence Platform · Continuous Backend Source of Truth · Life-Safety Critical
      </footer>
    </div>
  );
};
