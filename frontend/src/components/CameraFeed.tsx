import React from 'react';
import type { CameraStatus } from '../types/phoenix';

interface CameraFeedProps {
  id: string;
  name: string;
  location?: string;
  videoSource?: string;
  status: CameraStatus;
  hasCalibration?: boolean;
  isHighlighted?: boolean;
  compact?: boolean;
  badgeText?: string;
  badgeColor?: string;
  isSelected?: boolean;
  onClick?: () => void;
}

export const CameraFeed: React.FC<CameraFeedProps> = ({
  id,
  name,
  location,
  videoSource,
  status,
  hasCalibration = false,
  isHighlighted = false,
  compact = false,
  badgeText,
  badgeColor,
  isSelected = false,
  onClick,
}) => {
  // Normalize video source URL with proper URI encoding for spaces
  const resolveVideoUrl = (src?: string) => {
    if (!src) return undefined;
    let path = src;
    if (!path.startsWith('http') && !path.startsWith('/')) {
      path = `/${path}`;
    }
    return encodeURI(path);
  };

  const videoUrl = resolveVideoUrl(videoSource);

  return (
    <div
      onClick={onClick}
      style={{
        background: '#13161c',
        border: isSelected
          ? '2px solid #3b82f6'
          : isHighlighted
          ? '2px solid #dc2626'
          : '1px solid rgba(255, 255, 255, 0.1)',
        borderRadius: '6px',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: isHighlighted
          ? '0 0 14px rgba(220, 38, 38, 0.45)'
          : isSelected
          ? '0 0 12px rgba(59, 130, 246, 0.4)'
          : '0 2px 8px rgba(0,0,0,0.3)',
        cursor: onClick ? 'pointer' : 'default',
        transition: 'transform 0.15s ease, border-color 0.2s ease',
      }}
    >
      {/* Header bar */}
      <div
        style={{
          padding: compact ? '5px 8px' : '7px 12px',
          background: isHighlighted ? 'rgba(220, 38, 38, 0.22)' : isSelected ? 'rgba(59, 130, 246, 0.15)' : '#181b22',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: compact ? '11px' : '12px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', overflow: 'hidden' }}>
          <span style={{ fontWeight: 700, color: isHighlighted ? '#fca5a5' : '#f4f4f5', whiteSpace: 'nowrap' }}>
            {id}
          </span>
          <span style={{ color: '#a1a1aa', fontSize: compact ? '10px' : '11px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            · {name}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
          {badgeText && (
            <span
              style={{
                fontSize: '9px',
                fontWeight: 800,
                color: '#ffffff',
                backgroundColor: badgeColor || '#dc2626',
                padding: '1px 6px',
                borderRadius: '3px',
                letterSpacing: '0.4px',
                textTransform: 'uppercase',
              }}
            >
              {badgeText}
            </span>
          )}
          <span
            style={{
              fontSize: '10px',
              fontWeight: 600,
              color: status === 'ONLINE' ? '#4ade80' : '#ef4444',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <span
              style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                backgroundColor: status === 'ONLINE' ? '#22c55e' : '#ef4444',
              }}
            />
            {status}
          </span>
        </div>
      </div>

      {/* Video Stream Container */}
      <div style={{ position: 'relative', width: '100%', backgroundColor: '#090a0d', aspectRatio: '16/9', overflow: 'hidden' }}>
        {videoUrl ? (
          <video
            src={videoUrl}
            autoPlay
            loop
            muted
            playsInline
            controls={false}
            style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
          />
        ) : (
          <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#71717a', fontSize: '11px' }}>
            No CCTV video stream configured
          </div>
        )}

        {/* Hazard / Status Overlay Pill */}
        {isHighlighted && (
          <div
            style={{
              position: 'absolute',
              top: '6px',
              left: '6px',
              background: 'rgba(220, 38, 38, 0.9)',
              color: '#ffffff',
              fontSize: '9px',
              fontWeight: 800,
              padding: '2px 7px',
              borderRadius: '3px',
              letterSpacing: '0.5px',
              boxShadow: '0 2px 6px rgba(0,0,0,0.6)',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              backdropFilter: 'blur(4px)',
            }}
          >
            <span style={{ width: '5px', height: '5px', borderRadius: '50%', background: '#ffffff' }} />
            HAZARD DETECTED
          </div>
        )}

        {/* Calibration Badge (Lower Right) */}
        <div
          style={{
            position: 'absolute',
            bottom: '4px',
            right: '6px',
            fontSize: '8px',
            fontWeight: 700,
            padding: '1px 5px',
            borderRadius: '2px',
            backgroundColor: hasCalibration ? 'rgba(0,0,0,0.65)' : 'rgba(0,0,0,0.65)',
            color: hasCalibration ? '#86efac' : '#94a3b8',
            border: `1px solid ${hasCalibration ? 'rgba(34, 197, 94, 0.4)' : 'rgba(255, 255, 255, 0.15)'}`,
          }}
        >
          {hasCalibration ? 'HOMOGRAPHY CALIBRATED' : 'UNCALIBRATED'}
        </div>

        {location && (
          <div
            style={{
              position: 'absolute',
              bottom: '4px',
              left: '6px',
              fontSize: '8px',
              color: 'rgba(255, 255, 255, 0.75)',
              backgroundColor: 'rgba(0,0,0,0.6)',
              padding: '1px 4px',
              borderRadius: '2px',
              maxWidth: '65%',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            📍 {location}
          </div>
        )}
      </div>
    </div>
  );
};
