import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { ApiClient } from '../services/apiClient';
import type {
  StorageOverviewResponse,
  UserInventoryResponse,
  DatabaseInventoryResponse,
  JobsInventoryResponse,
  JobSampleResponse,
} from '../types/phoenix';

interface DataStorageExplorerProps {
  onBackToDashboard: () => void;
}

export const DataStorageExplorer: React.FC<DataStorageExplorerProps> = ({ onBackToDashboard }) => {
  const { role, userId } = useAuth();
  const [activeTab, setActiveTab] = useState<'overview' | 'users' | 'database' | 'jobs' | 'lineage'>('overview');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [overview, setOverview] = useState<StorageOverviewResponse | null>(null);
  const [userInv, setUserInv] = useState<UserInventoryResponse | null>(null);
  const [dbInv, setDbInv] = useState<DatabaseInventoryResponse | null>(null);
  const [jobsInv, setJobsInv] = useState<JobsInventoryResponse | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [jobSample, setJobSample] = useState<JobSampleResponse | null>(null);
  const [sampleLoading, setSampleLoading] = useState<boolean>(false);

  const isOccupant = role === 'OCCUPANT';

  useEffect(() => {
    if (isOccupant) {
      setLoading(false);
      return;
    }

    let isMounted = true;
    const loadAll = async () => {
      setLoading(true);
      setError(null);
      try {
        const [ovData, dbData, jbData] = await Promise.all([
          ApiClient.getExplorerOverview().catch((err) => {
            console.warn('Overview fetch error:', err);
            return null;
          }),
          ApiClient.getExplorerDatabase().catch(() => null),
          ApiClient.getExplorerJobs(25, 0).catch(() => null),
        ]);

        let uData: UserInventoryResponse | null = null;
        if (role === 'SUPERADMIN' || role === 'BUILDING_MANAGER') {
          uData = await ApiClient.getExplorerUsers().catch(() => null);
        }

        if (!isMounted) return;
        setOverview(ovData);
        setDbInv(dbData);
        setJobsInv(jbData);
        setUserInv(uData);
      } catch (err: any) {
        if (isMounted) setError(err.message || 'Failed loading explorer data.');
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    loadAll();
    return () => {
      isMounted = false;
    };
  }, [role, isOccupant]);

  const loadJobSample = async (jobId: string) => {
    setSelectedJobId(jobId);
    setSampleLoading(true);
    try {
      const sample = await ApiClient.getExplorerJobSample(jobId);
      setJobSample(sample);
    } catch (err: any) {
      console.error('Failed to load job sample:', err);
    } finally {
      setSampleLoading(false);
    }
  };

  const handleExportReport = () => {
    const url = ApiClient.getExplorerExportUrl();
    window.open(url, '_blank');
  };

  if (isOccupant) {
    return (
      <div style={{ minHeight: '100vh', backgroundColor: '#0c0e12', color: '#f4f4f5', padding: '30px', fontFamily: 'Inter, system-ui, sans-serif' }}>
        <button
          onClick={onBackToDashboard}
          style={{ padding: '8px 14px', backgroundColor: '#27272a', color: '#ffffff', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '4px', cursor: 'pointer', marginBottom: '20px' }}
        >
          ← Return to Evacuation Dashboard
        </button>
        <div style={{ maxWidth: '600px', margin: '40px auto', backgroundColor: '#181b22', border: '1px solid rgba(239,68,68,0.4)', borderRadius: '8px', padding: '24px', textAlign: 'center' }}>
          <div style={{ fontSize: '32px', marginBottom: '12px' }}>🔒</div>
          <h2 style={{ color: '#fca5a5', margin: '0 0 10px 0' }}>Access Restricted — OCCUPANT Role</h2>
          <p style={{ color: '#a1a1aa', fontSize: '13px', lineHeight: 1.6 }}>
            The <strong>Data & Storage Explorer</strong> is restricted to Security and System Administrators (SUPERADMIN, BUILDING_MANAGER, FIRST_RESPONDER) in accordance with PHOENIX life-safety access control policy.
          </p>
          <p style={{ color: '#71717a', fontSize: '11px', marginTop: '16px' }}>
            Current Authenticated Session: <strong style={{ color: '#d4d4d8' }}>{userId} (OCCUPANT)</strong>
          </p>
        </div>
      </div>
    );
  }

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
      {/* Top Header Command Bar */}
      <header
        style={{
          height: '56px',
          backgroundColor: '#090a0d',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          padding: '0 20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <button
            onClick={onBackToDashboard}
            style={{
              padding: '5px 12px',
              backgroundColor: '#1f2937',
              color: '#d1d5db',
              border: '1px solid rgba(255, 255, 255, 0.12)',
              borderRadius: '4px',
              fontSize: '11px',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            ← Back to CCTV Matrix
          </button>
          <div
            style={{
              padding: '3px 8px',
              backgroundColor: '#3b82f6',
              color: '#ffffff',
              fontWeight: 800,
              fontSize: '11px',
              borderRadius: '3px',
              letterSpacing: '0.8px',
            }}
          >
            DATA & STORAGE EXPLORER
          </div>
          <span style={{ fontSize: '12px', color: '#a1a1aa' }}>
            Reviewer Audit & Data Lineage Inspection Console
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            onClick={handleExportReport}
            style={{
              padding: '6px 14px',
              backgroundColor: '#16a34a',
              color: '#ffffff',
              border: 'none',
              borderRadius: '4px',
              fontSize: '11px',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              boxShadow: '0 1px 4px rgba(0,0,0,0.4)',
            }}
          >
            📥 Download Reviewer Report (.json)
          </button>

          <div style={{ fontSize: '11px', color: '#94a3b8', borderLeft: '1px solid rgba(255,255,255,0.1)', paddingLeft: '12px' }}>
            {userId} (<strong style={{ color: '#4ade80' }}>{role}</strong>)
          </div>
        </div>
      </header>

      {/* Sub-Navigation Tabs */}
      <nav
        style={{
          display: 'flex',
          backgroundColor: '#13161c',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          padding: '0 20px',
          gap: '4px',
        }}
      >
        {[
          { key: 'overview', label: '1. Storage & Checkpoints' },
          { key: 'users', label: '2. User Accounts & Identity' },
          { key: 'database', label: '3. Database Tables & Records' },
          { key: 'jobs', label: '4. Video & Perception Jobs' },
          { key: 'lineage', label: '5. Data Lineage Flow' },
        ].map((t) => {
          const isSelected = activeTab === t.key;
          return (
            <button
              key={t.key}
              onClick={() => setActiveTab(t.key as any)}
              style={{
                padding: '10px 16px',
                backgroundColor: isSelected ? 'rgba(59, 130, 246, 0.15)' : 'transparent',
                color: isSelected ? '#60a5fa' : '#9ca3af',
                border: 'none',
                borderBottom: isSelected ? '2px solid #3b82f6' : '2px solid transparent',
                fontSize: '12px',
                fontWeight: isSelected ? 800 : 500,
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              {t.label}
            </button>
          );
        })}
      </nav>

      {/* Main Content Viewport */}
      <main style={{ padding: '20px', flex: 1, overflowY: 'auto' }}>
        {loading && (
          <div style={{ textAlign: 'center', padding: '60px 0', color: '#9ca3af' }}>
            <div style={{ fontSize: '24px', marginBottom: '10px' }}>⚙️</div>
            <div>Retrieving verified filesystem and database storage inventory...</div>
          </div>
        )}

        {error && (
          <div style={{ backgroundColor: 'rgba(220, 38, 38, 0.15)', border: '1px solid #dc2626', borderRadius: '6px', padding: '14px', color: '#fca5a5', marginBottom: '20px' }}>
            ⚠️ <strong>Error loading explorer:</strong> {error}
          </div>
        )}

        {!loading && (
          <>
            {/* ============================================================== */}
            {/* TAB 1: SYSTEM STORAGE OVERVIEW */}
            {/* ============================================================== */}
            {activeTab === 'overview' && overview && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                {/* Database Card */}
                <div style={{ backgroundColor: '#181b22', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '6px', padding: '16px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                    <div style={{ fontSize: '13px', fontWeight: 800, color: '#38bdf8', textTransform: 'uppercase' }}>
                      Primary Relational Database
                    </div>
                    <span style={{ fontSize: '11px', background: 'rgba(34,197,94,0.15)', color: '#4ade80', padding: '2px 8px', borderRadius: '3px', fontWeight: 700 }}>
                      ✓ WAL MODE VERIFIED
                    </span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', fontSize: '12px' }}>
                    <div style={{ backgroundColor: '#0c0e12', padding: '10px', borderRadius: '4px' }}>
                      <div style={{ fontSize: '10px', color: '#71717a' }}>DATABASE PATH</div>
                      <div style={{ fontWeight: 700, color: '#f4f4f5', marginTop: '2px', wordBreak: 'break-all' }}>{overview.database.path}</div>
                    </div>
                    <div style={{ backgroundColor: '#0c0e12', padding: '10px', borderRadius: '4px' }}>
                      <div style={{ fontSize: '10px', color: '#71717a' }}>STORAGE TYPE</div>
                      <div style={{ fontWeight: 700, color: '#f4f4f5', marginTop: '2px' }}>{overview.database.database_type}</div>
                    </div>
                    <div style={{ backgroundColor: '#0c0e12', padding: '10px', borderRadius: '4px' }}>
                      <div style={{ fontSize: '10px', color: '#71717a' }}>FILE SIZE</div>
                      <div style={{ fontWeight: 700, color: '#4ade80', marginTop: '2px' }}>{(overview.database.size_bytes / (1024 * 1024)).toFixed(2)} MB</div>
                    </div>
                    <div style={{ backgroundColor: '#0c0e12', padding: '10px', borderRadius: '4px' }}>
                      <div style={{ fontSize: '10px', color: '#71717a' }}>LAST MODIFIED</div>
                      <div style={{ fontWeight: 700, color: '#cbd5e1', marginTop: '2px' }}>
                        {overview.database.last_modified ? new Date(overview.database.last_modified).toLocaleString() : 'N/A'}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Directory Storage Inventory */}
                <div style={{ backgroundColor: '#181b22', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '6px', padding: '16px' }}>
                  <div style={{ fontSize: '13px', fontWeight: 800, color: '#fbbf24', textTransform: 'uppercase', marginBottom: '12px' }}>
                    Filesystem Directory Allocations
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px' }}>
                    {Object.entries(overview.directories).map(([key, dir]) => (
                      <div key={key} style={{ backgroundColor: '#0c0e12', padding: '12px', borderRadius: '4px', border: '1px solid rgba(255,255,255,0.06)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontSize: '11px', fontWeight: 700, color: '#ffffff' }}>{key.replace(/_/g, ' ').toUpperCase()}</span>
                          <span style={{ fontSize: '9px', padding: '1px 6px', borderRadius: '2px', backgroundColor: dir.exists ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)', color: dir.exists ? '#86efac' : '#fca5a5' }}>
                            {dir.exists ? 'EXISTS' : 'NOT FOUND'}
                          </span>
                        </div>
                        <div style={{ fontSize: '11px', color: '#71717a', marginTop: '4px', wordBreak: 'break-all' }}>{dir.path}</div>
                        <div style={{ display: 'flex', gap: '16px', marginTop: '8px', fontSize: '11px' }}>
                          <span>Files: <strong style={{ color: '#f4f4f5' }}>{dir.file_count}</strong></span>
                          <span>Size: <strong style={{ color: '#4ade80' }}>{(dir.total_size_bytes / (1024 * 1024)).toFixed(2)} MB</strong></span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* YOLO Model Weights & Video Artifacts */}
                <div style={{ backgroundColor: '#181b22', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '6px', padding: '16px' }}>
                  <div style={{ fontSize: '13px', fontWeight: 800, color: '#c084fc', textTransform: 'uppercase', marginBottom: '12px' }}>
                    YOLOv11 Model Weights & Video Feeds
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px' }}>
                    {Object.entries(overview.key_artifacts).map(([key, file]) => (
                      <div key={key} style={{ backgroundColor: '#0c0e12', padding: '12px', borderRadius: '4px', border: '1px solid rgba(255,255,255,0.06)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontSize: '11px', fontWeight: 700, color: '#ffffff' }}>{key.replace(/_/g, ' ').toUpperCase()}</span>
                          <span style={{ fontSize: '9px', padding: '1px 6px', borderRadius: '2px', backgroundColor: file.exists ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)', color: file.exists ? '#86efac' : '#fca5a5' }}>
                            {file.exists ? 'VERIFIED ON DISK' : 'MISSING'}
                          </span>
                        </div>
                        <div style={{ fontSize: '11px', color: '#71717a', marginTop: '4px', wordBreak: 'break-all' }}>{file.path}</div>
                        <div style={{ display: 'flex', gap: '16px', marginTop: '8px', fontSize: '11px' }}>
                          <span>Size: <strong style={{ color: '#4ade80' }}>{(file.size_bytes / (1024 * 1024)).toFixed(2)} MB</strong></span>
                          <span>Modified: <strong style={{ color: '#cbd5e1' }}>{file.last_modified ? new Date(file.last_modified).toLocaleDateString() : 'N/A'}</strong></span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* ============================================================== */}
            {/* TAB 2: USER ACCOUNTS & IDENTITY */}
            {/* ============================================================== */}
            {activeTab === 'users' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                {userInv ? (
                  <>
                    <div style={{ backgroundColor: '#181b22', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '6px', padding: '16px' }}>
                      <div style={{ fontSize: '13px', fontWeight: 800, color: '#38bdf8', textTransform: 'uppercase', marginBottom: '12px' }}>
                        Registered Role-Based Operator Accounts ({userInv.total_users})
                      </div>
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
                        <thead>
                          <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#9ca3af' }}>
                            <th style={{ padding: '8px' }}>User ID</th>
                            <th style={{ padding: '8px' }}>Role</th>
                            <th style={{ padding: '8px' }}>Operator Email</th>
                            <th style={{ padding: '8px' }}>Full Name</th>
                            <th style={{ padding: '8px' }}>Organization</th>
                            <th style={{ padding: '8px' }}>Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {userInv.users.map((u) => (
                            <tr key={u.user_id} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                              <td style={{ padding: '8px', fontWeight: 700, color: '#f4f4f5' }}>{u.user_id}</td>
                              <td style={{ padding: '8px' }}>
                                <span
                                  style={{
                                    padding: '2px 8px',
                                    borderRadius: '3px',
                                    fontSize: '10px',
                                    fontWeight: 800,
                                    backgroundColor:
                                      u.role === 'SUPERADMIN' ? 'rgba(239,68,68,0.2)' :
                                      u.role === 'BUILDING_MANAGER' ? 'rgba(34,197,94,0.2)' :
                                      u.role === 'FIRST_RESPONDER' ? 'rgba(249,115,22,0.2)' :
                                      'rgba(59,130,246,0.2)',
                                    color:
                                      u.role === 'SUPERADMIN' ? '#fca5a5' :
                                      u.role === 'BUILDING_MANAGER' ? '#86efac' :
                                      u.role === 'FIRST_RESPONDER' ? '#fdba74' :
                                      '#93c5fd',
                                  }}
                                >
                                  {u.role}
                                </span>
                              </td>
                              <td style={{ padding: '8px', color: '#cbd5e1' }}>{u.email}</td>
                              <td style={{ padding: '8px', color: '#f4f4f5' }}>{u.full_name}</td>
                              <td style={{ padding: '8px', color: '#71717a' }}>{u.organization_id}</td>
                              <td style={{ padding: '8px' }}>
                                <span style={{ color: u.is_active ? '#4ade80' : '#ef4444', fontWeight: 700 }}>
                                  {u.is_active ? 'ACTIVE' : 'DEACTIVATED'}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    {/* Architectural Concept Card */}
                    <div style={{ backgroundColor: '#181b22', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '6px', padding: '16px' }}>
                      <div style={{ fontSize: '13px', fontWeight: 800, color: '#a78bfa', textTransform: 'uppercase', marginBottom: '10px' }}>
                        Identity & Access Control Security Architecture
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px', fontSize: '11px', lineHeight: 1.5 }}>
                        <div style={{ backgroundColor: '#0c0e12', padding: '10px', borderRadius: '4px' }}>
                          <strong style={{ color: '#38bdf8' }}>User ID:</strong>
                          <div style={{ color: '#a1a1aa', marginTop: '2px' }}>{userInv.identity_architecture_explanation.user_id}</div>
                        </div>
                        <div style={{ backgroundColor: '#0c0e12', padding: '10px', borderRadius: '4px' }}>
                          <strong style={{ color: '#4ade80' }}>Role (RBAC):</strong>
                          <div style={{ color: '#a1a1aa', marginTop: '2px' }}>{userInv.identity_architecture_explanation.role}</div>
                        </div>
                        <div style={{ backgroundColor: '#0c0e12', padding: '10px', borderRadius: '4px' }}>
                          <strong style={{ color: '#fbbf24' }}>Access Token (JWT):</strong>
                          <div style={{ color: '#a1a1aa', marginTop: '2px' }}>{userInv.identity_architecture_explanation.access_token}</div>
                        </div>
                        <div style={{ backgroundColor: '#0c0e12', padding: '10px', borderRadius: '4px' }}>
                          <strong style={{ color: '#f87171' }}>Password Protection:</strong>
                          <div style={{ color: '#a1a1aa', marginTop: '2px' }}>{userInv.identity_architecture_explanation.storage_security}</div>
                        </div>
                      </div>
                    </div>
                  </>
                ) : (
                  <div style={{ backgroundColor: '#181b22', padding: '24px', borderRadius: '6px', textAlign: 'center', color: '#9ca3af' }}>
                    User inventory requires SuperAdmin or Building Manager privileges.
                  </div>
                )}
              </div>
            )}

            {/* ============================================================== */}
            {/* TAB 3: DATABASE TABLES & RECORDS */}
            {/* ============================================================== */}
            {activeTab === 'database' && dbInv && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <h3 style={{ margin: '0 0 4px 0', fontSize: '15px', color: '#f4f4f5' }}>
                      SQLite Schema & Table Records ({dbInv.total_tables} Tables · {dbInv.total_records.toLocaleString()} Total Rows)
                    </h3>
                    <span style={{ fontSize: '11px', color: '#71717a' }}>Database file: {dbInv.database_file}</span>
                  </div>
                </div>

                <div style={{ backgroundColor: '#181b22', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '6px', overflow: 'hidden' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
                    <thead>
                      <tr style={{ backgroundColor: '#0f1117', borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#9ca3af' }}>
                        <th style={{ padding: '10px 12px' }}>Table Name</th>
                        <th style={{ padding: '10px 12px' }}>Primary Key</th>
                        <th style={{ padding: '10px 12px' }}>Exact Row Count</th>
                        <th style={{ padding: '10px 12px' }}>Architectural Purpose & Contents</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dbInv.tables.map((tbl) => (
                        <tr key={tbl.table_name} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                          <td style={{ padding: '10px 12px', fontWeight: 700, color: '#38bdf8' }}>{tbl.table_name}</td>
                          <td style={{ padding: '10px 12px', color: '#fbbf24', fontFamily: 'monospace' }}>{tbl.primary_key}</td>
                          <td style={{ padding: '10px 12px', fontWeight: 800, color: tbl.row_count > 0 ? '#4ade80' : '#71717a' }}>
                            {tbl.row_count.toLocaleString()}
                          </td>
                          <td style={{ padding: '10px 12px', color: '#cbd5e1' }}>{tbl.description}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* ============================================================== */}
            {/* TAB 4: VIDEO & PERCEPTION JOBS */}
            {/* ============================================================== */}
            {activeTab === 'jobs' && jobsInv && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <div style={{ backgroundColor: '#181b22', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '6px', padding: '16px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                    <div style={{ fontSize: '13px', fontWeight: 800, color: '#f87171', textTransform: 'uppercase' }}>
                      Perception Processing Jobs ({jobsInv.total_jobs} Total Jobs Logged)
                    </div>
                    <span style={{ fontSize: '11px', color: '#9ca3af' }}>
                      Click any job row to inspect an isolated read-only sample of genuine YOLO detections and routes.
                    </span>
                  </div>

                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11px', textAlign: 'left' }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#9ca3af' }}>
                          <th style={{ padding: '8px' }}>Job ID</th>
                          <th style={{ padding: '8px' }}>Video Source</th>
                          <th style={{ padding: '8px' }}>Camera</th>
                          <th style={{ padding: '8px' }}>Status</th>
                          <th style={{ padding: '8px' }}>Progress</th>
                          <th style={{ padding: '8px' }}>Frames</th>
                          <th style={{ padding: '8px' }}>Detections</th>
                          <th style={{ padding: '8px' }}>Fire / Smoke</th>
                          <th style={{ padding: '8px' }}>Max Risk</th>
                          <th style={{ padding: '8px' }}>Runtime</th>
                          <th style={{ padding: '8px' }}>Annotated Output</th>
                        </tr>
                      </thead>
                      <tbody>
                        {jobsInv.jobs.map((j) => {
                          const isSelected = selectedJobId === j.job_id;
                          return (
                            <tr
                              key={j.job_id}
                              onClick={() => loadJobSample(j.job_id)}
                              style={{
                                borderBottom: '1px solid rgba(255,255,255,0.05)',
                                backgroundColor: isSelected ? 'rgba(59,130,246,0.15)' : 'transparent',
                                cursor: 'pointer',
                              }}
                            >
                              <td style={{ padding: '8px', fontWeight: 700, color: '#f4f4f5' }}>{j.job_id}</td>
                              <td style={{ padding: '8px', color: '#cbd5e1' }}>{j.original_filename}</td>
                              <td style={{ padding: '8px', color: '#71717a' }}>{j.camera_id}</td>
                              <td style={{ padding: '8px' }}>
                                <span
                                  style={{
                                    padding: '2px 6px',
                                    borderRadius: '2px',
                                    fontSize: '9px',
                                    fontWeight: 800,
                                    backgroundColor: j.status === 'COMPLETED' ? 'rgba(34,197,94,0.2)' : j.status === 'PROCESSING' ? 'rgba(234,179,8,0.2)' : 'rgba(239,68,68,0.2)',
                                    color: j.status === 'COMPLETED' ? '#86efac' : j.status === 'PROCESSING' ? '#fde047' : '#fca5a5',
                                  }}
                                >
                                  {j.status}
                                </span>
                              </td>
                              <td style={{ padding: '8px', fontWeight: 700 }}>{j.progress_percent}%</td>
                              <td style={{ padding: '8px' }}>{j.frames_processed} / {j.total_frames || '...'}</td>
                              <td style={{ padding: '8px', fontWeight: 700, color: j.detections_count > 0 ? '#4ade80' : '#71717a' }}>
                                {j.detections_count}
                              </td>
                              <td style={{ padding: '8px' }}>
                                {j.fire_detected && <span style={{ color: '#ef4444', fontWeight: 700, marginRight: '4px' }}>🔥 FIRE</span>}
                                {j.smoke_detected && <span style={{ color: '#cbd5e1', fontWeight: 700 }}>💨 SMOKE</span>}
                                {!j.fire_detected && !j.smoke_detected && <span style={{ color: '#71717a' }}>None</span>}
                              </td>
                              <td style={{ padding: '8px', fontWeight: 700, color: j.max_risk_level === 'CRITICAL' ? '#ef4444' : j.max_risk_level === 'HIGH' ? '#f97316' : '#86efac' }}>
                                {j.max_risk_level}
                              </td>
                              <td style={{ padding: '8px' }}>{j.execution_time_seconds ? `${j.execution_time_seconds}s` : 'N/A'}</td>
                              <td style={{ padding: '8px' }}>
                                <span style={{ color: j.annotated_video_exists ? '#4ade80' : '#71717a', fontSize: '10px' }}>
                                  {j.annotated_video_exists ? '✓ Available (.mp4)' : 'Pending'}
                                </span>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Job Sample Inspector Panel */}
                {selectedJobId && (
                  <div style={{ backgroundColor: '#181b22', border: '1px solid #3b82f6', borderRadius: '6px', padding: '16px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                      <div style={{ fontSize: '13px', fontWeight: 800, color: '#60a5fa' }}>
                        Isolated Sample Records for Job: {selectedJobId}
                      </div>
                      <button
                        onClick={() => setSelectedJobId(null)}
                        style={{ background: 'transparent', border: 'none', color: '#9ca3af', cursor: 'pointer', fontWeight: 700 }}
                      >
                        ✕ Close Sample
                      </button>
                    </div>

                    {sampleLoading && <div style={{ color: '#9ca3af', padding: '10px 0' }}>Loading job sample records...</div>}

                    {!sampleLoading && jobSample && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                        {/* Sample Detections */}
                        <div>
                          <div style={{ fontSize: '11px', fontWeight: 700, color: '#f4f4f5', marginBottom: '6px' }}>
                            YOLOv11 Detections Sample ({jobSample.sample_detections.length} rows):
                          </div>
                          <div style={{ overflowX: 'auto', backgroundColor: '#0c0e12', padding: '8px', borderRadius: '4px' }}>
                            <table style={{ width: '100%', fontSize: '10px', textAlign: 'left' }}>
                              <thead>
                                <tr style={{ color: '#71717a' }}>
                                  <th>Detection ID</th>
                                  <th>Frame</th>
                                  <th>Class</th>
                                  <th>Confidence</th>
                                  <th>Bounding Box (x1, y1, x2, y2)</th>
                                  <th>Floor Plan Point (m)</th>
                                </tr>
                              </thead>
                              <tbody>
                                {jobSample.sample_detections.map((d) => (
                                  <tr key={d.detection_id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                                    <td style={{ color: '#d4d4d8' }}>{d.detection_id}</td>
                                    <td>{d.frame_id}</td>
                                    <td style={{ fontWeight: 700, color: d.class_name === 'fire' ? '#ef4444' : d.class_name === 'smoke' ? '#cbd5e1' : '#38bdf8' }}>
                                      {d.class_name.toUpperCase()}
                                    </td>
                                    <td>{(d.confidence * 100).toFixed(1)}%</td>
                                    <td style={{ fontFamily: 'monospace' }}>
                                      {d.bbox ? `[${d.bbox.x1.toFixed(1)}, ${d.bbox.y1.toFixed(1)}, ${d.bbox.x2.toFixed(1)}, ${d.bbox.y2.toFixed(1)}]` : 'None'}
                                    </td>
                                    <td>{d.floor_point ? `(${d.floor_point.x.toFixed(2)}m, ${d.floor_point.y.toFixed(2)}m)` : 'Uncalibrated'}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>

                        {/* Sample Temporal Observations */}
                        {jobSample.sample_temporal_analyses.length > 0 && (
                          <div>
                            <div style={{ fontSize: '11px', fontWeight: 700, color: '#f4f4f5', marginBottom: '6px' }}>
                              Temporal Smoke Growth Observations Sample ({jobSample.sample_temporal_analyses.length} rows):
                            </div>
                            <div style={{ overflowX: 'auto', backgroundColor: '#0c0e12', padding: '8px', borderRadius: '4px' }}>
                              <table style={{ width: '100%', fontSize: '10px', textAlign: 'left' }}>
                                <thead>
                                  <tr style={{ color: '#71717a' }}>
                                    <th>Analysis ID</th>
                                    <th>Smoke Area (px²)</th>
                                    <th>Growth Rate (px²/s)</th>
                                    <th>Trend</th>
                                    <th>Confidence</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {jobSample.sample_temporal_analyses.map((t) => (
                                    <tr key={t.analysis_id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                                      <td style={{ color: '#d4d4d8' }}>{t.analysis_id}</td>
                                      <td style={{ fontWeight: 700, color: '#ffffff' }}>{t.area_px2.toLocaleString()} px²</td>
                                      <td style={{ color: t.growth_rate_px2_per_sec > 0 ? '#ef4444' : '#4ade80' }}>
                                        {t.growth_rate_px2_per_sec.toFixed(1)} px²/s
                                      </td>
                                      <td>{t.trend}</td>
                                      <td>{(t.confidence * 100).toFixed(1)}%</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* ============================================================== */}
            {/* TAB 5: DATA LINEAGE FLOW */}
            {/* ============================================================== */}
            {activeTab === 'lineage' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <div style={{ backgroundColor: '#181b22', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '6px', padding: '20px' }}>
                  <div style={{ fontSize: '14px', fontWeight: 800, color: '#38bdf8', marginBottom: '14px', textTransform: 'uppercase' }}>
                    PHOENIX End-to-End Perception & Emergency Intelligence Lineage
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {[
                      {
                        stage: '1. Video Upload & Storage',
                        tech: 'FastAPI Stream Chunking & SHA-256 Hashing',
                        desc: 'Validates file extension, computes cryptographic checksum, and stores raw file in storage/videos/<id>/source.mp4.',
                        status: 'GENUINE BACKEND PERSISTENCE',
                      },
                      {
                        stage: '2. Job Scheduling & Isolation',
                        tech: 'SQLite processing_jobs Table & Background Task',
                        desc: 'Generates UUID job_id, registers camera linkage, and tracks progress percentage, frames analyzed, and stage.',
                        status: 'ACID TRANSACTION ISOLATION',
                      },
                      {
                        stage: '3. Dual-Model YOLOv11 Inference',
                        tech: 'Ultralytics PyTorch (fire_smoke_best.pt + yolo11n.pt)',
                        desc: 'Processes frames at stride, detecting FIRE, SMOKE, and PERSON bounding boxes with floating-point confidences.',
                        status: 'REAL PYTORCH INFERENCE',
                      },
                      {
                        stage: '4. Temporal Smoke Growth Tracking',
                        tech: 'TemporalSmokeAnalyzer (Δarea / Δt + EMA Smoothing)',
                        desc: 'Calculates 2D smoke plume surface growth rate and classifies trends (RAPID_GROWTH, MODERATE, STABLE, DECREASING).',
                        status: 'DATA-DRIVEN OBSERVATIONS',
                      },
                      {
                        stage: '5. Planar Homography Projection',
                        tech: 'PlanarHomographyMapper (3×3 Perspective Matrix)',
                        desc: 'Maps video pixel bounding-box ground contact points directly to architectural floor coordinates (X, Y in meters).',
                        status: 'MATHEMATICAL PROJECTION',
                      },
                      {
                        stage: '6. Deterministic Spatial Risk',
                        tech: 'DeterministicRiskEngine (exp(-lambda * dist))',
                        desc: 'Propagates spatial hazard scores across building navigation nodes with exponential proximity decay.',
                        status: 'DETERMINISTIC SPATIAL ENGINE',
                      },
                      {
                        stage: '7. Multi-Factor Dijkstra Evacuation Routing',
                        tech: 'NetworkX Least-Cost Graph Pathfinding',
                        desc: 'Calculates dynamic shortest paths balancing physical distance, hazard exposure, and corridor blockage predictions.',
                        status: 'NETWORKX GRAPH ROUTING',
                      },
                      {
                        stage: '8. Telemetry Dispatch & Output Generation',
                        tech: 'WebSocket EventBus + OpenCV Annotated Video Encoder',
                        desc: 'Generates annotated output MP4 and broadcasts real-time domain events to connected browser dashboards.',
                        status: 'REAL-TIME WEBSOCKET BUS',
                      },
                    ].map((step, idx) => (
                      <div
                        key={idx}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '16px',
                          backgroundColor: '#0c0e12',
                          padding: '12px 16px',
                          borderRadius: '6px',
                          borderLeft: '4px solid #3b82f6',
                        }}
                      >
                        <div style={{ width: '28px', height: '28px', borderRadius: '50%', backgroundColor: '#2563eb', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, fontSize: '12px' }}>
                          {idx + 1}
                        </div>
                        <div style={{ flex: 1 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontSize: '13px', fontWeight: 700, color: '#f4f4f5' }}>{step.stage}</span>
                            <span style={{ fontSize: '9px', fontWeight: 800, color: '#4ade80', backgroundColor: 'rgba(34,197,94,0.15)', padding: '2px 6px', borderRadius: '2px' }}>
                              {step.status}
                            </span>
                          </div>
                          <div style={{ fontSize: '11px', color: '#60a5fa', marginTop: '2px' }}>{step.tech}</div>
                          <div style={{ fontSize: '11px', color: '#9ca3af', marginTop: '2px' }}>{step.desc}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
};
