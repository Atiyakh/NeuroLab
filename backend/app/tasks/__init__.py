"""Celery tasks module"""
from .preprocessing import preprocess_recording, preprocess_batch
from .features import extract_features_task
from .training import train_model_task, check_auto_retrain, load_model_and_predict
from .realtime import process_realtime_chunk, realtime_inference

__all__ = [
    'preprocess_recording',
    'preprocess_batch',
    'extract_features_task',
    'train_model_task',
    'check_auto_retrain',
    'load_model_and_predict',
    'process_realtime_chunk',
    'realtime_inference'
]
