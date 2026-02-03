import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDropzone } from 'react-dropzone';
import { ingestFile } from '../services/api';

const Upload = () => {
  const navigate = useNavigate();
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState({});
  const [metadata, setMetadata] = useState({
    subject_id: '',
    session_id: '',
    task: '',
    montage: 'standard_1020',
    notes: '',
  });

  const onDrop = useCallback((acceptedFiles) => {
    const newFiles = acceptedFiles.map(file => ({
      file,
      id: Math.random().toString(36).substr(2, 9),
      status: 'pending',
    }));
    setFiles(prev => [...prev, ...newFiles]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/octet-stream': ['.edf', '.bdf', '.fif', '.set'],
    },
    multiple: true,
  });

  const removeFile = (id) => {
    setFiles(files.filter(f => f.id !== id));
  };

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  const handleUpload = async () => {
    if (files.length === 0) return;
    
    setUploading(true);
    
    for (const fileObj of files) {
      try {
        setUploadProgress(prev => ({ ...prev, [fileObj.id]: 0 }));
        setFiles(prev => prev.map(f => 
          f.id === fileObj.id ? { ...f, status: 'uploading' } : f
        ));

        await ingestFile(fileObj.file, {
          subject_id: metadata.subject_id,
          session_id: metadata.session_id,
          meta: { task: metadata.task, montage: metadata.montage, notes: metadata.notes }
        });

        setFiles(prev => prev.map(f => 
          f.id === fileObj.id ? { ...f, status: 'completed' } : f
        ));
      } catch (error) {
        console.error('Upload failed:', error);
        setFiles(prev => prev.map(f => 
          f.id === fileObj.id ? { ...f, status: 'failed', error: error.message } : f
        ));
      }
    }

    setUploading(false);
    
    // Navigate to recordings after successful upload
    const allCompleted = files.every(f => f.status === 'completed');
    if (allCompleted) {
      setTimeout(() => navigate('/recordings'), 1500);
    }
  };

  const completedCount = files.filter(f => f.status === 'completed').length;
  const hasFiles = files.length > 0;

  return (
    <div>
      <div className="page-header">
        <h1>Upload Recordings</h1>
        <p>Upload EEG/MEG recordings for processing and analysis</p>
      </div>

      <div className="grid grid-2 mt-xl">
        {/* Dropzone */}
        <div className="card">
          <div 
            {...getRootProps()} 
            className={`dropzone ${isDragActive ? 'active' : ''}`}
          >
            <input {...getInputProps()} />
            <div className="dropzone-icon">
              {isDragActive ? '📥' : '🧠'}
            </div>
            <p className="dropzone-title">
              {isDragActive ? 'Drop files here' : 'Drag & drop recordings'}
            </p>
            <p className="dropzone-subtitle">
              or click to browse • Supports EDF, BDF, FIF, SET
            </p>
          </div>

          {/* File List */}
          {hasFiles && (
            <div className="mt-xl">
              <div className="flex justify-between items-center mb-md">
                <h4 style={{ margin: 0 }}>Files ({files.length})</h4>
                {completedCount > 0 && (
                  <span className="badge badge-success">
                    {completedCount} uploaded
                  </span>
                )}
              </div>
              
              <div className="flex flex-col gap-sm">
                {files.map((fileObj) => (
                  <div key={fileObj.id} className="file-item">
                    <div 
                      className="file-icon" 
                      style={{ 
                        background: fileObj.status === 'completed' 
                          ? 'var(--gradient-success)' 
                          : fileObj.status === 'failed'
                          ? 'var(--gradient-error)'
                          : 'var(--gradient-primary)'
                      }}
                    >
                      {fileObj.status === 'completed' ? '✓' : 
                       fileObj.status === 'failed' ? '✗' : '📄'}
                    </div>
                    <div className="file-info">
                      <div className="file-name">{fileObj.file.name}</div>
                      <div className="file-meta">
                        {formatFileSize(fileObj.file.size)}
                        {fileObj.status === 'uploading' && uploadProgress[fileObj.id] && (
                          <span> • {Math.round(uploadProgress[fileObj.id])}%</span>
                        )}
                      </div>
                      {fileObj.status === 'uploading' && (
                        <div className="progress-bar mt-sm" style={{ height: '4px' }}>
                          <div 
                            className="progress-bar-fill" 
                            style={{ width: `${uploadProgress[fileObj.id] || 0}%` }}
                          />
                        </div>
                      )}
                    </div>
                    {fileObj.status === 'pending' && (
                      <button 
                        className="btn btn-ghost btn-sm"
                        onClick={(e) => { e.stopPropagation(); removeFile(fileObj.id); }}
                      >
                        ✕
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Metadata Form */}
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">
              <span className="card-icon card-icon-primary">📝</span>
              Recording Details
            </h3>
          </div>

          <div className="form-group">
            <label className="form-label">Subject ID</label>
            <input
              type="text"
              className="form-input"
              placeholder="e.g., SUB001"
              value={metadata.subject_id}
              onChange={(e) => setMetadata({ ...metadata, subject_id: e.target.value })}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Session ID</label>
            <input
              type="text"
              className="form-input"
              placeholder="e.g., SES001"
              value={metadata.session_id}
              onChange={(e) => setMetadata({ ...metadata, session_id: e.target.value })}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Task / Paradigm</label>
            <input
              type="text"
              className="form-input"
              placeholder="e.g., resting-state, oddball, motor"
              value={metadata.task}
              onChange={(e) => setMetadata({ ...metadata, task: e.target.value })}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Montage</label>
            <select
              className="form-input"
              value={metadata.montage}
              onChange={(e) => setMetadata({ ...metadata, montage: e.target.value })}
            >
              <option value="standard_1020">10-20 System</option>
              <option value="standard_1010">10-10 System</option>
              <option value="standard_1005">10-05 System</option>
              <option value="biosemi64">BioSemi 64</option>
              <option value="biosemi128">BioSemi 128</option>
              <option value="biosemi256">BioSemi 256</option>
              <option value="easycap-M1">EasyCap M1</option>
              <option value="custom">Custom</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Notes</label>
            <textarea
              className="form-input"
              rows={3}
              placeholder="Additional information about this recording..."
              value={metadata.notes}
              onChange={(e) => setMetadata({ ...metadata, notes: e.target.value })}
              style={{ resize: 'vertical', minHeight: '80px' }}
            />
          </div>

          <button
            className="btn btn-primary btn-lg"
            style={{ width: '100%' }}
            onClick={handleUpload}
            disabled={!hasFiles || uploading}
          >
            {uploading ? (
              <>
                <span className="spinner spinner-sm"></span>
                Uploading...
              </>
            ) : (
              <>
                <span>📤</span>
                Upload {files.length > 0 ? `${files.length} File${files.length > 1 ? 's' : ''}` : 'Files'}
              </>
            )}
          </button>
        </div>
      </div>

      {/* Format Info */}
      <div className="card mt-xl">
        <div className="card-header">
          <h3 className="card-title">
            <span className="card-icon card-icon-primary">ℹ️</span>
            Supported Formats
          </h3>
        </div>
        <div className="grid grid-4">
          <div className="metric-card">
            <div className="metric-value" style={{ fontSize: '1.25rem' }}>EDF</div>
            <div className="metric-label">European Data Format</div>
          </div>
          <div className="metric-card">
            <div className="metric-value" style={{ fontSize: '1.25rem' }}>BDF</div>
            <div className="metric-label">BioSemi Data Format</div>
          </div>
          <div className="metric-card">
            <div className="metric-value" style={{ fontSize: '1.25rem' }}>FIF</div>
            <div className="metric-label">MNE-Python Format</div>
          </div>
          <div className="metric-card">
            <div className="metric-value" style={{ fontSize: '1.25rem' }}>SET</div>
            <div className="metric-label">EEGLAB Format</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Upload;
