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
        this.loadRecordings();
    }
    
    initializeElements() {
        this.recordingsList = document.getElementById('recordings-list');
        this.refreshBtn = document.getElementById('refresh-recordings');
    }
    
    bindEvents() {
        this.refreshBtn.addEventListener('click', () => this.loadRecordings());
        
        // Auto-refresh recordings every 30 seconds
        setInterval(() => this.loadRecordings(), 30000);
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
});