"""
Real-time processing Celery tasks
Handles streaming data and live inference
"""
import json
import numpy as np
from datetime import datetime
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


class RealtimeBuffer:
    """
    Ring buffer for real-time EEG data.
    Stores data in Redis for cross-worker access.
    """
    
    def __init__(self, recording_id: str, sfreq: int, buffer_seconds: int = 30, n_channels: int = 64):
        self.recording_id = recording_id
        self.sfreq = sfreq
        self.buffer_seconds = buffer_seconds
        self.n_channels = n_channels
        self.buffer_size = sfreq * buffer_seconds
        
        self._redis = None
        self._key = f"realtime_buffer:{recording_id}"
    
    @property
    def redis(self):
        if self._redis is None:
            import redis
            import os
            self._redis = redis.from_url(os.environ.get('REDIS_URL', 'redis://localhost:6379/0'))
        return self._redis
    
    def append(self, data: np.ndarray):
        """
        Append new data to buffer.
        
        Args:
            data: Shape (n_channels, n_samples)
        """
        # Get current buffer
        current = self._get_buffer()
        
        # Append new data
        if current is not None:
            combined = np.concatenate([current, data], axis=1)
            # Keep only last buffer_size samples
            if combined.shape[1] > self.buffer_size:
                combined = combined[:, -self.buffer_size:]
        else:
            combined = data[:, -self.buffer_size:] if data.shape[1] > self.buffer_size else data
        
        # Store back
        self._set_buffer(combined)
    
    def get_data(self, duration_sec: float = None) -> np.ndarray:
        """
        Get data from buffer.
        
        Args:
            duration_sec: Duration to retrieve (None = all)
            
        Returns:
            Data array
        """
        data = self._get_buffer()
        if data is None:
            return None
        
        if duration_sec is not None:
            n_samples = int(duration_sec * self.sfreq)
            return data[:, -n_samples:]
        
        return data
    
    def _get_buffer(self) -> np.ndarray:
        """Get buffer from Redis."""
        data = self.redis.get(self._key)
        if data is None:
            return None
        return np.frombuffer(data, dtype=np.float64).reshape(self.n_channels, -1)
    
    def _set_buffer(self, data: np.ndarray):
        """Set buffer in Redis."""
        self.redis.setex(
            self._key,
            self.buffer_seconds * 2,  # TTL
            data.tobytes()
        )
    
    def clear(self):
        """Clear the buffer."""
        self.redis.delete(self._key)


@shared_task(bind=True, name='app.tasks.realtime.process_realtime_chunk')
def process_realtime_chunk(self, recording_id: str, chunk_data: list, sfreq: int):
    """
    Process a chunk of real-time data.
    
    Args:
        recording_id: Recording ID
        chunk_data: List of channel data
        sfreq: Sampling frequency
    """
    from flask import current_app
    from app import create_app
    from app.processing.preprocessing import PreprocessingPipeline
    from app.processing.features import FeatureExtractor
    
    app = create_app()
    
    with app.app_context():
        config = current_app.config.get('PROCESSING_CONFIG', {})
        
        try:
            # Convert to numpy array
            data = np.array(chunk_data)
            
            # Initialize buffer
            buffer = RealtimeBuffer(
                recording_id,
                sfreq,
                buffer_seconds=config.get('realtime', {}).get('buffer_seconds', 30),
                n_channels=data.shape[0]
            )
            
            # Append to buffer
            buffer.append(data)
            
            # Get full buffer for processing
            buffer_data = buffer.get_data()
            if buffer_data is None or buffer_data.shape[1] < sfreq * 2:
                return {'status': 'buffering', 'samples': data.shape[1]}
            
            # Apply lightweight preprocessing (no ICA for real-time)
            # Just notch + bandpass
            from scipy import signal
            
            # Notch filter
            notch_freq = config.get('notch_freqs', [50])[0]
            b_notch, a_notch = signal.iirnotch(notch_freq, 30, sfreq)
            processed = signal.filtfilt(b_notch, a_notch, buffer_data, axis=1)
            
            # Bandpass filter
            bandpass = config.get('bandpass', {'low': 1.0, 'high': 40.0})
            b_bp, a_bp = signal.butter(4, [bandpass['low'], bandpass['high']], btype='band', fs=sfreq)
            processed = signal.filtfilt(b_bp, a_bp, processed, axis=1)
            
            # Extract features on latest window
            window_sec = config.get('realtime', {}).get('hop_seconds', 1.0)
            window_samples = int(window_sec * sfreq)
            window_data = processed[:, -window_samples:]
            
            # Quick feature extraction
            features = extract_realtime_features(window_data, sfreq, config.get('features', {}))
            
            # Emit via SocketIO
            from app import socketio
            socketio.emit(
                'realtime_features',
                {
                    'recording_id': recording_id,
                    'timestamp': datetime.utcnow().isoformat(),
                    'features': features
                },
                room=f'recording_{recording_id}'
            )
            
            return {
                'status': 'processed',
                'features': features
            }
            
        except Exception as e:
            logger.error(f"Realtime processing error: {str(e)}")
            return {'status': 'error', 'error': str(e)}


def extract_realtime_features(data: np.ndarray, sfreq: float, config: dict) -> dict:
    """
    Extract features from a single window (optimized for real-time).
    
    Args:
        data: Shape (n_channels, n_samples)
        sfreq: Sampling frequency
        config: Feature config
        
    Returns:
        Dict of features
    """
    from scipy import signal
    
    bands = config.get('bands', [
        {'name': 'delta', 'low': 1, 'high': 4},
        {'name': 'theta', 'low': 4, 'high': 8},
        {'name': 'alpha', 'low': 8, 'high': 12},
        {'name': 'beta', 'low': 12, 'high': 30},
        {'name': 'gamma', 'low': 30, 'high': 45}
    ])
    
    # Compute PSD (averaged across channels)
    freqs, psd = signal.welch(data, fs=sfreq, nperseg=min(data.shape[1], int(sfreq)))
    psd_mean = psd.mean(axis=0)
    
    features = {}
    total_power = 0
    
    for band in bands:
        idx = np.logical_and(freqs >= band['low'], freqs <= band['high'])
        band_power = np.trapz(psd_mean[idx], freqs[idx])
        features[band['name']] = float(band_power)
        total_power += band_power
    
    # Relative powers
    for band in bands:
        features[f"rel_{band['name']}"] = features[band['name']] / (total_power + 1e-10)
    
    # Simple stats
    features['rms'] = float(np.sqrt(np.mean(data ** 2)))
    features['std'] = float(np.std(data))
    
    return features


@shared_task(bind=True, name='app.tasks.realtime.realtime_inference')
def realtime_inference(self, recording_id: str, model_id: str):
    """
    Run real-time inference on buffered data.
    
    Args:
        recording_id: Recording ID
        model_id: Model ID to use
    """
    from flask import current_app
    from app import create_app
    from app.models import MLModel
    from app.services.storage import storage_service
    
    app = create_app()
    
    with app.app_context():
        config = current_app.config.get('PROCESSING_CONFIG', {})
        
        try:
            model = MLModel.query.get(model_id)
            if not model:
                return {'status': 'error', 'error': 'Model not found'}
            
            # Get buffer
            sfreq = config.get('target_sfreq', 250)
            buffer = RealtimeBuffer(
                recording_id,
                sfreq,
                n_channels=64  # Assume 64 channels
            )
            
            data = buffer.get_data(duration_sec=2.0)  # 2 second window
            if data is None or data.shape[1] < sfreq:
                return {'status': 'buffering'}
            
            # Extract features
            features = extract_realtime_features(data, sfreq, config.get('features', {}))
            
            # Convert to feature vector matching model's expected features
            feature_names = model.feature_names or list(features.keys())
            X = np.array([[features.get(f, 0) for f in feature_names]])
            
            # Load model and predict
            import tempfile
            import joblib
            
            temp_dir = tempfile.mkdtemp()
            try:
                model_path = model.s3_path.replace(f's3://{storage_service.bucket}/', '')
                local_path = f"{temp_dir}/model.joblib"
                storage_service.download_file(model_path, local_path)
                
                pipeline = joblib.load(local_path)
                
                y_pred = pipeline.predict(X)
                y_proba = pipeline.predict_proba(X)
                
                result = {
                    'prediction': int(y_pred[0]),
                    'probability': float(y_proba[0].max()),
                    'probabilities': y_proba[0].tolist(),
                    'timestamp': datetime.utcnow().isoformat()
                }
                
                # Emit via SocketIO
                from app import socketio
                socketio.emit(
                    'realtime_prediction',
                    {
                        'recording_id': recording_id,
                        **result
                    },
                    room=f'recording_{recording_id}'
                )
                
                return {'status': 'success', **result}
                
            finally:
                import shutil
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                    
        except Exception as e:
            logger.error(f"Realtime inference error: {str(e)}")
            return {'status': 'error', 'error': str(e)}


# Import os at module level
import os
