import React, { useState, useEffect } from 'react';
import { 
  getModels, 
  trainModel, 
  promoteModel, 
  deleteModel,
  getRecordings 
} from '../services/api';
import socketService from '../services/socket';

const Models = () => {
  const [models, setModels] = useState([]);
  const [recordings, setRecordings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showTrainModal, setShowTrainModal] = useState(false);
  const [selectedModel, setSelectedModel] = useState(null);
  const [trainForm, setTrainForm] = useState({
    name: '',
    model_type: 'random_forest',
    recording_ids: [],
    target_variable: 'label',
  });
  const [trainingJobs, setTrainingJobs] = useState({});

  useEffect(() => {
    loadModels();
    loadRecordings();

    const unsubJob = socketService.onJobProgress((data) => {
      if (data.step === 'training') {
        setTrainingJobs(prev => ({ ...prev, [data.model_id]: data }));
        if (data.progress >= 1) loadModels();
      }
    });

    return () => unsubJob();
  }, []);

  const loadModels = async () => {
    try {
      const data = await getModels();
      setModels(data);
    } catch (error) {
      console.error('Failed to load models:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadRecordings = async () => {
    try {
      const data = await getRecordings({ status: 'processed' });
      setRecordings(data.filter(r => r.features_path));
    } catch (error) {
      console.error('Failed to load recordings:', error);
    }
  };

  const handleTrainModel = async (e) => {
    e.preventDefault();
    try {
      const result = await trainModel(trainForm);
      socketService.subscribeToJob(result.job_id);
      setShowTrainModal(false);
      setTrainForm({ name: '', model_type: 'random_forest', recording_ids: [], target_variable: 'label' });
      loadModels();
    } catch (error) {
      console.error('Failed to train model:', error);
    }
  };

  const handlePromoteModel = async (modelId) => {
    try {
      await promoteModel(modelId);
      loadModels();
    } catch (error) {
      console.error('Failed to promote model:', error);
    }
  };

  const handleDeleteModel = async (modelId) => {
    if (!window.confirm('Are you sure you want to delete this model?')) return;
    try {
      await deleteModel(modelId);
      loadModels();
    } catch (error) {
      console.error('Failed to delete model:', error);
    }
  };

  const getStatusBadge = (status) => {
    const statusMap = {
      training: 'badge-processing',
      trained: 'badge-success',
      failed: 'badge-error',
      production: 'badge-info',
    };
    return statusMap[status] || 'badge-info';
  };

  const toggleRecordingSelection = (recordingId) => {
    setTrainForm(prev => ({
      ...prev,
      recording_ids: prev.recording_ids.includes(recordingId)
        ? prev.recording_ids.filter(id => id !== recordingId)
        : [...prev.recording_ids, recordingId],
    }));
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
      <div className="page-header">
        <div className="flex justify-between items-start">
          <div>
            <h1>ML Models</h1>
            <p>Train, evaluate, and deploy machine learning models</p>
          </div>
          <button 
            className="btn btn-primary" 
            onClick={() => setShowTrainModal(true)}
            disabled={recordings.length === 0}
          >
            <span>🤖</span> Train New Model
          </button>
        </div>
      </div>

      {models.length === 0 ? (
        <div className="card mt-xl">
          <div className="empty-state">
            <div className="empty-state-icon">🤖</div>
            <h3 className="empty-state-title">No models trained yet</h3>
            <p className="empty-state-text">
              Train your first model to start classifying neural signals
            </p>
            {recordings.length > 0 ? (
              <button className="btn btn-primary mt-md" onClick={() => setShowTrainModal(true)}>
                Train Your First Model
              </button>
            ) : (
              <p className="text-warning mt-md">
                You need recordings with extracted features to train a model
              </p>
            )}
          </div>
        </div>
      ) : (
        <div className="grid grid-2 mt-xl">
          {models.map((model) => (
            <div 
              key={model.id} 
              className="card"
              style={model.status === 'production' ? {
                background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(6, 182, 212, 0.05) 100%)',
                borderColor: 'rgba(16, 185, 129, 0.3)'
              } : {}}
            >
              <div className="card-header">
                <h3 className="card-title">
                  {model.status === 'production' && <span style={{ marginRight: '8px' }}>🚀</span>}
                  {model.name}
                </h3>
                <span className={`badge ${getStatusBadge(model.status)}`}>
                  {model.status === 'training' && <span className="badge-dot"></span>}
                  {model.status}
                </span>
              </div>

              {/* Training progress */}
              {trainingJobs[model.id] && trainingJobs[model.id].progress < 1 && (
                <div className="mb-lg">
                  <div className="flex justify-between text-muted mb-xs" style={{ fontSize: '0.875rem' }}>
                    <span>Training...</span>
                    <span>{Math.round((trainingJobs[model.id].progress || 0) * 100)}%</span>
                  </div>
                  <div className="progress-bar">
                    <div
                      className="progress-bar-fill"
                      style={{ width: `${(trainingJobs[model.id].progress || 0) * 100}%` }}
                    />
                  </div>
                </div>
              )}

              <div className="mb-lg">
                <div className="flex gap-lg text-secondary" style={{ fontSize: '0.875rem' }}>
                  <span>Type: <strong className="text-primary">{model.model_type?.replace(/_/g, ' ')}</strong></span>
                  <span>v{model.version}</span>
                </div>
              </div>

              {/* Metrics */}
              {model.metrics && (
                <div className="grid grid-4 mb-lg" style={{ gap: 'var(--spacing-sm)' }}>
                  <div className="metric-card">
                    <div className="metric-value text-success">
                      {(model.metrics.accuracy * 100).toFixed(1)}%
                    </div>
                    <div className="metric-label">Accuracy</div>
                  </div>
                  <div className="metric-card">
                    <div className="metric-value text-primary">
                      {(model.metrics.f1_score * 100).toFixed(1)}%
                    </div>
                    <div className="metric-label">F1 Score</div>
                  </div>
                  <div className="metric-card">
                    <div className="metric-value">
                      {(model.metrics.precision * 100).toFixed(1)}%
                    </div>
                    <div className="metric-label">Precision</div>
                  </div>
                  <div className="metric-card">
                    <div className="metric-value">
                      {(model.metrics.recall * 100).toFixed(1)}%
                    </div>
                    <div className="metric-label">Recall</div>
                  </div>
                </div>
              )}

              {model.metrics?.cv_mean && (
                <p className="text-muted" style={{ fontSize: '0.875rem', marginBottom: 'var(--spacing-lg)' }}>
                  Cross-validation: {(model.metrics.cv_mean * 100).toFixed(1)}% ± {(model.metrics.cv_std * 100).toFixed(1)}%
                </p>
              )}

              {/* Actions */}
              <div className="flex gap-sm flex-wrap">
                {model.status === 'trained' && (
                  <button className="btn btn-success btn-sm" onClick={() => handlePromoteModel(model.id)}>
                    🚀 Deploy to Production
                  </button>
                )}
                <button className="btn btn-secondary btn-sm" onClick={() => setSelectedModel(model)}>
                  📊 View Details
                </button>
                {model.status !== 'production' && (
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() => handleDeleteModel(model.id)}
                    style={{ color: 'var(--accent-error)' }}
                  >
                    🗑 Delete
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Train Model Modal */}
      {showTrainModal && (
        <div className="modal-overlay" onClick={() => setShowTrainModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">Train New Model</h2>
              <button className="modal-close" onClick={() => setShowTrainModal(false)}>✕</button>
            </div>
            
            <form onSubmit={handleTrainModel}>
              <div className="form-group">
                <label className="form-label">Model Name</label>
                <input
                  type="text"
                  className="form-input"
                  value={trainForm.name}
                  onChange={(e) => setTrainForm({ ...trainForm, name: e.target.value })}
                  required
                  placeholder="e.g., Sleep Stage Classifier v1"
                />
              </div>

              <div className="form-group">
                <label className="form-label">Model Type</label>
                <select
                  className="form-input"
                  value={trainForm.model_type}
                  onChange={(e) => setTrainForm({ ...trainForm, model_type: e.target.value })}
                >
                  <option value="random_forest">Random Forest</option>
                  <option value="logistic_regression">Logistic Regression</option>
                  <option value="svm">Support Vector Machine</option>
                  <option value="gradient_boosting">Gradient Boosting</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Target Variable</label>
                <input
                  type="text"
                  className="form-input"
                  value={trainForm.target_variable}
                  onChange={(e) => setTrainForm({ ...trainForm, target_variable: e.target.value })}
                  placeholder="e.g., label, sleep_stage, condition"
                />
              </div>

              <div className="form-group">
                <label className="form-label">Training Data</label>
                <div style={{ 
                  maxHeight: '200px', 
                  overflow: 'auto',
                  border: '1px solid var(--border-color)',
                  borderRadius: 'var(--radius-lg)',
                  padding: 'var(--spacing-sm)'
                }}>
                  {recordings.map((recording) => (
                    <label 
                      key={recording.id}
                      className="flex items-center gap-sm"
                      style={{ 
                        padding: 'var(--spacing-sm) var(--spacing-md)',
                        cursor: 'pointer',
                        borderRadius: 'var(--radius-md)',
                        background: trainForm.recording_ids.includes(recording.id) 
                          ? 'var(--bg-glass-hover)' 
                          : 'transparent'
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={trainForm.recording_ids.includes(recording.id)}
                        onChange={() => toggleRecordingSelection(recording.id)}
                      />
                      <span className="text-primary">{recording.filename}</span>
                      <span className="text-muted" style={{ fontSize: '0.8125rem' }}>
                        {recording.meta?.task || 'No task'}
                      </span>
                    </label>
                  ))}
                </div>
                <span className="text-muted" style={{ fontSize: '0.8125rem', marginTop: '8px', display: 'block' }}>
                  {trainForm.recording_ids.length} recording(s) selected
                </span>
              </div>

              <div className="flex gap-md justify-end">
                <button type="button" className="btn btn-secondary" onClick={() => setShowTrainModal(false)}>
                  Cancel
                </button>
                <button 
                  type="submit" 
                  className="btn btn-primary"
                  disabled={trainForm.recording_ids.length === 0 || !trainForm.name}
                >
                  🚀 Start Training
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Model Details Modal */}
      {selectedModel && (
        <div className="modal-overlay" onClick={() => setSelectedModel(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '700px' }}>
            <div className="modal-header">
              <h2 className="modal-title">{selectedModel.name}</h2>
              <button className="modal-close" onClick={() => setSelectedModel(null)}>✕</button>
            </div>
            
            {selectedModel.metrics?.classification_report && (
              <div className="mb-lg">
                <h4 style={{ marginBottom: 'var(--spacing-md)' }}>Classification Report</h4>
                <pre style={{ 
                  fontSize: '0.75rem',
                  padding: 'var(--spacing-md)',
                  background: 'var(--bg-primary)',
                  borderRadius: 'var(--radius-md)',
                  overflow: 'auto'
                }}>
                  {selectedModel.metrics.classification_report}
                </pre>
              </div>
            )}

            {selectedModel.visualizations && (
              <div>
                <h4 style={{ marginBottom: 'var(--spacing-md)' }}>Visualizations</h4>
                <div className="grid grid-2" style={{ gap: 'var(--spacing-md)' }}>
                  {selectedModel.visualizations.confusion_matrix && (
                    <div className="viz-container">
                      <img src={selectedModel.visualizations.confusion_matrix} alt="Confusion Matrix" />
                    </div>
                  )}
                  {selectedModel.visualizations.roc_curve && (
                    <div className="viz-container">
                      <img src={selectedModel.visualizations.roc_curve} alt="ROC Curve" />
                    </div>
                  )}
                  {selectedModel.visualizations.feature_importance && (
                    <div className="viz-container" style={{ gridColumn: 'span 2' }}>
                      <img src={selectedModel.visualizations.feature_importance} alt="Feature Importance" />
                    </div>
                  )}
                </div>
              </div>
            )}

            {selectedModel.hyperparameters && Object.keys(selectedModel.hyperparameters).length > 0 && (
              <details className="mt-lg">
                <summary>Hyperparameters</summary>
                <pre style={{ fontSize: '0.75rem' }}>
                  {JSON.stringify(selectedModel.hyperparameters, null, 2)}
                </pre>
              </details>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default Models;
