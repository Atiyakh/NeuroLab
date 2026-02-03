"""
Preprocessing Celery tasks
Full MNE-based preprocessing pipeline
"""
import os
import json
import tempfile
from datetime import datetime
from celery import shared_task
from celery.utils.log import get_task_logger

import numpy as np
import mne

logger = get_task_logger(__name__)


@shared_task(bind=True, name='app.tasks.preprocessing.preprocess_recording')
def preprocess_recording(self, recording_id: str, job_id: str):
    """
    Main preprocessing task for a recording.
    
    Implements the full pipeline:
    1. Read + convert
    2. Resample
    3. Notch filter
    4. Bandpass filter
    5. Detect bad channels
    6. ICA artifact removal
    7. Save cleaned data
    8. Generate visualizations
    """
    from flask import current_app
    from app import create_app
    from app.models import db, Recording, ProcessingJob
    from app.services.storage import storage_service
    from app.processing.preprocessing import PreprocessingPipeline
    from app.processing.visualization import generate_preprocessing_plots
    
    app = create_app()
    
    with app.app_context():
        # Get recording and job
        recording = Recording.query.get(recording_id)
        job = ProcessingJob.query.get(job_id)
        
        if not recording or not job:
            logger.error(f"Recording or job not found: {recording_id}, {job_id}")
            return {'status': 'failed', 'error': 'Recording or job not found'}
        
        # Update job status
        job.status = 'running'
        job.started_at = datetime.utcnow()
        job.log = "Starting preprocessing...\n"
        db.session.commit()
        
        temp_dir = tempfile.mkdtemp(prefix='neurolab_')
        
        try:
            # Get config
            config = current_app.config.get('PROCESSING_CONFIG', {})
            
            # Download raw file
            job.log += "Downloading raw file...\n"
            job.progress = 0.1
            db.session.commit()
            
            s3_path = recording.s3_path.replace(f's3://{storage_service.bucket}/', '')
            local_raw_path = os.path.join(temp_dir, os.path.basename(s3_path))
            storage_service.download_file(s3_path, local_raw_path)
            
            # Initialize pipeline
            pipeline = PreprocessingPipeline(config)
            
            # Read raw file
            job.log += "Reading raw file...\n"
            job.progress = 0.2
            db.session.commit()
            
            raw = pipeline.read_raw(local_raw_path)
            
            # Update recording metadata
            recording.sfreq = int(raw.info['sfreq'])
            recording.channels = len(raw.ch_names)
            recording.duration_sec = raw.times[-1]
            recording.meta = {
                **recording.meta,
                'original_sfreq': int(raw.info['sfreq']),
                'original_channels': raw.ch_names
            }
            db.session.commit()
            
            # Resample
            job.log += f"Resampling to {config.get('target_sfreq', 250)} Hz...\n"
            job.progress = 0.3
            db.session.commit()
            
            raw = pipeline.resample(raw)
            
            # Notch filter
            job.log += f"Applying notch filter at {config.get('notch_freqs', [50])} Hz...\n"
            job.progress = 0.4
            db.session.commit()
            
            raw = pipeline.notch_filter(raw)
            
            # Bandpass filter
            bandpass = config.get('bandpass', {'low': 1.0, 'high': 40.0})
            job.log += f"Applying bandpass filter {bandpass['low']}-{bandpass['high']} Hz...\n"
            job.progress = 0.5
            db.session.commit()
            
            raw = pipeline.bandpass_filter(raw)
            
            # Detect bad channels
            job.log += "Detecting bad channels...\n"
            job.progress = 0.6
            db.session.commit()
            
            raw, bad_channels = pipeline.detect_bad_channels(raw)
            job.log += f"  Found {len(bad_channels)} bad channels: {bad_channels}\n"
            
            # Check if too many bad channels
            bad_pct = len(bad_channels) / len(raw.ch_names)
            if bad_pct > config.get('artifact', {}).get('max_bad_channels_pct', 0.25):
                job.log += f"  WARNING: {bad_pct*100:.1f}% channels marked bad, needs manual review\n"
                recording.status = 'needs_review'
                recording.meta['bad_channels'] = bad_channels
                recording.meta['bad_channel_pct'] = bad_pct
                db.session.commit()
            
            # Interpolate bad channels
            if bad_channels:
                job.log += "Interpolating bad channels...\n"
                raw = pipeline.interpolate_bads(raw)
            
            # ICA artifact removal
            job.log += "Running ICA for artifact removal...\n"
            job.progress = 0.7
            db.session.commit()
            
            raw, ica_info = pipeline.run_ica(raw)
            job.log += f"  Removed {len(ica_info.get('excluded_components', []))} ICA components\n"
            recording.meta['ica_info'] = ica_info
            
            # Save cleaned raw
            job.log += "Saving cleaned data...\n"
            job.progress = 0.85
            db.session.commit()
            
            cleaned_filename = f"cleaned_raw.fif"
            cleaned_local_path = os.path.join(temp_dir, cleaned_filename)
            raw.save(cleaned_local_path, overwrite=True)
            
            # Upload to S3
            cleaned_s3_path = f"processed/{recording_id}/{cleaned_filename}"
            storage_service.upload_file(cleaned_local_path, cleaned_s3_path)
            recording.processed_path = f"s3://{storage_service.bucket}/{cleaned_s3_path}"
            
            # Generate visualizations
            job.log += "Generating visualizations...\n"
            job.progress = 0.9
            db.session.commit()
            
            viz_paths = generate_preprocessing_plots(
                raw, 
                recording_id, 
                temp_dir, 
                storage_service,
                ica_info
            )
            recording.meta['visualizations'] = viz_paths
            
            # Update recording status
            recording.status = 'processed' if recording.status != 'needs_review' else 'needs_review'
            recording.sfreq = int(raw.info['sfreq'])
            recording.meta['processing_completed'] = datetime.utcnow().isoformat()
            recording.meta['aligned_channels'] = raw.ch_names
            
            # Complete job
            job.status = 'completed'
            job.progress = 1.0
            job.finished_at = datetime.utcnow()
            job.log += "Preprocessing completed successfully.\n"
            
            db.session.commit()
            
            logger.info(f"Preprocessing completed for recording {recording_id}")
            
            return {
                'status': 'completed',
                'recording_id': recording_id,
                'processed_path': recording.processed_path,
                'bad_channels': bad_channels,
                'ica_components_removed': len(ica_info.get('excluded_components', []))
            }
            
        except Exception as e:
            logger.error(f"Preprocessing failed for {recording_id}: {str(e)}")
            
            job.status = 'failed'
            job.error = str(e)
            job.finished_at = datetime.utcnow()
            job.log += f"\nERROR: {str(e)}\n"
            
            recording.status = 'failed'
            
            db.session.commit()
            
            return {
                'status': 'failed',
                'recording_id': recording_id,
                'error': str(e)
            }
            
        finally:
            # Cleanup temp directory
            import shutil
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)


@shared_task(bind=True, name='app.tasks.preprocessing.preprocess_batch')
def preprocess_batch(self, recording_ids: list):
    """
    Preprocess multiple recordings in batch.
    """
    results = []
    for i, recording_id in enumerate(recording_ids):
        self.update_state(
            state='PROGRESS',
            meta={'current': i, 'total': len(recording_ids)}
        )
        
        # Create job and run preprocessing
        from app import create_app
        from app.models import db, ProcessingJob
        
        app = create_app()
        with app.app_context():
            job = ProcessingJob(
                recording_id=recording_id,
                step='preprocessing',
                status='pending'
            )
            db.session.add(job)
            db.session.commit()
            
            result = preprocess_recording(recording_id, str(job.id))
            results.append(result)
    
    return {
        'completed': len([r for r in results if r['status'] == 'completed']),
        'failed': len([r for r in results if r['status'] == 'failed']),
        'results': results
    }
