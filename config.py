import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # Paths configuration
    BASE_DIR = Path(__file__).parent.parent
    VENV_PATH = BASE_DIR / 'venv'
    WHISPER_CPP_PATH = Path(os.environ.get('WHISPER_CPP_PATH', Path.home() / 'Documents' / 'Work' / 'whisper.cpp'))
    CALLS_OUTPUT_PATH = Path(os.environ.get('CALLS_OUTPUT_PATH', Path.home() / 'Documents' / 'Work' / 'calls'))
    
    # Whisper.cpp configuration  
    WHISPER_STREAM_PATH = WHISPER_CPP_PATH / 'stream'
    WHISPER_MODEL_PATH = Path('/Users/ashraf.osman/Documents/Work/whisper.cpp/models/ggml-small.en-tdrz.bin')
    WHISPER_THREADS = int(os.environ.get('WHISPER_THREADS', '8'))
    WHISPER_MODE = os.environ.get('WHISPER_MODE', 'local').lower()
    WHISPER_API_URL = os.environ.get('WHISPER_API_URL', '')
    WHISPER_API_TOKEN = os.environ.get('WHISPER_API_TOKEN', '')
    WHISPER_API_SAMPLE_RATE = int(os.environ.get('WHISPER_API_SAMPLE_RATE', '16000'))
    WHISPER_API_CHUNK_DURATION = int(os.environ.get('WHISPER_API_CHUNK_DURATION', '3'))
    
    # API Keys
    PERPLEXITY_API_KEY = os.environ.get('PERPLEXITY_API_KEY')
    SUMMARY_API_URL = os.environ.get('SUMMARY_API_URL', 'https://api.perplexity.ai/chat/completions')
    SUMMARY_API_MODEL = os.environ.get('SUMMARY_API_MODEL', 'sonar')
    SUMMARY_API_TOKEN = os.environ.get('SUMMARY_API_TOKEN', PERPLEXITY_API_KEY)
    
    # Meeting configuration
    MAX_FILENAME_LENGTH = 100
    ALLOWED_FILENAME_CHARS = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_. '
    
    @classmethod
    def validate_paths(cls):
        """Validate that required paths exist"""
        errors = []
        
        # Check API token for Perplexity default
        if cls.SUMMARY_API_URL.startswith('https://api.perplexity.ai') and not cls.SUMMARY_API_TOKEN:
            errors.append("SUMMARY_API_TOKEN (or PERPLEXITY_API_KEY) is required for Perplexity")

        if cls.WHISPER_MODE == 'api' and not cls.WHISPER_API_URL:
            errors.append("WHISPER_API_URL is required when WHISPER_MODE is 'api'")

        if cls.WHISPER_MODE != 'api':
            if not cls.WHISPER_CPP_PATH.exists():
                errors.append(f"Whisper.cpp path not found: {cls.WHISPER_CPP_PATH}")
            
            if not cls.WHISPER_STREAM_PATH.exists():
                errors.append(f"Whisper stream executable not found: {cls.WHISPER_STREAM_PATH}")
            
            if not cls.WHISPER_MODEL_PATH.exists():
                errors.append(f"Whisper model not found: {cls.WHISPER_MODEL_PATH}")
        
        # Create output directory if it doesn't exist
        cls.CALLS_OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
        
        return errors
    
    @classmethod
    def sanitize_filename(cls, filename):
        """Sanitize filename to prevent directory traversal and invalid characters"""
        # Remove any path separators
        filename = filename.replace('/', '').replace('\\', '')
        
        # Keep only allowed characters
        sanitized = ''.join(c for c in filename if c in cls.ALLOWED_FILENAME_CHARS)
        
        # Limit length
        sanitized = sanitized[:cls.MAX_FILENAME_LENGTH]
        
        # Ensure it's not empty or just dots
        if not sanitized or sanitized.strip('.') == '':
            sanitized = 'meeting'
        
        return sanitized.strip()

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(32).hex()

# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
