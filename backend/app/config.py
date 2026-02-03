"""
NeuroLab Configuration
All application settings with defaults
"""
import os
from datetime import timedelta


class Config:
    """Base configuration with defaults"""
    
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Database - Use SQLite for local development if no DATABASE_URL provided
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'sqlite:///neurolab.db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Redis
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    
    # Celery
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_TIMEZONE = 'UTC'
    CELERY_TASK_TRACK_STARTED = True
    
    # MinIO / S3
    MINIO_ENDPOINT = os.environ.get('MINIO_ENDPOINT', 'localhost:9000')
    MINIO_ACCESS_KEY = os.environ.get('MINIO_ACCESS_KEY', 'minioadmin')
    MINIO_SECRET_KEY = os.environ.get('MINIO_SECRET_KEY', 'minioadmin')
    MINIO_BUCKET = os.environ.get('MINIO_BUCKET', 'neurolab')
    MINIO_SECURE = os.environ.get('MINIO_SECURE', 'False').lower() == 'true'
    
    # JWT
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'jwt-secret-key-change-in-production')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    
    # Processing Parameters (explicit defaults from design doc)
    PROCESSING_CONFIG = {
        'target_sfreq': 250,
        'notch_freqs': [50],  # Change to [60] for US sites
        'bandpass': {
            'low': 1.0,
            'high': 40.0
        },
        'ica': {
            'n_components': 20,
            'method': 'fastica',
            'random_state': 42,
            'eog_corr_threshold': 0.35,
            'ecg_corr_threshold': 0.3
        },
        'artifact': {
            'max_bad_channels_pct': 0.25,
            'flat_threshold': 1e-6,
            'high_variance_zscore': 5,
            'kurtosis_threshold': 10,
            'muscle_rms_threshold': 100e-6  # 100 µV
        },
        'features': {
            'bands': [
                {'name': 'delta', 'low': 1, 'high': 4},
                {'name': 'theta', 'low': 4, 'high': 8},
                {'name': 'alpha', 'low': 8, 'high': 12},
                {'name': 'beta', 'low': 12, 'high': 30},
                {'name': 'gamma', 'low': 30, 'high': 45}
            ],
            'welch_window_sec': 2.0,
            'entropy_m': 2,
            'entropy_r_factor': 0.2
        },
        'training': {
            'cv_folds': 5,
            'test_split': 0.2,
            'baseline_model': 'logistic',
            'rf': {
                'n_estimators': 200,
                'grid': {
                    'n_estimators': [100, 200, 500],
                    'max_depth': [None, 10, 20],
                    'max_features': ['sqrt', 0.2, 0.5]
                }
            },
            'promotion_thresholds': {
                'roc_auc': 0.75,
                'f1': 0.65
            }
        },
        'realtime': {
            'buffer_seconds': 30,
            'hop_seconds': 1.0
        }
    }
    
    # Upload limits
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500 MB max file size

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
    # NOTE: Require all secrets to be set from environment
    @property
    def SECRET_KEY(self):
        key = os.environ.get('SECRET_KEY')
        if not key:
            raise ValueError("SECRET_KEY must be set in production")
        return key


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
