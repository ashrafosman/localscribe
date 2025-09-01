from flask import Flask, render_template, request, jsonify, send_file
from flask_socketio import SocketIO, emit
import os
from pathlib import Path
import mimetypes
from config import config, Config
from meeting_service import MeetingService

app = Flask(__name__)
app.config.from_object(config[os.environ.get('FLASK_CONFIG', 'default')])
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize meeting service
meeting_service = MeetingService()

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/api/audio_devices')
def get_audio_devices():
    """Get list of available audio capture devices"""
    try:
        devices = meeting_service.get_audio_devices()
        return jsonify(devices)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/prompts')
def get_prompts():
    """Get list of available summarization prompts"""
    try:
        prompts = meeting_service.get_available_prompts()
        return jsonify(prompts)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/start_recording', methods=['POST'])
def start_recording():
    """Start a new recording"""
    try:
        data = request.get_json()
        meeting_name = data.get('meeting_name', '').strip()
        audio_device_id = data.get('audio_device_id', -1)
        prompt_type = data.get('prompt_type', 'meeting')
        
        if not meeting_name:
            return jsonify({'error': 'Meeting name is required'}), 400
        
        meeting_id = meeting_service.start_recording(meeting_name, audio_device_id, prompt_type)
        
        # Add WebSocket callback for this meeting
        def status_callback(meeting_id, status, message):
            if status == 'transcription':
                # Stream transcription text in real-time
                socketio.emit('meeting_status', {
                    'type': 'transcription',
                    'meeting_id': meeting_id,
                    'text': message
                })
            else:
                # Regular status updates
                socketio.emit('meeting_status', {
                    'type': 'status',
                    'meeting_id': meeting_id,
                    'status': status,
                    'message': message
                })
                
                if status == 'complete':
                    socketio.emit('meeting_status', {
                        'type': 'recording_complete',
                        'meeting_id': meeting_id
                    })
        
        meeting_service.add_status_callback(meeting_id, status_callback)
        
        return jsonify({
            'success': True,
            'meeting_id': meeting_id,
            'message': 'Recording started'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stop_recording', methods=['POST'])
def stop_recording():
    """Stop an active recording"""
    try:
        data = request.get_json()
        meeting_id = data.get('meeting_id')
        
        if not meeting_id:
            return jsonify({'error': 'Meeting ID is required'}), 400
        
        meeting_service.stop_recording(meeting_id)
        
        return jsonify({
            'success': True,
            'message': 'Recording stopped'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/meeting_status/<meeting_id>')
def get_meeting_status(meeting_id):
    """Get meeting status"""
    status = meeting_service.get_meeting_status(meeting_id)
    
    if status is None:
        return jsonify({'error': 'Meeting not found'}), 404
    
    return jsonify({
        'meeting_id': meeting_id,
        'status': status
    })

@app.route('/api/files')
def get_files():
    """Get list of meeting files"""
    try:
        files = meeting_service.get_meeting_files()
        return jsonify(files)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download')
def download_file():
    """Download a meeting file"""
    try:
        file_path = request.args.get('file')
        
        if not file_path:
            return jsonify({'error': 'File path is required'}), 400
        
        # Security: ensure the file is within the calls directory
        requested_path = Path(file_path).resolve()
        calls_path = Config.CALLS_OUTPUT_PATH.resolve()
        
        if not str(requested_path).startswith(str(calls_path)):
            return jsonify({'error': 'Access denied'}), 403
        
        if not requested_path.exists():
            return jsonify({'error': 'File not found'}), 404
        
        # Determine MIME type
        mime_type, _ = mimetypes.guess_type(str(requested_path))
        if mime_type is None:
            mime_type = 'text/plain'
        
        return send_file(
            requested_path,
            mimetype=mime_type,
            as_attachment=True,
            download_name=requested_path.name
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection"""
    print('Client connected')
    emit('connected', {'message': 'Connected to meeting server'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    print('Client disconnected')

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# Cleanup completed meetings periodically
def initialize():
    """Initialize the application"""
    import threading
    import time
    
    def cleanup_worker():
        while True:
            time.sleep(300)  # 5 minutes
            meeting_service.cleanup_completed_meetings()
    
    cleanup_thread = threading.Thread(target=cleanup_worker)
    cleanup_thread.daemon = True
    cleanup_thread.start()

# Initialize on first request
@app.before_request
def before_first_request():
    if not hasattr(app, '_initialized'):
        initialize()
        app._initialized = True

if __name__ == '__main__':
    # Validate configuration on startup
    errors = Config.validate_paths()
    if errors:
        print("Configuration errors:")
        for error in errors:
            print(f"  - {error}")
        print("\nPlease fix these issues before starting the application.")
        exit(1)
    
    print("Starting Meeting Recorder & Summarizer...")
    print(f"Whisper.cpp path: {Config.WHISPER_CPP_PATH}")
    print(f"Output directory: {Config.CALLS_OUTPUT_PATH}")
    
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=app.config['DEBUG'],
        allow_unsafe_werkzeug=True
    )