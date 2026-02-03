import { io } from 'socket.io-client';

const WS_URL = process.env.REACT_APP_WS_URL || 'http://localhost:5000';

class SocketService {
  constructor() {
    this.socket = null;
    this.listeners = new Map();
  }

  connect() {
    if (this.socket?.connected) {
      return this.socket;
    }

    this.socket = io(WS_URL, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
    });

    this.socket.on('connect', () => {
      console.log('WebSocket connected');
    });

    this.socket.on('disconnect', () => {
      console.log('WebSocket disconnected');
    });

    this.socket.on('error', (error) => {
      console.error('WebSocket error:', error);
    });

    return this.socket;
  }

  disconnect() {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
  }

  // Recording room management
  joinRecording(recordingId) {
    this.connect();
    this.socket.emit('join_recording', { recording_id: recordingId });
  }

  leaveRecording(recordingId) {
    if (this.socket) {
      this.socket.emit('leave_recording', { recording_id: recordingId });
    }
  }

  // Job subscription
  subscribeToJob(jobId) {
    this.connect();
    this.socket.emit('subscribe_job', { job_id: jobId });
  }

  unsubscribeFromJob(jobId) {
    if (this.socket) {
      this.socket.emit('unsubscribe_job', { job_id: jobId });
    }
  }

  // Stream data ( real-time mode )
  streamData(recordingId, chunk, sfreq) {
    this.connect();
    this.socket.emit('stream_data', {
      recording_id: recordingId,
      chunk: chunk,
      sfreq: sfreq,
    });
  }

  // Request inference
  requestInference(recordingId, modelId) {
    this.connect();
    this.socket.emit('request_inference', {
      recording_id: recordingId,
      model_id: modelId,
    });
  }

  onRealtimeFeatures(callback) {
    this.connect();
    this.socket.on('realtime_features', callback);
    return () => this.socket.off('realtime_features', callback);
  }

  onRealtimePrediction(callback) {
    this.connect();
    this.socket.on('realtime_prediction', callback);
    return () => this.socket.off('realtime_prediction', callback);
  }

  onJobProgress(callback) {
    this.connect();
    this.socket.on('job_progress', callback);
    return () => this.socket.off('job_progress', callback);
  }

  onRecordingUpdate(callback) {
    this.connect();
    this.socket.on('recording_update', callback);
    return () => this.socket.off('recording_update', callback);
  }

  on(event, callback) {
    this.connect();
    this.socket.on(event, callback);
    return () => this.socket.off(event, callback);
  }

  off(event, callback) {
    if (this.socket) {
      this.socket.off(event, callback);
    }
  }

  emit(event, data) {
    this.connect();
    this.socket.emit(event, data);
  }
}

// Singleton instance
const socketService = new SocketService();

export default socketService;
