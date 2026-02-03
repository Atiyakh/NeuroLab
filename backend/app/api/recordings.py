"""
Recordings API - Recording management and processing
"""
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime

from ..models import db, Recording, ProcessingJob, Session
from ..services.storage import storage_service

recordings_bp = Blueprint('recordings', __name__)


@recordings_bp.route('/recordings', methods=['GET'])
@jwt_required(optional=True)
def list_recordings():
    status = request.args.get('status')
    session_id = request.args.get('session_id')
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)
    
    query = Recording.query
    
    if status:
        query = query.filter_by(status=status)
    if session_id:
        query = query.filter_by(session_id=session_id)
    
    total = query.count()
    recordings = query.order_by(Recording.created_at.desc()).offset(offset).limit(limit).all()
    
    return jsonify({
        'recordings': [r.to_dict() for r in recordings],
        'total': total,
        'limit': limit,
        'offset': offset
    }), 200


@recordings_bp.route('/recordings/<recording_id>', methods=['GET'])
@jwt_required(optional=True)
def get_recording(recording_id):
    recording = Recording.query.get_or_404(recording_id)
    
    # Get associated processing jobs
    jobs = recording.processing_jobs.order_by(ProcessingJob.created_at.desc()).all()
    
    result = recording.to_dict()
    result['processing_jobs'] = [j.to_dict() for j in jobs]
    
    # Add presigned URLs for file downloads if available
    if recording.s3_path:
        try:
            result['raw_url'] = storage_service.get_presigned_url(
                recording.s3_path.replace(f's3://{storage_service.bucket}/', ''),
                expires_hours=1
            )
        except Exception:
            result['raw_url'] = None
    
    if recording.processed_path:
        try:
            result['processed_url'] = storage_service.get_presigned_url(
                recording.processed_path.replace(f's3://{storage_service.bucket}/', ''),
                expires_hours=1
            )
        except Exception:
            result['processed_url'] = None
    
    return jsonify(result), 200


@recordings_bp.route('/recordings/<recording_id>', methods=['PATCH'])
@jwt_required(optional=True)
def update_recording(recording_id):
    recording = Recording.query.get_or_404(recording_id)
    data = request.get_json()
    
    if 'meta' in data:
        # Merge with existing meta
        recording.meta = {**recording.meta, **data['meta']}
    
    if 'status' in data:
        recording.status = data['status']
    
    db.session.commit()
    return jsonify(recording.to_dict()), 200


@recordings_bp.route('/recordings/<recording_id>', methods=['DELETE'])
@jwt_required(optional=True)
def delete_recording(recording_id):
    """Delete a recording and its associated files."""
    recording = Recording.query.get_or_404(recording_id)
    
    # Delete from S3
    try:
        if recording.s3_path:
            obj_name = recording.s3_path.replace(f's3://{storage_service.bucket}/', '')
            storage_service.delete_file(obj_name)
        
        if recording.processed_path:
            obj_name = recording.processed_path.replace(f's3://{storage_service.bucket}/', '')
            storage_service.delete_file(obj_name)
        
        if recording.features_path:
            obj_name = recording.features_path.replace(f's3://{storage_service.bucket}/', '')
            storage_service.delete_file(obj_name)
    except Exception as e:
        current_app.logger.warning(f"Error deleting S3 files: {e}")
    
    # Delete from database
    db.session.delete(recording)
    db.session.commit()
    
    return jsonify({'message': 'Recording deleted'}), 200


@recordings_bp.route('/recordings/<recording_id>/start_preprocess', methods=['POST'])
@jwt_required(optional=True)
def start_preprocessing(recording_id):
    recording = Recording.query.get_or_404(recording_id)
    
    if recording.status not in ['uploaded', 'failed', 'needs_review']:
        return jsonify({
            'error': f'Cannot start preprocessing for recording with status: {recording.status}'
        }), 400
    
    data = request.get_json() or {}
    params = data.get('params', {})
    
    # Create processing job
    job = ProcessingJob(
        recording_id=recording.id,
        step='preprocessing',
        params=params,
        status='pending'
    )
    db.session.add(job)
    
    # Update recording status
    recording.status = 'processing'
    db.session.commit()
    
    # Enqueue Celery task
    from ..tasks.preprocessing import preprocess_recording
    task = preprocess_recording.delay(str(recording.id), str(job.id))
    
    # update job with Celery task ID
    job.celery_task_id = task.id
    db.session.commit()
    
    return jsonify({
        'job_id': str(job.id),
        'recording_id': recording_id,
        'celery_task_id': task.id,
        'status': 'pending'
    }), 202


@recordings_bp.route('/recordings/<recording_id>/extract_features', methods=['POST'])
@jwt_required(optional=True)
def extract_features(recording_id):
    """
    Start feature extraction job for a processed recording.
    """
    recording = Recording.query.get_or_404(recording_id)
    
    if recording.status != 'processed':
        return jsonify({
            'error': 'Recording must be preprocessed before feature extraction'
        }), 400
    
    data = request.get_json() or {}
    params = data.get('params', {})
    
    # Create processing job
    job = ProcessingJob(
        recording_id=recording.id,
        step='feature_extraction',
        params=params,
        status='pending'
    )
    db.session.add(job)
    db.session.commit()
    
    # Enqueue Celery task
    from ..tasks.features import extract_features_task
    task = extract_features_task.delay(str(recording.id), str(job.id))
    
    job.celery_task_id = task.id
    db.session.commit()
    
    return jsonify({
        'job_id': str(job.id),
        'recording_id': recording_id,
        'celery_task_id': task.id,
        'status': 'pending'
    }), 202


@recordings_bp.route('/recordings/<recording_id>/jobs', methods=['GET'])
@jwt_required(optional=True)
def get_recording_jobs(recording_id):
    """Get all processing jobs for a recording."""
    recording = Recording.query.get_or_404(recording_id)
    jobs = recording.processing_jobs.order_by(ProcessingJob.created_at.desc()).all()
    
    return jsonify({
        'recording_id': recording_id,
        'jobs': [j.to_dict() for j in jobs]
    }), 200


@recordings_bp.route('/jobs/<job_id>', methods=['GET'])
@jwt_required(optional=True)
def get_job(job_id):
    """Get processing job details."""
    job = ProcessingJob.query.get_or_404(job_id)
    return jsonify(job.to_dict()), 200


@recordings_bp.route('/jobs/<job_id>/cancel', methods=['POST'])
@jwt_required(optional=True)
def cancel_job(job_id):
    """Cancel a running job."""
    job = ProcessingJob.query.get_or_404(job_id)
    
    if job.status not in ['pending', 'running']:
        return jsonify({'error': 'Job cannot be cancelled'}), 400
    
    # Revoke Celery task
    if job.celery_task_id:
        from ..extensions import celery_app
        celery_app.control.revoke(job.celery_task_id, terminate=True)
    
    job.status = 'cancelled'
    job.finished_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'message': 'Job cancelled', 'job_id': job_id}), 200


@recordings_bp.route('/recordings/<recording_id>/visualizations', methods=['GET'])
@jwt_required(optional=True)
def get_visualizations(recording_id):
    """Get available visualizations for a recording."""
    recording = Recording.query.get_or_404(recording_id)
    
    # List visualization files in S3
    viz_prefix = f"visualizations/{recording_id}/"
    
    try:
        viz_files = storage_service.list_objects(prefix=viz_prefix)
        
        visualizations = []
        for f in viz_files:
            viz_type = f.split('/')[-1].rsplit('.', 1)[0]
            visualizations.append({
                'type': viz_type,
                'path': f,
                'url': storage_service.get_presigned_url(f, expires_hours=1)
            })
        
        return jsonify({
            'recording_id': recording_id,
            'visualizations': visualizations
        }), 200
        
    except Exception as e:
        return jsonify({
            'recording_id': recording_id,
            'visualizations': [],
            'error': str(e)
        }), 200
