# LocalScribe - CLI Meeting Recorder & Summarizer

A command-line application for recording meetings, transcribing audio, and generating AI-powered summaries with an optional web interface for file management.

## Features

- **CLI Recording**: Command-line interface for reliable audio capture including both speakers and microphone
- **Real-time Transcription**: Live transcription display during recording
- **Audio Device Selection**: Interactive device selection for optimal audio capture
- **AI Summarization**: Powered by Perplexity AI for intelligent meeting summaries
- **Web File Manager**: Browse, download, and manage meeting transcripts and summaries
- **Local Setup**: Self-contained whisper.cpp integration for offline transcription

## Prerequisites

- Python 3.9+
- Perplexity AI API key
- Audio input device (microphone or system audio)

## Quick Start

### Installation

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
   # Edit .env with your Perplexity API key
   ```

3. **Setup whisper (automatic)**:
   ```bash
   ./setup_whisper.sh
   ```

### Recording Meetings

1. **Start recording**:
   ```bash
   python record_cli.py --record
   ```

2. **Follow the prompts**:
   - Enter meeting name
   - Select audio device
   - Start speaking!

3. **Stop recording**: Press `Ctrl+C` when done

4. **Quick prompt (mic + template)**:
   ```bash
   python record_cli.py --quick
   ```
   This asks for meeting name (with a default), lets you pick microphone/device and meeting template, then starts recording immediately. It remembers your last-used mic and template.

### Managing Files (Optional)

4. **Start web interface** (for file management):
   ```bash
   python app.py
   ```

5. **Access file manager**:
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

## CLI Commands

### Primary Recording Command
```bash
python record_cli.py --record
```

### Quick Prompt
```bash
python record_cli.py --quick
```
Prompts for mic/device and meeting template with a smart default meeting name.
Remembers the last-used mic and template between runs.

### Additional Utilities
```bash
# Test audio routing and device selection
python test_audio_routing.py

# List available audio devices
python record_cli.py --list-devices

# Test specific audio device
python record_cli.py --test-device <device_id>
```

## Web Interface (File Management)

### API Endpoints
- `GET /` - File management interface with CLI instructions
- `GET /api/files` - List all meeting files
- `GET /api/download?file=<path>` - Download meeting file
- `GET /api/audio_devices` - List available audio devices

## File Structure

```
LocalScribe/
├── record_cli.py          # Main CLI recording application
├── app.py                 # Web file manager (optional)
├── config.py              # Configuration management
├── meeting_service.py     # Core meeting recording logic
├── test_audio_routing.py  # Audio device testing utility
├── setup_whisper.sh       # Whisper.cpp setup script
├── requirements.txt       # Python dependencies
├── .env.example          # Environment template
├── whisper/              # Local whisper.cpp installation
│   ├── stream            # Whisper stream executable
│   └── whisper.cpp/      # Source code (gitignored)
├── calls/                # Generated meeting files
├── templates/
│   └── index.html        # Web file manager interface
└── static/
    ├── css/style.css     # Web styling
    └── js/app.js         # Web frontend logic
```

## Security Features

- Filename sanitization to prevent directory traversal
- Path validation for file downloads
- Environment-based configuration management
- CORS protection for WebSocket connections

## Troubleshooting

### Common Issues

1. **"No such file or directory: stream"**:
   - Run `./setup_whisper.sh` to install whisper.cpp locally
   - Or manually copy from existing whisper.cpp installation

2. **Audio device not working**:
   - Run `python test_audio_routing.py` to test devices
   - Try different audio device IDs
   - Check system audio permissions

3. **Model not found**:
   - Ensure you have `ggml-small.en-tdrz.bin` in `/path/to/whisper.cpp/models/`
   - Update `WHISPER_MODEL_PATH` in config.py if needed

4. **API key issues**:
   - Verify Perplexity AI API key in `.env` file
   - Check API quota and billing status

5. **Permission errors**:
   - Ensure write permissions for `calls/` directory
   - Check whisper executable permissions: `chmod +x whisper/stream`

### Debugging Commands

```bash
# Test audio device selection
python test_audio_routing.py

# List available devices
python record_cli.py --list-devices

# Run with debug output
python record_cli.py --record --verbose
```

## Development

### Adding Features

1. **CLI Interface**: Modify `record_cli.py` for recording features
2. **Core Logic**: Update `meeting_service.py` for transcription/summarization
3. **Web Interface**: Update `app.py` and web templates for file management
4. **Configuration**: Add options to `config.py`

### Testing

```bash
# Test CLI recording
python record_cli.py --record

# Test audio devices
python test_audio_routing.py

# Run web file manager
python app.py
```

## Audio Setup Tips

### For macOS Users

1. **Install BlackHole** for system audio capture:
   - Download from https://github.com/ExistentialAudio/BlackHole
   - Create Multi-Output Device in Audio MIDI Setup
   - Combine Built-in Output + BlackHole

2. **Audio Permissions**:
   - System Preferences → Security & Privacy → Microphone
   - Grant permissions to Terminal/Python

### For System + Microphone Recording

1. Use an aggregate device or multi-input device
2. BlackHole devices appear as "BlackHole (System Audio + Mic - Requires Setup)"
3. Test with `python test_audio_routing.py` first

## License

This project is part of a meeting transcription system. Please ensure compliance with audio recording laws and privacy regulations in your jurisdiction.
