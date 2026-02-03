"""
Feature extraction Celery task
"""
import os
import json
import tempfile
from datetime import datetime
from celery import shared_task
from celery.utils.log import get_task_logger

import pandas as pd
import mne

logger = get_task_logger(__name__)


@shared_task(bind=True, name='app.tasks.features.extract_features_task')
def extract_features_task(self, recording_id: str, job_id: str):
    from flask import current_app
    from app import create_app
    from app.models import db, Recording, ProcessingJob
    from app.services.storage import storage_service
    from app.processing.features import FeatureExtractor
    
    app = create_app()
    
    with app.app_context():
        recording = Recording.query.get(recording_id)
        job = ProcessingJob.query.get(job_id)
        
        if not recording or not job:
            return {'status': 'failed', 'error': 'Recording or job not found'}
        
        job.status = 'running'
        job.started_at = datetime.utcnow()
        job.log = "Starting feature extraction...\n"
        db.session.commit()
        
        temp_dir = tempfile.mkdtemp(prefix='neurolab_features_')
        
        try:
            config = current_app.config.get('PROCESSING_CONFIG', {}).get('features', {})
            
            # Download processed file
            job.log += "Downloading processed file...\n"
            job.progress = 0.2
            db.session.commit()
            
            processed_path = recording.processed_path.replace(f's3://{storage_service.bucket}/', '')
            local_path = os.path.join(temp_dir, 'cleaned_raw.fif')
            storage_service.download_file(processed_path, local_path)
            
            # Load raw
            job.log += "Loading cleaned data...\n"
            job.progress = 0.3
            db.session.commit()
            
            raw = mne.io.read_raw_fif(local_path, preload=True, verbose=False)
            
            # Extract features
            job.log += "Extracting features...\n"
            job.progress = 0.5
            db.session.commit()
            
            extractor = FeatureExtractor(config)
            features_df = extractor.extract_all_features(raw)
            
            job.log += f"  Extracted {len(features_df)} feature vectors\n"
            job.log += f"  Features per vector: {len(features_df.columns) - 2}\n"  # -2 for epoch_id, channel
            
            # Also extract channel-averaged features
            averaged_df = extractor.extract_channel_averaged_features(raw)
            
            # Compute connectivity features
            job.log += "Computing connectivity features...\n"
            job.progress = 0.7
            db.session.commit()
            
            connectivity = extractor.compute_connectivity(raw)
            
            # Save features to Parquet
            job.log += "Saving features...\n"
            job.progress = 0.85
            db.session.commit()
            
            features_local = os.path.join(temp_dir, 'features.parquet')
            features_df.to_parquet(features_local, index=False)
            
            averaged_local = os.path.join(temp_dir, 'features_averaged.parquet')
            averaged_df.to_parquet(averaged_local, index=False)
            
            # Upload to S3
            features_s3 = f"features/{recording_id}/features.parquet"
            averaged_s3 = f"features/{recording_id}/features_averaged.parquet"
            
            storage_service.upload_file(features_local, features_s3)
            storage_service.upload_file(averaged_local, averaged_s3)
            
            # Save summary JSON
            summary = {
                'n_epochs': int(features_df['epoch_id'].nunique()),
                'n_channels': int(features_df['channel'].nunique()),
                'n_features': len(features_df.columns) - 2,
                'feature_names': [c for c in features_df.columns if c not in ['epoch_id', 'channel']],
                'connectivity': connectivity,
                'stats': {
                    col: {
                        'mean': float(features_df[col].mean()),
                        'std': float(features_df[col].std()),
                        'min': float(features_df[col].min()),
                        'max': float(features_df[col].max())
                    }
                    for col in features_df.columns if col not in ['epoch_id', 'channel']
                }
            }
            
            summary_local = os.path.join(temp_dir, 'summary.json')
            with open(summary_local, 'w') as f:
                json.dump(summary, f, indent=2)
            
            summary_s3 = f"features/{recording_id}/summary.json"
            storage_service.upload_file(summary_local, summary_s3)
            
            # Update recording
            recording.features_path = f"s3://{storage_service.bucket}/{features_s3}"
            recording.meta['feature_summary'] = {
                'n_epochs': summary['n_epochs'],
                'n_channels': summary['n_channels'],
                'n_features': summary['n_features']
            }
            
            # Complete job
            job.status = 'completed'
            job.progress = 1.0
            job.finished_at = datetime.utcnow()
            job.log += "Feature extraction completed successfully.\n"
            
            db.session.commit()
            
            logger.info(f"Features extracted for recording {recording_id}")
            
            return {
                'status': 'completed',
                'recording_id': recording_id,
                'features_path': recording.features_path,
                'n_epochs': summary['n_epochs'],
                'n_features': summary['n_features']
            }
            
        except Exception as e:
            logger.error(f"Feature extraction failed: {str(e)}")
            
            job.status = 'failed'
            job.error = str(e)
            job.finished_at = datetime.utcnow()
            job.log += f"\nERROR: {str(e)}\n"
            
            db.session.commit()
            
            return {'status': 'failed', 'error': str(e)}
            
        finally:
            import shutil
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
