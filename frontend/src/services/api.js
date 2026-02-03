import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000';

const api = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export const ingestFile = async (file, metadata = {}) => {
  const formData = new FormData();
  formData.append('file', file);
  
  if (metadata.subject_id) {
    formData.append('subject_id', metadata.subject_id);
  }
  if (metadata.session_id) {
    formData.append('session_id', metadata.session_id);
  }
  formData.append('meta', JSON.stringify(metadata.meta || {}));
  
  const response = await api.post('/ingest', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const validateFile = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await api.post('/ingest/validate', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const getSubjects = async () => {
  const response = await api.get('/subjects');
  return response.data;
};

export const createSubject = async (data) => {
  const response = await api.post('/subjects', data);
  return response.data;
};

export const getRecordings = async (params = {}) => {
  const response = await api.get('/recordings', { params });
  return response.data;
};

export const getRecording = async (id) => {
  const response = await api.get(`/recordings/${id}`);
  return response.data;
};

export const updateRecording = async (id, data) => {
  const response = await api.patch(`/recordings/${id}`, data);
  return response.data;
};

export const deleteRecording = async (id) => {
  const response = await api.delete(`/recordings/${id}`);
  return response.data;
};

export const startPreprocessing = async (id, params = {}) => {
  const response = await api.post(`/recordings/${id}/start_preprocess`, { params });
  return response.data;
};

export const extractFeatures = async (id, params = {}) => {
  const response = await api.post(`/recordings/${id}/extract_features`, { params });
  return response.data;
};

export const getRecordingJobs = async (id) => {
  const response = await api.get(`/recordings/${id}/jobs`);
  return response.data;
};

export const getRecordingVisualizations = async (id) => {
  const response = await api.get(`/recordings/${id}/visualizations`);
  return response.data;
};

// Jobs API
export const getJob = async (id) => {
  const response = await api.get(`/jobs/${id}`);
  return response.data;
};

export const cancelJob = async (id) => {
  const response = await api.post(`/jobs/${id}/cancel`);
  return response.data;
};

// Models API
export const getModels = async (params = {}) => {
  const response = await api.get('/models', { params });
  return response.data;
};

export const getModel = async (id) => {
  const response = await api.get(`/models/${id}`);
  return response.data;
};

export const trainModel = async (data) => {
  const response = await api.post('/models/train', data);
  return response.data;
};

export const promoteModel = async (id, stage) => {
  const response = await api.post(`/models/${id}/promote`, { stage });
  return response.data;
};

export const deleteModel = async (id) => {
  const response = await api.delete(`/models/${id}`);
  return response.data;
};

export const predict = async (modelId, data) => {
  const response = await api.post(`/models/${modelId}/predict`, data);
  return response.data;
};

export const getProductionModel = async () => {
  const response = await api.get('/models/production');
  return response.data;
};

export const compareModels = async (modelIds) => {
  const response = await api.post('/models/compare', { model_ids: modelIds });
  return response.data;
};

// Dashboard API
export const getDashboardStats = async () => {
  const response = await api.get('/dashboard/stats');
  return response.data;
};

export const getRecentRecordings = async (limit = 10) => {
  const response = await api.get('/dashboard/recent_recordings', { params: { limit } });
  return response.data;
};

export const getRecentJobs = async (limit = 10) => {
  const response = await api.get('/dashboard/recent_jobs', { params: { limit } });
  return response.data;
};

export const getRecordingPreview = async (id) => {
  const response = await api.get(`/dashboard/recording/${id}/preview`);
  return response.data;
};

export const getModelMetrics = async (id) => {
  const response = await api.get(`/dashboard/model/${id}/metrics`);
  return response.data;
};

export const healthCheck = async () => {
  const response = await api.get('/dashboard/system/health');
  return response.data;
};

// Auth API
export const login = async (username, password) => {
  const response = await api.post('/auth/login', { username, password });
  return response.data;
};

export const register = async (data) => {
  const response = await api.post('/auth/register', data);
  return response.data;
};

export const refreshToken = async () => {
  const response = await api.post('/auth/refresh');
  return response.data;
};

export const getCurrentUser = async () => {
  const response = await api.get('/auth/me');
  return response.data;
};

export default api;
