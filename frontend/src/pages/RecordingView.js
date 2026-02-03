import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { 
  getRecording, 
  startPreprocessing, 
  extractFeatures,
  getRecordingPreview 
} from '../services/api';
import socketService from '../services/socket';

const RecordingView = () => {
  const { id } = useParams();
  const [recording, setRecording] = useState(null);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [processingJob, setProcessingJob] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');

  useEffect(() => {
    loadRecording();
    loadPreview();

    socketService.joinRecording(id);
    const unsubRecording = socketService.onRecordingUpdate((data) => {
      if (data.recording_id === id) {
        loadRecording();
      }
    });
    const unsubJob = socketService.onJobProgress((data) => {
      setProcessingJob(prev => prev?.id === data.job_id ? { ...prev, ...data } : prev);
    });

    return () => {
      socketService.leaveRecording(id);
      unsubRecording();
      unsubJob();
    };
  }, [id]);

  const loadRecording = async () => {
    try {
      const data = await getRecording(id);
      setRecording(data);
      
      const activeJob = data.processing_jobs?.find(
        j => j.status === 'running' || j.status === 'pending'
      );
      setProcessingJob(activeJob);
    } catch (error) {
      console.error('Failed to load recording:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadPreview = async () => {
    try {
      const data = await getRecordingPreview(id);
      setPreview(data);
    } catch (error) {
      console.error('Failed to load preview:', error);
    }
  };

  const handleStartProcessing = async () => {
    try {
      const result = await startPreprocessing(id);
      setProcessingJob({ id: result.job_id, status: 'pending', progress: 0 });
      socketService.subscribeToJob(result.job_id);
      loadRecording();
    } catch (error) {
      console.error('Failed to start preprocessing:', error);
    }
  };

  const handleExtractFeatures = async () => {
    try {
      const result = await extractFeatures(id);
      setProcessingJob({ id: result.job_id, status: 'pending', progress: 0 });
      socketService.subscribeToJob(result.job_id);
      loadRecording();
    } catch (error) {
      console.error('Failed to start feature extraction:', error);
    }
  };

  const getStatusBadge = (status) => {
    const statusMap = {
      uploaded: 'badge-info',
      processing: 'badge-processing',
      processed: 'badge-success',
      failed: 'badge-error',
      needs_review: 'badge-warning',
      pending: 'badge-info',
      running: 'badge-processing',
      completed: 'badge-success',
    };
    return statusMap[status] || 'badge-info';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center" style={{ minHeight: '60vh' }}>
        <div className="spinner"></div>
      </div>
    );
  }

  if (!recording) {
    return (
      <div className="card">
        <div className="empty-state">
          <div className="empty-state-icon">❌</div>
          <h3 className="empty-state-title">Recording not found</h3>
          <Link to="/recordings" className="btn btn-primary mt-md">
            Back to Recordings
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="page-header">
        <Link to="/recordings" className="text-muted" style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
          ← Back to Recordings
        </Link>
        <div className="flex justify-between items-start">
          <div>
            <div className="flex items-center gap-md">
              <h1 style={{ marginBottom: '8px' }}>{recording.filename}</h1>
              <span className={`badge ${getStatusBadge(recording.status)}`}>
                {recording.status === 'processing' && <span className="badge-dot"></span>}
                {recording.status}
              </span>
            </div>
            <p style={{ margin: 0 }}>
              {recording.meta?.task || 'No task'} • {recording.meta?.montage || 'Unknown montage'}
            </p>
          </div>
          <div className="flex gap-md">
            {recording.status === 'uploaded' && (
              <button className="btn btn-primary" onClick={handleStartProcessing}>
                ⚡ Start Processing
              </button>
            )}
            {recording.status === 'processed' && !recording.features_path && (
              <button className="btn btn-primary" onClick={handleExtractFeatures}>
                📊 Extract Features
              </button>
            )}
            {recording.status === 'failed' && (
              <button className="btn btn-warning" onClick={handleStartProcessing}>
                ↻ Retry Processing
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Processing Progress */}
      {processingJob && (processingJob.status === 'running' || processingJob.status === 'pending') && (
        <div className="card" style={{ 
          background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(139, 92, 246, 0.05) 100%)',
          borderColor: 'rgba(99, 102, 241, 0.2)'
        }}>
          <div className="flex justify-between items-center mb-md">
            <div className="flex items-center gap-md">
              <div className="spinner spinner-sm"></div>
              <span className="font-semibold">Processing: {processingJob.step}</span>
            </div>
            <span className="text-muted">{Math.round((processingJob.progress || 0) * 100)}%</span>
          </div>
          <div className="progress-bar progress-bar-lg">
            <div
              className="progress-bar-fill"
              style={{ width: `${(processingJob.progress || 0) * 100}%` }}
            />
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-xs mb-lg" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '1px' }}>
        {['overview', 'processing', 'visualizations'].map(tab => (
          <button
            key={tab}
            className={`btn ${activeTab === tab ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => setActiveTab(tab)}
            style={{ borderRadius: 'var(--radius-md) var(--radius-md) 0 0' }}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {/* Overview Tab */}
      {activeTab === 'overview' && (
        <div className="grid grid-2">
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">
                <span className="card-icon card-icon-primary">📋</span>
                Recording Info
              </h3>
            </div>
            <div className="grid grid-2" style={{ gap: 'var(--spacing-lg)' }}>
              <div>
                <div className="stat-label">Channels</div>
                <div className="font-semibold text-primary" style={{ fontSize: '1.25rem' }}>
                  {recording.channels || 'Unknown'}
                </div>
              </div>
              <div>
                <div className="stat-label">Sample Rate</div>
                <div className="font-semibold text-primary" style={{ fontSize: '1.25rem' }}>
                  {recording.sfreq ? `${recording.sfreq} Hz` : 'Unknown'}
                </div>
              </div>
              <div>
                <div className="stat-label">Duration</div>
                <div className="font-semibold text-primary" style={{ fontSize: '1.25rem' }}>
                  {recording.duration_sec 
                    ? `${Math.floor(recording.duration_sec / 60)}:${String(Math.round(recording.duration_sec % 60)).padStart(2, '0')}`
                    : 'Unknown'
                  }
                </div>
              </div>
              <div>
                <div className="stat-label">Format</div>
                <div className="font-semibold text-primary" style={{ fontSize: '1.25rem' }}>
                  {recording.meta?.format || 'Unknown'}
                </div>
              </div>
            </div>
            
            <div style={{ marginTop: 'var(--spacing-xl)', paddingTop: 'var(--spacing-lg)', borderTop: '1px solid var(--border-color)' }}>
              <div className="stat-label mb-sm">Subject</div>
              <div className="text-secondary">{recording.meta?.subject_id || 'Not specified'}</div>
              
              <div className="stat-label mb-sm mt-md">Session</div>
              <div className="text-secondary">{recording.meta?.session_id || 'Not specified'}</div>
              
              <div className="stat-label mb-sm mt-md">Created</div>
              <div className="text-secondary">{new Date(recording.created_at).toLocaleString()}</div>
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <h3 className="card-title">
                <span className="card-icon card-icon-success">🔬</span>
                Processing Summary
              </h3>
            </div>
            {recording.meta?.ica_info ? (
              <div>
                <div className="grid grid-2" style={{ gap: 'var(--spacing-lg)' }}>
                  <div className="metric-card">
                    <div className="metric-value text-warning">
                      {recording.meta.bad_channels?.length || 0}
                    </div>
                    <div className="metric-label">Bad Channels</div>
                  </div>
                  <div className="metric-card">
                    <div className="metric-value text-primary">
                      {recording.meta.ica_info.excluded_components?.length || 0}
                    </div>
                    <div className="metric-label">ICA Rejected</div>
                  </div>
                </div>
                
                {recording.meta.bad_channels?.length > 0 && (
                  <div className="mt-lg">
                    <div className="stat-label mb-sm">Removed Channels</div>
                    <div className="flex gap-xs flex-wrap">
                      {recording.meta.bad_channels.map(ch => (
                        <span key={ch} className="badge badge-warning">{ch}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="empty-state" style={{ padding: 'var(--spacing-xl)' }}>
                <div className="empty-state-icon" style={{ fontSize: '3rem' }}>⏳</div>
                <p className="empty-state-title">Not processed yet</p>
                <p className="empty-state-text">Run preprocessing to see analysis results</p>
              </div>
            )}
            
            {recording.meta?.feature_summary && (
              <div style={{ marginTop: 'var(--spacing-xl)', paddingTop: 'var(--spacing-lg)', borderTop: '1px solid var(--border-color)' }}>
                <h4 style={{ marginBottom: 'var(--spacing-md)' }}>Feature Summary</h4>
                <div className="grid grid-2" style={{ gap: 'var(--spacing-md)' }}>
                  <div className="metric-card">
                    <div className="metric-value">{recording.meta.feature_summary.n_epochs}</div>
                    <div className="metric-label">Epochs</div>
                  </div>
                  <div className="metric-card">
                    <div className="metric-value">{recording.meta.feature_summary.n_features}</div>
                    <div className="metric-label">Features</div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Processing Tab */}
      {activeTab === 'processing' && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">
              <span className="card-icon card-icon-warning">⚙️</span>
              Processing History
            </h3>
          </div>
          
          {recording.processing_jobs?.length > 0 ? (
            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    <th>Step</th>
                    <th>Status</th>
                    <th>Started</th>
                    <th>Finished</th>
                    <th>Duration</th>
                  </tr>
                </thead>
                <tbody>
                  {recording.processing_jobs.map((job) => {
                    const duration = job.started_at && job.finished_at
                      ? Math.round((new Date(job.finished_at) - new Date(job.started_at)) / 1000)
                      : null;
                    
                    return (
                      <tr key={job.id}>
                        <td>
                          <span className="font-medium text-primary">{job.step}</span>
                        </td>
                        <td>
                          <span className={`badge ${getStatusBadge(job.status)}`}>
                            {job.status === 'running' && <span className="badge-dot"></span>}
                            {job.status}
                          </span>
                        </td>
                        <td className="text-muted">
                          {job.started_at ? new Date(job.started_at).toLocaleString() : '-'}
                        </td>
                        <td className="text-muted">
                          {job.finished_at ? new Date(job.finished_at).toLocaleString() : '-'}
                        </td>
                        <td className="text-secondary">
                          {duration ? `${duration}s` : '-'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty-state">
              <div className="empty-state-icon">📋</div>
              <p className="empty-state-title">No processing history</p>
              <p className="empty-state-text">Processing jobs will appear here once started</p>
            </div>
          )}
        </div>
      )}

      {/* Visualizations Tab */}
      {activeTab === 'visualizations' && (
        <div>
          {preview?.visualizations && Object.keys(preview.visualizations).length > 0 ? (
            <div className="grid grid-2">
              {Object.entries(preview.visualizations).map(([type, url]) => (
                <div key={type} className="card">
                  <div className="card-header">
                    <h3 className="card-title" style={{ textTransform: 'capitalize' }}>
                      {type.replace(/_/g, ' ')}
                    </h3>
                  </div>
                  <div className="viz-container">
                    <img src={url} alt={type} />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="card">
              <div className="empty-state">
                <div className="empty-state-icon">📊</div>
                <p className="empty-state-title">No visualizations yet</p>
                <p className="empty-state-text">Process this recording to generate visualizations</p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Downloads */}
      <div className="card mt-lg">
        <div className="card-header">
          <h3 className="card-title">
            <span className="card-icon card-icon-primary">📥</span>
            Downloads
          </h3>
        </div>
        <div className="flex gap-md">
          {recording.raw_url && (
            <a href={recording.raw_url} className="btn btn-secondary" download>
              📄 Raw Data
            </a>
          )}
          {recording.processed_url && (
            <a href={recording.processed_url} className="btn btn-secondary" download>
              ✨ Processed Data
            </a>
          )}
          {recording.features_path && (
            <a href={recording.features_url} className="btn btn-secondary" download>
              📊 Features (Parquet)
            </a>
          )}
          {!recording.raw_url && !recording.processed_url && (
            <p className="text-muted">No downloads available</p>
          )}
        </div>
      </div>
    </div>
  );
};

export default RecordingView;
