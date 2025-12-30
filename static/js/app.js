// Utility function to copy text to clipboard
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        // Find the button that was clicked and show feedback
        const button = event.target;
        const originalText = button.innerHTML;
        button.innerHTML = '✅';
        setTimeout(() => {
            button.innerHTML = originalText;
        }, 1500);
    }).catch(err => {
        console.error('Failed to copy text:', err);
        alert('Failed to copy to clipboard');
    });
}

class MeetingApp {
    constructor() {
        this.initializeElements();
        this.bindEvents();
        this.initializeSocket();
        this.loadRecordings();
    }
    
    initializeElements() {
        this.recordingsList = document.getElementById('recordings-list');
        this.refreshBtn = document.getElementById('refresh-recordings');
        this.transcriptStream = document.getElementById('transcript-stream');
        this.transcriptPlaceholder = document.getElementById('transcript-placeholder');
        this.statusPill = document.getElementById('status-pill');
        this.autoScrollButton = document.getElementById('auto-scroll');
        this.copyTranscriptButton = document.getElementById('copy-transcript');
        this.meetingName = document.getElementById('meeting-name');
        this.elapsedTime = document.getElementById('elapsed-time');
        this.meetingInput = document.getElementById('meeting-input');
        this.deviceSelect = document.getElementById('device-select');
        this.promptSelect = document.getElementById('prompt-select');
        this.startButton = document.getElementById('start-recording');
        this.stopButton = document.getElementById('stop-recording');
        this.refreshDevicesButton = document.getElementById('refresh-devices');
        this.keypointsTab = document.getElementById('keypoints-tab');
        this.keypointsList = document.getElementById('keypoints-list');
        this.actionsTab = document.getElementById('actions-tab');
        this.actionsList = document.getElementById('actions-list');
        this.settingsPanel = document.getElementById('settings-panel');
        this.openSettingsButton = document.getElementById('open-settings');
        this.closeSettingsButton = document.getElementById('close-settings');
        this.saveSettingsButton = document.getElementById('save-settings');
        this.outputPathInput = document.getElementById('output-path');
        this.summaryTabs = [this.keypointsTab, this.actionsTab].filter(Boolean);
        this.autoScroll = true;
        this.currentMeetingId = null;
        this.timerInterval = null;
        this.startTimestamp = null;
    }
    
    bindEvents() {
        this.refreshBtn?.addEventListener('click', () => this.loadRecordings());
        this.autoScrollButton?.addEventListener('click', () => this.toggleAutoScroll());
        this.copyTranscriptButton?.addEventListener('click', () => this.copyTranscript());
        this.startButton?.addEventListener('click', () => this.startRecording());
        this.stopButton?.addEventListener('click', () => this.stopRecording());
        this.refreshDevicesButton?.addEventListener('click', () => this.loadDevices());
        this.keypointsTab?.addEventListener('click', () => {
            this.setActiveTab('keypoints');
            this.generateKeypoints();
        });
        this.actionsTab?.addEventListener('click', () => {
            this.setActiveTab('actions');
            this.generateActionItems();
        });
        this.openSettingsButton?.addEventListener('click', () => this.openSettings());
        this.closeSettingsButton?.addEventListener('click', () => this.closeSettings());
        this.saveSettingsButton?.addEventListener('click', () => this.saveSettings());
        
        // Auto-refresh recordings every 30 seconds
        setInterval(() => this.loadRecordings(), 30000);
    }

    initializeSocket() {
        if (typeof io === 'undefined') {
            console.warn('Socket.IO not available; live transcript disabled.');
            return;
        }

        this.socket = io();
        this.socket.on('connected', (payload) => {
            console.log(payload.message);
        });
        this.socket.on('meeting_status', (payload) => {
            this.handleMeetingStatus(payload);
        });
    }

    async loadDevices() {
        try {
            const response = await fetch('/api/audio_devices');
            const devices = await response.json();
            this.deviceSelect.innerHTML = '';
            const savedDeviceId = localStorage.getItem('localscribe_device_id');
            devices.forEach((device) => {
                const option = document.createElement('option');
                option.value = device.id;
                option.textContent = device.name;
                this.deviceSelect.appendChild(option);
                if (savedDeviceId !== null && String(device.id) === savedDeviceId) {
                    option.selected = true;
                }
            });
        } catch (error) {
            console.error('Error loading devices:', error);
        }
    }

    async loadPrompts() {
        try {
            const response = await fetch('/api/prompts');
            const prompts = await response.json();
            this.promptSelect.innerHTML = '';
            prompts.forEach((prompt) => {
                const option = document.createElement('option');
                option.value = prompt.id;
                option.textContent = prompt.name;
                this.promptSelect.appendChild(option);
            });
        } catch (error) {
            console.error('Error loading prompts:', error);
        }
    }

    async loadSettings() {
        try {
            const response = await fetch('/api/settings');
            const data = await response.json();
            if (data && data.calls_output_path && this.outputPathInput) {
                this.outputPathInput.value = data.calls_output_path;
            }
        } catch (error) {
            console.error('Error loading settings:', error);
        }
    }

    async saveSettings() {
        if (!this.outputPathInput) {
            return;
        }
        const pathValue = this.outputPathInput.value.trim();
        if (!pathValue) {
            alert('Please enter a folder path.');
            return;
        }

        try {
            const response = await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ calls_output_path: pathValue })
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Failed to save settings');
            }
            this.outputPathInput.value = data.calls_output_path;
            this.closeSettings();
            this.loadRecordings();
        } catch (error) {
            console.error('Error saving settings:', error);
            alert(error.message);
        }
    }

    openSettings() {
        if (this.settingsPanel) {
            this.settingsPanel.classList.remove('hidden');
            this.settingsPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }

    closeSettings() {
        if (this.settingsPanel) {
            this.settingsPanel.classList.add('hidden');
        }
    }

    async startRecording() {
        const meetingName = this.meetingInput.value.trim();
        if (!meetingName) {
            alert('Meeting name is required.');
            return;
        }

        const payload = {
            meeting_name: meetingName,
            audio_device_id: parseInt(this.deviceSelect.value, 10),
            prompt_type: this.promptSelect.value
        };

        localStorage.setItem('localscribe_device_id', this.deviceSelect.value);

        try {
            const response = await fetch('/api/start_recording', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Failed to start recording');
            }

            this.currentMeetingId = data.meeting_id;
            this.startTimestamp = Date.now();
            this.updateElapsedTime();
            this.startTimer();
            this.clearTranscript();
            this.updateStatus('recording', data.message || 'Recording started', this.currentMeetingId, meetingName);
            this.startButton.disabled = true;
            this.stopButton.disabled = false;
        } catch (error) {
            console.error('Error starting recording:', error);
            alert(error.message);
            this.startButton.disabled = false;
        }
    }

    async stopRecording() {
        if (!this.currentMeetingId) {
            return;
        }

        try {
            const response = await fetch('/api/stop_recording', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ meeting_id: this.currentMeetingId })
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Failed to stop recording');
            }
            this.updateStatus('processing', data.message || 'Processing', this.currentMeetingId);
            this.stopButton.disabled = true;
        } catch (error) {
            console.error('Error stopping recording:', error);
            alert(error.message);
        }
    }

    handleMeetingStatus(payload) {
        if (!payload) {
            return;
        }

        if (payload.type === 'transcription') {
            this.appendTranscriptLine(payload.text);
            return;
        }

        if (payload.type === 'status') {
            this.updateStatus(payload.status, payload.message, payload.meeting_id, payload.meeting_name);
        }
    }

    appendTranscriptLine(text) {
        if (!text || !this.transcriptStream) {
            return;
        }

        if (this.transcriptPlaceholder) {
            this.transcriptPlaceholder.remove();
            this.transcriptPlaceholder = null;
        }

        const line = document.createElement('p');
        line.className = 'transcript-line new';
        line.textContent = text.trim();
        this.transcriptStream.appendChild(line);

        setTimeout(() => line.classList.remove('new'), 1200);

        if (this.autoScroll) {
            this.transcriptStream.scrollTop = this.transcriptStream.scrollHeight;
        }
    }

    updateStatus(status, message, meetingId, meetingName) {
        if (!this.statusPill) {
            return;
        }

        const knownStatuses = ['recording', 'processing', 'complete', 'idle', 'error'];
        const nextClass = knownStatuses.includes(status) ? status : 'idle';
        this.statusPill.textContent = message || status || 'Idle';
        this.statusPill.classList.remove('recording', 'processing', 'complete', 'idle', 'error');
        this.statusPill.classList.add(nextClass);

        if (meetingName && this.meetingName) {
            this.meetingName.textContent = meetingName;
        } else if (meetingId && this.meetingName) {
            this.meetingName.textContent = `Meeting ${meetingId}`;
        }

        if (status === 'complete' || status === 'error') {
            this.startButton.disabled = false;
            this.stopButton.disabled = true;
            this.currentMeetingId = null;
            this.stopTimer();
            this.loadRecordings();
        }
    }

    clearTranscript() {
        if (!this.transcriptStream) {
            return;
        }
        this.transcriptStream.innerHTML = '';
        this.transcriptPlaceholder = document.createElement('p');
        this.transcriptPlaceholder.id = 'transcript-placeholder';
        this.transcriptPlaceholder.className = 'transcript-placeholder';
        this.transcriptPlaceholder.textContent = 'Waiting for new audio...';
        this.transcriptStream.appendChild(this.transcriptPlaceholder);
    }

    startTimer() {
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
        }
        this.timerInterval = setInterval(() => this.updateElapsedTime(), 1000);
    }

    stopTimer() {
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
            this.timerInterval = null;
        }
        this.elapsedTime.textContent = '00:00:00';
    }

    updateElapsedTime() {
        if (!this.startTimestamp || !this.elapsedTime) {
            return;
        }
        const elapsed = Math.floor((Date.now() - this.startTimestamp) / 1000);
        const hours = String(Math.floor(elapsed / 3600)).padStart(2, '0');
        const minutes = String(Math.floor((elapsed % 3600) / 60)).padStart(2, '0');
        const seconds = String(elapsed % 60).padStart(2, '0');
        this.elapsedTime.textContent = `${hours}:${minutes}:${seconds}`;
    }

    toggleAutoScroll() {
        this.autoScroll = !this.autoScroll;
        this.autoScrollButton.textContent = `Auto-scroll: ${this.autoScroll ? 'On' : 'Off'}`;
        if (this.autoScroll && this.transcriptStream) {
            this.transcriptStream.scrollTop = this.transcriptStream.scrollHeight;
        }
    }

    copyTranscript() {
        if (!this.transcriptStream) {
            return;
        }
        const lines = Array.from(this.transcriptStream.querySelectorAll('.transcript-line'))
            .map((node) => node.textContent)
            .filter(Boolean)
            .join('\n');
        if (!lines) {
            return;
        }
        navigator.clipboard.writeText(lines).catch((err) => {
            console.error('Failed to copy transcript:', err);
        });
    }

    async generateKeypoints() {
        if (!this.keypointsList) {
            return;
        }

        const transcriptText = Array.from(this.transcriptStream.querySelectorAll('.transcript-line'))
            .map((node) => node.textContent)
            .filter(Boolean)
            .join('\n');

        if (!transcriptText) {
            alert('No transcript available yet.');
            return;
        }

        this.keypointsList.innerHTML = '<li>Generating key points...</li>';

        try {
            const response = await fetch('/api/summary/keypoints', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: transcriptText })
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Failed to generate key points');
            }

            const items = this.parseBulletLines(data.summary);
            this.keypointsList.innerHTML = '';
            items.forEach((item) => {
                const li = document.createElement('li');
                li.textContent = item;
                this.keypointsList.appendChild(li);
            });
        } catch (error) {
            console.error('Error generating key points:', error);
            this.keypointsList.innerHTML = '<li>Failed to generate key points.</li>';
        }
    }

    async generateActionItems() {
        if (!this.actionsList) {
            return;
        }

        const transcriptText = Array.from(this.transcriptStream.querySelectorAll('.transcript-line'))
            .map((node) => node.textContent)
            .filter(Boolean)
            .join('\n');

        if (!transcriptText) {
            alert('No transcript available yet.');
            return;
        }

        this.actionsList.innerHTML = '<li>Generating action items...</li>';

        try {
            const response = await fetch('/api/summary/action-items', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: transcriptText })
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Failed to generate action items');
            }

            const items = this.parseBulletLines(data.summary);
            this.actionsList.innerHTML = '';
            items.forEach((item) => {
                const li = document.createElement('li');
                li.textContent = item;
                this.actionsList.appendChild(li);
            });
        } catch (error) {
            console.error('Error generating action items:', error);
            this.actionsList.innerHTML = '<li>Failed to generate action items.</li>';
        }
    }

    setActiveTab(tabName) {
        this.summaryTabs.forEach((tab) => tab.classList.remove('active'));
        if (tabName === 'actions' && this.actionsTab) {
            this.actionsTab.classList.add('active');
        } else if (this.keypointsTab) {
            this.keypointsTab.classList.add('active');
        }
    }

    parseBulletLines(text) {
        if (!text) {
            return ['No key points generated.'];
        }
        const lines = text
            .split('\n')
            .map((line) => line.replace(/^[-*•]\s*/, '').trim())
            .filter(Boolean);
        return lines.length ? lines : [text.trim()];
    }
    
    async loadRecordings() {
        try {
            const response = await fetch('/api/files');
            const files = await response.json();
            
            this.displayRecordings(files);
            
        } catch (error) {
            console.error('Error loading recordings:', error);
            this.recordingsList.innerHTML = '<p class="error-text">Error loading recordings</p>';
        }
    }
    
    displayRecordings(files) {
        if (!files || files.length === 0) {
            this.recordingsList.innerHTML = '<p class="no-recordings">No recordings found. Use the CLI to create your first recording!</p>';
            return;
        }
        
        let html = '';
        files.forEach((file, index) => {
            html += `
                <div class="recording-item">
                    <div class="recording-header">
                        <h3>${file.name}</h3>
                        <span class="recording-date">${file.date}</span>
                        <span class="recording-size">${file.size}</span>
                    </div>
                    <div class="recording-actions">
                        <a href="/api/download?file=${encodeURIComponent(file.transcript_path)}" 
                           class="btn btn-small" download>
                            📝 Download Transcript
                        </a>
                        ${file.summary_path ? 
                            `<a href="/api/download?file=${encodeURIComponent(file.summary_path)}" 
                                class="btn btn-small" download>
                                📋 Download Summary
                             </a>` : 
                            '<span class="btn btn-small btn-disabled">📋 Summary Processing...</span>'
                        }
                    </div>
                </div>
            `;
        });
        
        this.recordingsList.innerHTML = html;
    }
}

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new MeetingApp();
    window.app.loadDevices();
    window.app.loadPrompts();
    window.app.loadSettings();
});
