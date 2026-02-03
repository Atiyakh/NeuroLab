import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getRecordings, deleteRecording, startPreprocessing } from '../services/api';

const Recordings = () => {
  const [recordings, setRecordings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    status: '',
    search: '',
  });

  useEffect(() => {
    loadRecordings();
  }, [filters.status]);

  const loadRecordings = async () => {
    try {
      setLoading(true);
      const data = await getRecordings(filters.status ? { status: filters.status } : {});
      setRecordings(data);
    } catch (error) {
      console.error('Failed to load recordings:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id, e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!window.confirm('Are you sure you want to delete this recording?')) return;
    
    try {
      await deleteRecording(id);
      setRecordings(recordings.filter(r => r.id !== id));
    } catch (error) {
      console.error('Failed to delete recording:', error);
    }
  };

  const handleProcess = async (id, e) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      await startPreprocessing(id);
      loadRecordings();
    } catch (error) {
      console.error('Failed to start processing:', error);
    }
  };

  const getStatusBadge = (status) => {
    const statusMap = {
      uploaded: 'badge-info',
      processing: 'badge-processing',
      processed: 'badge-success',
      failed: 'badge-error',
      needs_review: 'badge-warning',
    };
    return statusMap[status] || 'badge-info';
  };

  const formatDate = (date) => {
    return new Date(date).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatDuration = (seconds) => {
    if (!seconds) return '-';
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const filteredRecordings = recordings.filter(r => 
    !filters.search || r.filename.toLowerCase().includes(filters.search.toLowerCase())
  );

  const statusCounts = {
    all: recordings.length,
    uploaded: recordings.filter(r => r.status === 'uploaded').length,
    processing: recordings.filter(r => r.status === 'processing').length,
    processed: recordings.filter(r => r.status === 'processed').length,
    failed: recordings.filter(r => r.status === 'failed').length,
  };

  return (
    <div>
      <div className="page-header">
        <div className="flex justify-between items-start">
          <div>
            <h1>Recordings</h1>
            <p>Manage and process your EEG/MEG recordings</p>
          </div>
          <Link to="/upload" className="btn btn-primary">
            <span>📤</span> Upload New
          </Link>
        </div>
      </div>

      {/* Status Tabs */}
      <div className="flex gap-sm mt-xl mb-lg" style={{ flexWrap: 'wrap' }}>
        {[
          { key: '', label: 'All', count: statusCounts.all },
          { key: 'uploaded', label: 'Uploaded', count: statusCounts.uploaded },
          { key: 'processing', label: 'Processing', count: statusCounts.processing },
          { key: 'processed', label: 'Processed', count: statusCounts.processed },
          { key: 'failed', label: 'Failed', count: statusCounts.failed },
        ].map(tab => (
          <button
            key={tab.key}
            className={`btn ${filters.status === tab.key ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setFilters({ ...filters, status: tab.key })}
          >
            {tab.label}
            <span style={{ 
              marginLeft: '8px', 
              background: 'rgba(255,255,255,0.2)', 
              padding: '2px 8px', 
              borderRadius: '12px',
              fontSize: '0.75rem'
            }}>
              {tab.count}
            </span>
          </button>
        ))}
      </div>

      {/* Search */}
      <div className="card">
        <div className="flex gap-md items-center mb-lg">
          <div style={{ flex: 1 }}>
            <input
              type="text"
              className="form-input"
              placeholder="🔍 Search recordings..."
              value={filters.search}
              onChange={(e) => setFilters({ ...filters, search: e.target.value })}
            />
          </div>
          <button className="btn btn-secondary" onClick={loadRecordings}>
            ↻ Refresh
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center" style={{ padding: '60px' }}>
            <div className="spinner"></div>
          </div>
        ) : filteredRecordings.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">📂</div>
            <h3 className="empty-state-title">No recordings found</h3>
            <p className="empty-state-text">
              {filters.search || filters.status 
                ? 'Try adjusting your filters' 
                : 'Upload your first recording to get started'}
            </p>
            {!filters.search && !filters.status && (
              <Link to="/upload" className="btn btn-primary mt-md">
                Upload Recording
              </Link>
            )}
          </div>
        ) : (
          <div className="table-container">
            <table className="table">
              <thead>
                <tr>
                  <th>Recording</th>
                  <th>Channels</th>
                  <th>Duration</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredRecordings.map((recording) => (
                  <tr key={recording.id}>
                    <td>
                      <Link 
                        to={`/recordings/${recording.id}`}
                        style={{ textDecoration: 'none' }}
                      >
                        <div className="flex items-center gap-md">
                          <div 
                            className="file-icon" 
                            style={{ 
                              width: '36px', 
                              height: '36px', 
                              fontSize: '1rem',
                              background: recording.status === 'processed' 
                                ? 'var(--gradient-success)' 
                                : 'var(--gradient-primary)'
                            }}
                          >
                            🧠
                          </div>
                          <div>
                            <div className="font-semibold text-primary">{recording.filename}</div>
                            <div className="text-muted" style={{ fontSize: '0.8125rem' }}>
                              {recording.meta?.task || 'No task'} • {recording.meta?.montage || 'Unknown montage'}
                            </div>
                          </div>
                        </div>
                      </Link>
                    </td>
                    <td>
                      <span className="text-primary font-medium">{recording.channels || '-'}</span>
                    </td>
                    <td>
                      <span className="text-secondary">{formatDuration(recording.duration_sec)}</span>
                    </td>
                    <td>
                      <span className={`badge ${getStatusBadge(recording.status)}`}>
                        {recording.status === 'processing' && <span className="badge-dot"></span>}
                        {recording.status}
                      </span>
                    </td>
                    <td>
                      <span className="text-muted" style={{ fontSize: '0.875rem' }}>
                        {formatDate(recording.created_at)}
                      </span>
                    </td>
                    <td>
                      <div className="flex justify-end gap-xs">
                        {recording.status === 'uploaded' && (
                          <button
                            className="btn btn-primary btn-sm"
                            onClick={(e) => handleProcess(recording.id, e)}
                          >
                            ⚡ Process
                          </button>
                        )}
                        {recording.status === 'failed' && (
                          <button
                            className="btn btn-warning btn-sm"
                            onClick={(e) => handleProcess(recording.id, e)}
                          >
                            ↻ Retry
                          </button>
                        )}
                        <Link 
                          to={`/recordings/${recording.id}`}
                          className="btn btn-secondary btn-sm"
                        >
                          View
                        </Link>
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={(e) => handleDelete(recording.id, e)}
                          style={{ color: 'var(--accent-error)' }}
                        >
                          🗑
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default Recordings;
