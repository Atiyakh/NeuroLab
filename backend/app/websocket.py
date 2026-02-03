"""
WebSocket handlers for real-time communication
"""
from flask_socketio import join_room, leave_room, emit
from flask_jwt_extended import decode_token


def register_socket_handlers(socketio):
    
    @socketio.on('connect')
    def handle_connect():
        emit('connected', {'status': 'connected'})
    
    @socketio.on('disconnect')
    def handle_disconnect():
        pass # TODO: handle any cleanup
    
    @socketio.on('join_recording')
    def handle_join_recording(data):
        """Join a recording's real-time channel."""
        recording_id = data.get('recording_id')
        if recording_id:
            room = f'recording_{recording_id}'
            join_room(room)
            emit('joined', {'room': room, 'recording_id': recording_id})
    
    @socketio.on('leave_recording')
    def handle_leave_recording(data):
        recording_id = data.get('recording_id')
        if recording_id:
            room = f'recording_{recording_id}'
            leave_room(room)
            emit('left', {'room': room})
    
    @socketio.on('stream_data')
    def handle_stream_data(data):
        """
        Handle incoming streaming EEG data
        data: {  # Example format
            'recording_id': 'uuid',
            'chunk': [[channel_data], ...],
            'sfreq': 250
        }
        """
        from app.tasks.realtime import process_realtime_chunk
        
        recording_id = data.get('recording_id')
        chunk = data.get('chunk')
        sfreq = data.get('sfreq', 250)
        
        if recording_id and chunk:
            # Process asynchronously
            process_realtime_chunk.delay(recording_id, chunk, sfreq)
    
    @socketio.on('request_inference')
    def handle_request_inference(data):
        from app.tasks.realtime import realtime_inference
        
        recording_id = data.get('recording_id')
        model_id = data.get('model_id')
        
        if recording_id and model_id:
            realtime_inference.delay(recording_id, model_id)
    
    @socketio.on('subscribe_job')
    def handle_subscribe_job(data):
        job_id = data.get('job_id')
        if job_id:
            room = f'job_{job_id}'
            join_room(room)
            emit('subscribed', {'room': room, 'job_id': job_id})
    
    @socketio.on('unsubscribe_job')
    def handle_unsubscribe_job(data):
        job_id = data.get('job_id')
        if job_id:
            leave_room(f'job_{job_id}')


def emit_job_progress(job_id: str, progress: float, status: str, log: str = None):
    from app import socketio
    
    socketio.emit(
        'job_progress',
        {
            'job_id': job_id,
            'progress': progress,
            'status': status,
            'log': log
        },
        room=f'job_{job_id}'
    )


def emit_recording_update(recording_id: str, status: str, data: dict = None):
    from app import socketio
    
    socketio.emit(
        'recording_update',
        {
            'recording_id': recording_id,
            'status': status,
            'data': data or {}
        },
        room=f'recording_{recording_id}'
    )
