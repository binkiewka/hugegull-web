// HugeGull Web UI JavaScript

class HugeGullUI {
    constructor() {
        this.jobId = null;
        this.ws = null;
        this.jobs = [];
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadRecentJobs();
    }

    bindEvents() {
        // Toggle advanced settings
        document.getElementById('toggleAdvanced').addEventListener('click', () => {
            const settings = document.getElementById('advancedSettings');
            settings.style.display = settings.style.display === 'none' ? 'block' : 'none';
        });

        // Generate button
        document.getElementById('generateBtn').addEventListener('click', () => this.startGeneration());

        // New video button
        document.getElementById('newVideoBtn').addEventListener('click', () => this.reset());

        // Retry button
        document.getElementById('retryBtn').addEventListener('click', () => this.reset());
    }

    getSettings() {
        return {
            duration: parseFloat(document.getElementById('duration').value) || 45,
            fps: parseInt(document.getElementById('fps').value) || 30,
            crf: parseInt(document.getElementById('crf').value) || 28,
            min_clip_duration: parseFloat(document.getElementById('minClip').value) || 3,
            max_clip_duration: parseFloat(document.getElementById('maxClip').value) || 9,
            gpu: document.getElementById('gpu').value || '',
        };
    }

    async startGeneration() {
        const url = document.getElementById('url').value.trim();
        const name = document.getElementById('name').value.trim();

        if (!url) {
            alert('Please enter a video URL');
            return;
        }

        // Show progress section
        this.showSection('progressSection');
        this.updateProgress(10);

        const settings = this.getSettings();

        try {
            const response = await fetch('/api/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url,
                    name: name || undefined,
                    settings
                })
            });

            if (!response.ok) {
                throw new Error('Failed to start generation');
            }

            const data = await response.json();
            this.jobId = data.job_id;
            
            // Connect WebSocket for progress
            this.connectWebSocket(this.jobId);
            
        } catch (err) {
            this.showError(err.message);
        }
    }

    connectWebSocket(jobId) {
        const wsUrl = `ws://${window.location.host}/ws/${jobId}`;
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('WebSocket connected');
        };

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleProgressUpdate(data);
        };

        this.ws.onerror = (err) => {
            console.error('WebSocket error:', err);
        };

        this.ws.onclose = () => {
            console.log('WebSocket closed');
        };
    }

    handleProgressUpdate(data) {
        const logOutput = document.getElementById('logOutput');

        // Add new log messages
        if (data.progress && data.progress.length > 0) {
            data.progress.forEach(msg => {
                const line = document.createElement('div');
                line.className = 'log-line';
                
                if (msg.includes('✅')) {
                    line.classList.add('success');
                } else if (msg.includes('❌') || msg.includes('Error')) {
                    line.classList.add('error');
                }
                
                line.textContent = msg;
                logOutput.appendChild(line);
            });
            
            // Auto-scroll to bottom
            logOutput.scrollTop = logOutput.scrollHeight;
        }

        // Update progress bar based on log messages
        const logText = logOutput.textContent;
        if (logText.includes('Starting:')) {
            this.updateProgress(20);
        }
        if (logText.includes('Clip 1')) {
            this.updateProgress(40);
        }
        if (logText.includes('Clip 2') || logText.includes('Clip 3')) {
            this.updateProgress(60);
        }
        if (logText.includes('Clip 4') || logText.includes('Clip 5')) {
            this.updateProgress(80);
        }

        // Handle completion
        if (data.status === 'completed') {
            this.updateProgress(100);
            setTimeout(() => this.showSuccess(data.output_file), 500);
        }

        // Handle failure
        if (data.status === 'failed') {
            this.showError(data.error || 'Generation failed');
        }
    }

    updateProgress(percent) {
        document.getElementById('progressFill').style.width = percent + '%';
    }

    showSuccess(outputFile) {
        this.showSection('resultSection');
        
        // Set download link
        const downloadBtn = document.getElementById('downloadBtn');
        downloadBtn.href = `/api/download/${this.jobId}`;
        
        // Refresh jobs list
        this.loadRecentJobs();
    }

    showError(message) {
        this.showSection('errorSection');
        document.getElementById('errorMessage').textContent = message;
    }

    showSection(sectionId) {
        // Hide all sections
        ['progressSection', 'resultSection', 'errorSection'].forEach(id => {
            document.getElementById(id).style.display = 'none';
        });
        
        // Show requested section
        if (sectionId) {
            document.getElementById(sectionId).style.display = 'block';
        }
    }

    reset() {
        this.jobId = null;
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        
        // Clear inputs
        document.getElementById('url').value = '';
        document.getElementById('name').value = '';
        document.getElementById('logOutput').innerHTML = '';
        this.updateProgress(0);
        
        // Hide all result sections
        this.showSection(null);
        
        // Show input section
        document.getElementById('generateBtn').disabled = false;
    }

    async loadRecentJobs() {
        try {
            const response = await fetch('/api/status');
            const jobs = await response.json();
            
            const jobsList = document.getElementById('jobsList');
            
            if (Object.keys(jobs).length === 0) {
                jobsList.innerHTML = '<p class="empty">No jobs yet</p>';
                return;
            }
            
            // Sort by creation time (newest first)
            const sortedJobs = Object.values(jobs).sort((a, b) => 
                new Date(b.created_at) - new Date(a.created_at)
            );
            
            jobsList.innerHTML = sortedJobs.slice(0, 10).map(job => {
                const statusClass = job.status;
                const time = new Date(job.created_at).toLocaleString();
                
                let downloadLink = '';
                if (job.status === 'completed' && job.output_file) {
                    downloadLink = `<a href="/api/download/${job.job_id}">Download</a>`;
                }
                
                return `
                    <div class="job-item">
                        <div class="job-info">
                            <div class="job-name">${job.name}</div>
                            <div class="job-meta">${time} • ${job.url.substring(0, 50)}...</div>
                        </div>
                        <span class="job-status ${statusClass}">${job.status}</span>
                        <div class="job-actions">${downloadLink}</div>
                    </div>
                `;
            }).join('');
            
        } catch (err) {
            console.error('Failed to load jobs:', err);
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new HugeGullUI();
});
