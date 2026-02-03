import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getDashboardStats, getRecentRecordings, getRecentJobs } from '../services/api';

const Dashboard = () => {
  const [stats, setStats] = useState(null);
  const [recentRecordings, setRecentRecordings] = useState([]);
  const [recentJobs, setRecentJobs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboardData();
    const interval = setInterval(loadDashboardData, 30000);
    return () => clearInterval(interval);
  }, []);

  const loadDashboardData = async () => {
    try {
      const [statsData, recordingsData, jobsData] = await Promise.all([
        getDashboardStats(),
        getRecentRecordings(5),
        getRecentJobs(5),
      ]);
      setStats(statsData);
      setRecentRecordings(recordingsData);
      setRecentJobs(jobsData);
    } catch (error) {
      console.error('Failed to load dashboard data:', error);
    } finally {
      setLoading(false);
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

  const formatTimeAgo = (date) => {
    const seconds = Math.floor((new Date() - new Date(date)) / 1000);
    if (seconds < 60) return 'Just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center" style={{ minHeight: '60vh' }}>
        <div className="spinner"></div>
      </div>
    );
  }

  return (
    <div>
      {/* Hero Section */}
      <div className="page-header">
        <h1>Welcome to NeuroLab</h1>
        <p>Your computational neuroscience command center</p>
        <div className="quick-actions">
          <Link to="/upload" className="btn btn-primary btn-lg">
            <span>📤</span> Upload Recording
          </Link>
          <Link to="/realtime" className="btn btn-secondary btn-lg">
            <span>📡</span> Real-time Analysis
          </Link>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-4 mt-xl">
        <div className="stat-card">
          <div className="stat-card-gradient" style={{ background: 'var(--accent-primary)' }}></div>
          <div className="stat-icon" style={{ background: 'rgba(99, 102, 241, 0.15)' }}>📊</div>
          <div className="stat-value">{stats?.recordings?.total || 0}</div>
          <div className="stat-label">Total Recordings</div>
        </div>
        
        <div className="stat-card">
          <div className="stat-card-gradient" style={{ background: 'var(--accent-success)' }}></div>
          <div className="stat-icon" style={{ background: 'rgba(16, 185, 129, 0.15)' }}>✅</div>
          <div className="stat-value">{stats?.recordings?.processed || 0}</div>
          <div className="stat-label">Processed</div>
        </div>
        
        <div className="stat-card">
          <div className="stat-card-gradient" style={{ background: 'var(--accent-warning)' }}></div>
          <div className="stat-icon" style={{ background: 'rgba(245, 158, 11, 0.15)' }}>⚡</div>
          <div className="stat-value">{stats?.jobs?.running || 0}</div>
          <div className="stat-label">Active Jobs</div>
        </div>
        
        <div className="stat-card">
          <div className="stat-card-gradient" style={{ background: 'var(--accent-cyan)' }}></div>
          <div className="stat-icon" style={{ background: 'rgba(6, 182, 212, 0.15)' }}>🤖</div>
          <div className="stat-value">{stats?.models?.total || 0}</div>
          <div className="stat-label">Trained Models</div>
        </div>
      </div>

      {/* Production Model Card */}
      {stats?.models?.production && (
        <div className="card mt-xl" style={{ 
          background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(6, 182, 212, 0.05) 100%)',
          borderColor: 'rgba(16, 185, 129, 0.2)'
        }}>
          <div className="card-header">
            <h3 className="card-title">
              <span className="card-icon card-icon-success">🚀</span>
              Production Model Active
            </h3>
            <span className="badge badge-success">
              <span className="badge-dot"></span>
              LIVE
            </span>
          </div>
          <div className="grid grid-4">
            <div>
              <div className="stat-label">Model Name</div>
              <div className="font-semibold text-primary">{stats.models.production.name}</div>
            </div>
            <div>
              <div className="stat-label">Accuracy</div>
              <div className="font-semibold text-success" style={{ fontSize: '1.25rem' }}>
                {((stats.models.production.metrics?.accuracy || 0) * 100).toFixed(1)}%
              </div>
            </div>
            <div>
              <div className="stat-label">F1 Score</div>
              <div className="font-semibold text-primary" style={{ fontSize: '1.25rem' }}>
                {((stats.models.production.metrics?.f1_score || 0) * 100).toFixed(1)}%
              </div>
            </div>
            <div>
              <div className="stat-label">Predictions Today</div>
              <div className="font-semibold text-primary" style={{ fontSize: '1.25rem' }}>
                {stats.models.production.predictions_today || 0}
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-2 mt-xl">
        {/* Recent Recordings */}
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">
              <span className="card-icon card-icon-primary">📁</span>
              Recent Recordings
            </h3>
            <Link to="/recordings" className="btn btn-ghost btn-sm">View All →</Link>
          </div>
          
          {recentRecordings.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">📂</div>
              <p className="empty-state-title">No recordings yet</p>
              <p className="empty-state-text">Upload your first EEG recording to get started</p>
            </div>
          ) : (
            <div className="flex flex-col gap-sm">
              {recentRecordings.map((recording) => (
                <Link 
                  key={recording.id} 
                  to={`/recordings/${recording.id}`}
                  className="file-item"
                  style={{ textDecoration: 'none' }}
                >
                  <div className="file-icon">🧠</div>
                  <div className="file-info">
                    <div className="file-name">{recording.filename}</div>
                    <div className="file-meta">
                      {recording.channels} channels • {formatTimeAgo(recording.created_at)}
                    </div>
                  </div>
                  <span className={`badge ${getStatusBadge(recording.status)}`}>
                    {recording.status}
                  </span>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Recent Jobs */}
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">
              <span className="card-icon card-icon-warning">⚙️</span>
              Processing Activity
            </h3>
          </div>
          
          {recentJobs.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">⏳</div>
              <p className="empty-state-title">No recent activity</p>
              <p className="empty-state-text">Processing jobs will appear here</p>
            </div>
          ) : (
            <div className="flex flex-col">
              {recentJobs.map((job) => (
                <div key={job.id} className="activity-item">
                  <div 
                    className="activity-icon" 
                    style={{ 
                      background: job.status === 'completed' 
                        ? 'rgba(16, 185, 129, 0.15)' 
                        : job.status === 'failed'
                        ? 'rgba(239, 68, 68, 0.15)'
                        : 'rgba(99, 102, 241, 0.15)'
                    }}
                  >
                    {job.status === 'completed' ? '✓' : job.status === 'failed' ? '✗' : '⟳'}
                  </div>
                  <div className="activity-content">
                    <div className="activity-title">
                      {job.step === 'preprocessing' && 'Preprocessing'}
                      {job.step === 'feature_extraction' && 'Feature Extraction'}
                      {job.step === 'training' && 'Model Training'}
                    </div>
                    <div className="activity-meta">
                      {job.recording_name || 'Recording'} • {formatTimeAgo(job.created_at)}
                    </div>
                    {job.status === 'running' && job.progress !== undefined && (
                      <div className="progress-bar mt-sm" style={{ height: '4px' }}>
                        <div 
                          className="progress-bar-fill" 
                          style={{ width: `${job.progress * 100}%` }}
                        />
                      </div>
                    )}
                  </div>
                  <span className={`badge ${getStatusBadge(job.status)}`}>
                    {job.status}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Getting Started */}
      {(stats?.recordings?.total || 0) === 0 && (
        <div className="card mt-xl" style={{ textAlign: 'center' }}>
          <div className="empty-state">
            <div className="empty-state-icon">🚀</div>
            <h3 className="empty-state-title">Get Started with NeuroLab</h3>
            <p className="empty-state-text">
              Upload your EEG/MEG recordings to begin preprocessing, feature extraction, and machine learning analysis.
            </p>
            <div className="flex justify-center gap-md mt-lg">
              <Link to="/upload" className="btn btn-primary btn-lg">
                Upload First Recording
              </Link>
              <a href="https://github.com/neurolab" className="btn btn-secondary btn-lg" target="_blank" rel="noreferrer">
                View Documentation
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;
