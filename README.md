# Meeting Recorder & Summarizer

A web-based application for recording meetings, transcribing audio, and generating AI-powered summaries.

## Features

- **Web Interface**: Start/stop recordings with a clean, modern interface
- **Real-time Status**: Live updates during recording and processing
- **Audio Transcription**: Uses whisper.cpp for high-quality transcription
- **AI Summarization**: Powered by Perplexity AI for intelligent meeting summaries
- **File Management**: Browse, download, and manage meeting transcripts and summaries
- **Deployment Ready**: Docker support for easy deployment

## Prerequisites

- Python 3.9+
- [whisper.cpp](https://github.com/ggerganov/whisper.cpp) installed and configured
- Perplexity AI API key

## Quick Start

### Development Setup

1. **Clone and setup**:
   ```bash
   cd LocalScribe
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Run the application**:
   ```bash
   python app.py
   ```

4. **Access the web interface**:
   Open http://localhost:5000 in your browser

### Docker Deployment

1. **Build and run with Docker Compose**:
   ```bash
   # Set environment variables
   export WHISPER_CPP_PATH=/path/to/your/whisper.cpp
   export CALLS_OUTPUT_PATH=/path/to/your/calls/directory
   export PERPLEXITY_API_KEY=your-api-key-here
   
   # Start the application
   docker-compose up -d
   ```

2. **For production with nginx**:
   ```bash
   docker-compose --profile production up -d
   ```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key | Auto-generated |
| `FLASK_DEBUG` | Enable debug mode | `False` |
| `PERPLEXITY_API_KEY` | API key for Perplexity AI | Required |
| `WHISPER_CPP_PATH` | Path to whisper.cpp installation | `~/Documents/Work/whisper.cpp` |
| `CALLS_OUTPUT_PATH` | Directory for storing recordings | `~/Documents/Work/calls` |
| `WHISPER_THREADS` | Number of threads for transcription | `8` |

### Required External Dependencies

1. **whisper.cpp**: 
   - Install from https://github.com/ggerganov/whisper.cpp
   - Download required models (e.g., `ggml-small.en-tdrz.bin`)
   - Update `WHISPER_CPP_PATH` in configuration

2. **Perplexity AI API Key**:
   - Sign up at https://perplexity.ai
   - Get API key from dashboard
   - Set `PERPLEXITY_API_KEY` environment variable

## API Endpoints

- `GET /` - Web interface
- `POST /api/start_recording` - Start new recording
- `POST /api/stop_recording` - Stop active recording
- `GET /api/meeting_status/<meeting_id>` - Get meeting status
- `GET /api/files` - List all meeting files
- `GET /api/download?file=<path>` - Download meeting file

## WebSocket Events

- `meeting_status` - Real-time status updates
- `recording_complete` - Recording finished notification
- `files_updated` - File list changed

## File Structure

```
LocalScribe/
├── app.py                 # Main Flask application
├── config.py              # Configuration management
├── meeting_service.py     # Core meeting recording logic
├── requirements.txt       # Python dependencies
├── Dockerfile            # Container configuration
├── docker-compose.yml    # Multi-container setup
├── .env.example          # Environment template
├── templates/
│   └── index.html        # Web interface
├── static/
│   ├── css/style.css     # Styling
│   └── js/app.js         # Frontend logic
└── calls/                # Generated meeting files
```

## Security Features

- Filename sanitization to prevent directory traversal
- Path validation for file downloads
- Environment-based configuration management
- CORS protection for WebSocket connections

## Troubleshooting

### Common Issues

1. **whisper.cpp not found**:
   - Verify `WHISPER_CPP_PATH` points to correct installation
   - Ensure `stream` executable exists and is executable

2. **Model not found**:
   - Download required model to `whisper.cpp/models/`
   - Verify model filename matches configuration

3. **Permission errors**:
   - Ensure write permissions for `CALLS_OUTPUT_PATH`
   - Check whisper.cpp executable permissions

4. **API key issues**:
   - Verify Perplexity AI API key is valid
   - Check API quota and billing status

### Logs

- Application logs: Check console output or Docker logs
- Meeting processing: Errors logged to stderr during recording
- WebSocket events: Monitor browser developer tools

## Development

### Adding Features

1. **Backend**: Modify `meeting_service.py` for core logic
2. **API**: Add endpoints in `app.py`
3. **Frontend**: Update `templates/index.html` and `static/js/app.js`
4. **Configuration**: Add options to `config.py`

### Testing

```bash
# Run development server
python app.py

# Test API endpoints
curl -X POST http://localhost:5000/api/start_recording \
  -H "Content-Type: application/json" \
  -d '{"meeting_name": "Test Meeting"}'
```

## License

This project is part of a meeting transcription system. Please ensure compliance with audio recording laws and privacy regulations in your jurisdiction.