class MeetingApp {
    constructor() {
        this.isRecording = false;
        this.currentMeetingId = null;
        this.socket = null;
        
        this.initializeElements();
        this.bindEvents();
        this.loadAudioDevices();
        this.initializeWebSocket();
    }
    
    initializeElements() {
        this.meetingNameInput = document.getElementById('meeting-name');
        this.audioDeviceSelect = document.getElementById('audio-device');
        this.promptTypeSelect = document.getElementById('prompt-type');
        this.startBtn = document.getElementById('start-recording');
        this.stopBtn = document.getElementById('stop-recording');
        this.statusDiv = document.getElementById('status');
        this.progressBar = document.getElementById('progress-bar');
        this.progressFill = document.querySelector('.progress-fill');
        this.transcriptionDisplay = document.getElementById('transcription-display');
        this.clearBtn = document.getElementById('clear-transcription');
        this.copyBtn = document.getElementById('copy-transcription');
    }
    
    bindEvents() {
        this.startBtn.addEventListener('click', () => this.startRecording());
        this.stopBtn.addEventListener('click', () => this.stopRecording());
        this.clearBtn.addEventListener('click', () => this.clearTranscription());
        this.copyBtn.addEventListener('click', () => this.copyTranscription());
        
        this.meetingNameInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !this.isRecording) {
                this.startRecording();
            }
        });
    }
    
    initializeWebSocket() {
        this.socket = io();
        
        this.socket.on('meeting_status', (data) => {
            this.handleWebSocketMessage(data);
        });
        
        this.socket.on('connect', () => {
            console.log('Connected to server');
        });
        
        this.socket.on('disconnect', () => {
            console.log('Disconnected from server');
        });
    }
    
    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'status':
                this.updateStatus(data.status, data.message);
                break;
            case 'progress':
                this.updateProgress(data.progress);
                break;
            case 'transcription':
                this.appendTranscription(data.text);
                break;
            case 'recording_complete':
                this.handleRecordingComplete(data);
                break;
        }
    }
    
    async loadAudioDevices() {
        try {
            const response = await fetch('/api/audio_devices');
            const devices = await response.json();
            
            // Clear existing options
            this.audioDeviceSelect.innerHTML = '';
            
            // Add device options
            devices.forEach(device => {
                const option = document.createElement('option');
                option.value = device.id;
                option.textContent = device.name;
                this.audioDeviceSelect.appendChild(option);
            });
            
        } catch (error) {
            console.error('Error loading audio devices:', error);
            this.audioDeviceSelect.innerHTML = '<option value="-1">Default Device</option>';
        }
    }

    async startRecording() {
        const meetingName = this.meetingNameInput.value.trim();
        const audioDeviceId = parseInt(this.audioDeviceSelect.value);
        const promptType = this.promptTypeSelect.value;
        
        if (!meetingName) {
            alert('Please enter a meeting name');
            this.meetingNameInput.focus();
            return;
        }
        
        try {
            const response = await fetch('/api/start_recording', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    meeting_name: meetingName,
                    audio_device_id: audioDeviceId,
                    prompt_type: promptType
                })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.isRecording = true;
                this.currentMeetingId = data.meeting_id;
                this.updateUI();
                this.updateStatus('recording', 'Recording in progress...');
                this.clearTranscription();
                this.transcriptionDisplay.classList.add('recording');
            } else {
                alert('Error starting recording: ' + data.error);
            }
        } catch (error) {
            console.error('Error starting recording:', error);
            alert('Failed to start recording');
        }
    }
    
    async stopRecording() {
        if (!this.currentMeetingId) return;
        
        try {
            const response = await fetch('/api/stop_recording', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ meeting_id: this.currentMeetingId })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.updateStatus('processing', 'Processing recording...');
            } else {
                alert('Error stopping recording: ' + data.error);
            }
        } catch (error) {
            console.error('Error stopping recording:', error);
            alert('Failed to stop recording');
        }
    }
    
    handleRecordingComplete(data) {
        this.isRecording = false;
        this.currentMeetingId = null;
        this.updateUI();
        this.updateStatus('complete', 'Recording complete and summarized!');
        this.hideProgress();
        this.transcriptionDisplay.classList.remove('recording');
        
        setTimeout(() => {
            this.updateStatus('idle', 'Ready to record');
            this.meetingNameInput.value = '';
        }, 3000);
    }
    
    updateUI() {
        this.startBtn.disabled = this.isRecording;
        this.stopBtn.disabled = !this.isRecording;
        this.meetingNameInput.disabled = this.isRecording;
        this.audioDeviceSelect.disabled = this.isRecording;
        this.promptTypeSelect.disabled = this.isRecording;
        this.clearBtn.disabled = this.isRecording;
        this.copyBtn.disabled = this.isRecording || !this.hasTranscription();
    }
    
    hasTranscription() {
        const placeholder = this.transcriptionDisplay.querySelector('.placeholder-text');
        return !placeholder && this.transcriptionDisplay.textContent.trim().length > 0;
    }
    
    appendTranscription(text) {
        // Remove placeholder if it exists
        const placeholder = this.transcriptionDisplay.querySelector('.placeholder-text');
        if (placeholder) {
            placeholder.remove();
        }
        
        // Create or get transcription text element
        let transcriptElement = this.transcriptionDisplay.querySelector('.transcription-text');
        if (!transcriptElement) {
            transcriptElement = document.createElement('div');
            transcriptElement.className = 'transcription-text';
            this.transcriptionDisplay.appendChild(transcriptElement);
        }
        
        // Append new text with highlight
        const newTextSpan = document.createElement('span');
        newTextSpan.textContent = text + ' ';
        newTextSpan.className = 'new-text';
        transcriptElement.appendChild(newTextSpan);
        
        // Remove highlight after animation
        setTimeout(() => {
            newTextSpan.classList.remove('new-text');
        }, 2000);
        
        // Auto-scroll to bottom
        this.transcriptionDisplay.scrollTop = this.transcriptionDisplay.scrollHeight;
        
        // Update UI state
        this.updateUI();
    }
    
    clearTranscription() {
        this.transcriptionDisplay.innerHTML = '<p class="placeholder-text">Transcription will appear here when recording starts...</p>';
        this.updateUI();
    }
    
    copyTranscription() {
        const transcriptElement = this.transcriptionDisplay.querySelector('.transcription-text');
        if (transcriptElement) {
            const text = transcriptElement.textContent;
            navigator.clipboard.writeText(text).then(() => {
                // Brief feedback
                const originalText = this.copyBtn.innerHTML;
                this.copyBtn.innerHTML = '✅ Copied!';
                setTimeout(() => {
                    this.copyBtn.innerHTML = originalText;
                }, 1500);
            }).catch(err => {
                console.error('Failed to copy text:', err);
                alert('Failed to copy text to clipboard');
            });
        }
    }
    
    updateStatus(status, message) {
        this.statusDiv.textContent = message;
        this.statusDiv.className = `status-${status}`;
    }
    
    updateProgress(progress) {
        this.progressBar.classList.remove('hidden');
        this.progressFill.style.width = `${progress}%`;
    }
    
    hideProgress() {
        this.progressBar.classList.add('hidden');
        this.progressFill.style.width = '0%';
    }
    
}

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new MeetingApp();
});