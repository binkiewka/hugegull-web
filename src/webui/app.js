// HugeGull Web UI JavaScript - Enhanced

class HugeGullUI {
    constructor() {
        this.jobId = null;
        this.ws = null;
        this.jobs = [];
        this.presets = {
            youtube: {
                duration: 45,
                fps: 30,
                crf: 28,
                minClip: 3,
                maxClip: 9,
                aspectRatio: '16:9',
                outputFormat: 'mp4'
            },
            tiktok: {
                duration: 30,
                fps: 30,
                crf: 26,
                minClip: 2,
                maxClip: 6,
                aspectRatio: '9:16',
                outputFormat: 'mp4'
            },
            instagram: {
                duration: 30,
                fps: 30,
                crf: 26,
                minClip: 2,
                maxClip: 6,
                aspectRatio: '1:1',
                outputFormat: 'mp4'
            },
            twitter: {
                duration: 60,
                fps: 30,
                crf: 28,
                minClip: 3,
                maxClip: 10,
                aspectRatio: '16:9',
                outputFormat: 'mp4'
            }
        };
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
            const isVisible = settings.style.display !== 'none';
            settings.style.display = isVisible ? 'none' : 'block';
        });

        // Preset buttons
        document.querySelectorAll('.preset-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.applyPreset(e.target.dataset.preset));
        });

        // Scene detection toggle affects sort options
        document.getElementById('sceneDetection').addEventListener('change', (e) => {
            const sortBy = document.getElementById('sortBy');
            const sceneScoreOption = sortBy.querySelector('option[value="scene_score"]');
            sceneScoreOption.disabled = !e.target.checked;
            if (!e.target.checked && sortBy.value === 'scene_score') {
                sortBy.value = 'index';
            }
        });

        // Action buttons
        document.getElementById('generateBtn').addEventListener('click', () => this.startGeneration(false));
        document.getElementById('previewBtn').addEventListener('click', () => this.startGeneration(true));
        document.getElementById('closePreviewBtn').addEventListener('click', () => {
            document.getElementById('previewSection').style.display = 'none';
        });
        document.getElementById('newVideoBtn').addEventListener('click', () => this.reset());
        document.getElementById('retryBtn').addEventListener('click', () => this.reset());
        document.getElementById('resumeBtn').addEventListener('click', () => this.resumeJob());

        // Help modal
        document.getElementById('showHelp').addEventListener('click', (e) => {
            e.preventDefault();
            document.getElementById('helpModal').style.display = 'flex';
        });
        document.querySelector('.close-modal').addEventListener('click', () => {
            document.getElementById('helpModal').style.display = 'none';
        });
        document.getElementById('helpModal').addEventListener('click', (e) => {
            if (e.target.id === 'helpModal') {
                document.getElementById('helpModal').style.display = 'none';
            }
        });
    }

    applyPreset(presetName) {
        const preset = this.presets[presetName];
        if (!preset) return;

        // Update button states
        document.querySelectorAll('.preset-btn').forEach(btn => btn.classList.remove('active'));
        document.querySelector(`[data-preset="${presetName}"]`).classList.add('active');

        // Apply settings
        document.getElementById('duration').value = preset.duration;
        document.getElementById('fps').value = preset.fps;
        document.getElementById('crf').value = preset.crf;
        document.getElementById('minClip').value = preset.minClip;
        document.getElementById('maxClip').value = preset.maxClip;
        document.getElementById('aspectRatio').value = preset.aspectRatio;
        document.getElementById('outputFormat').value = preset.outputFormat;
    }

    getSettings() {
        return {
            duration: parseFloat(document.getElementById('duration').value) || 45,
            fps: parseInt(document.getElementById('fps').value) || 30,
            crf: parseInt(document.getElementById('crf').value) || 28,
            min_clip_duration: parseFloat(document.getElementById('minClip').value) || 3,
            max_clip_duration: parseFloat(document.getElementById('maxClip').value) || 9,
            gpu: document.getElementById('gpu').value || '',
            aspect_ratio: document.getElementById('aspectRatio').value || '',
            output_format: document.getElementById('outputFormat').value || 'mp4',
            skip_start: parseFloat(document.getElementById('skipStart').value) || 0,
            skip_end: parseFloat(document.getElementById('skipEnd').value) || 0,
            scene_detection: document.getElementById('sceneDetection').checked,
            sort_by: document.getElementById('sortBy').value || 'index',
            shuffle_clips: document.getElementById('sortBy').value === 'random',
        };
    }

    async startGeneration(isPreview) {
        const url = document.getElementById('url').value.trim();
        const name = document.getElementById('name').value.trim();

        if (!url) {
            alert('Please enter a video URL');
            return;
        }

        const settings = this.getSettings();
        settings.preview = isPreview;
        settings.dry_run = isPreview;

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

            if (isPreview) {
                this.showSection('previewSection');
                this.connectWebSocket(this.jobId, true);
            } else {
                this.showSection('progressSection');
                this.connectWebSocket(this.jobId, false);
            }

        } catch (err) {
            this.showError(err.message);
        }
    }

    connectWebSocket(jobId, isPreview) {
        const wsUrl = `ws://${window.location.host}/ws/${jobId}`;
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('WebSocket connected');
        };

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (isPreview) {
                this.handlePreviewUpdate(data);
            } else {
                this.handleProgressUpdate(data);
            }
        };

        this.ws.onerror = (err) => {
            console.error('WebSocket error:', err);
        };

        this.ws.onclose = () => {
            console.log('WebSocket closed');
        };
    }

    handlePreviewUpdate(data) {
        const clipsList = document.getElementById('clipsList');
        
        if (data.clips && data.clips.length > 0) {
            clipsList.innerHTML = data.clips.map((clip, i) => `
                <div class="clip-item">
                    <span class="clip-number">Clip ${i + 1}</span>
                    <span class="clip-time">${clip.start.toFixed(1)}s - ${(clip.start + clip.duration).toFixed(1)}s</span>
                    ${clip.scene_score ? `<span class="clip-score">Score: ${clip.scene_score.toFixed(2)}</span>` : ''}
                </div>
            `).join('');
        }

        if (data.status === 'completed') {
            // Preview complete
        }

        if (data.status === 'failed') {
            this.showError(data.error || 'Preview failed');
        }
    }

    handleProgressUpdate(data) {
        const logOutput = document.getElementById('logOutput');
        const progressText = document.getElementById('progressText');
        const progressPercent = document.getElementById('progressPercent');

        // Add new log messages
        if (data.progress && data.progress.length > 0) {
            data.progress.forEach(msg => {
                const line = document.createElement('div');
                line.className = 'log-line';
                
                if (msg.includes('✅') || msg.includes('✓')) {
                    line.classList.add('success');
                } else if (msg.includes('❌') || msg.includes('Error')) {
                    line.classList.add('error');
                } else if (msg.includes('Clip') || msg.includes('Starting')) {
                    line.classList.add('info');
                }
                
                line.textContent = msg;
                logOutput.appendChild(line);
            });
            
            logOutput.scrollTop = logOutput.scrollHeight;
        }

        // Update progress stats
        if (data.total_clips && data.completed_clips !== undefined) {
            progressText.textContent = `Clip ${data.completed_clips} of ${data.total_clips}`;
            const percent = Math.round((data.completed_clips / data.total_clips) * 100);
            progressPercent.textContent = `${percent}%`;
            this.updateProgress(percent);
        }

        // Handle completion
        if (data.status === 'completed') {
            this.updateProgress(100);
            setTimeout(() => this.showSuccess(data.output_file), 500);
        }

        // Handle failure
        if (data.status === 'failed') {
            this.showError(data.error || 'Generation failed', data.can_resume);
        }
    }

    updateProgress(percent) {
        document.getElementById('progressFill').style.width = percent + '%';
    }

    showSuccess(outputFile) {
        this.showSection('resultSection');
        const downloadBtn = document.getElementById('downloadBtn');
        downloadBtn.href = `/api/download/${this.jobId}`;
        this.loadRecentJobs();
    }

    showError(message, canResume = false) {
        this.showSection('errorSection');
        document.getElementById('errorMessage').textContent = message;
        document.getElementById('resumeBtn').style.display = canResume ? 'inline-flex' : 'none';
    }

    showSection(sectionId) {
        ['previewSection', 'progressSection', 'resultSection', 'errorSection'].forEach(id => {
            document.getElementById(id).style.display = 'none';
        });
        
        if (sectionId) {
            document.getElementById(sectionId).style.display = 'block';
        }
    }

    resumeJob() {
        // Enable resume in settings and retry
        const settings = this.getSettings();
        settings.resume = true;
        
        // Re-submit with resume flag
        this.startGeneration(false);
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
        document.getElementById('clipsList').innerHTML = '';
        this.updateProgress(0);
        document.getElementById('progressText').textContent = 'Clip 0 of 0';
        document.getElementById('progressPercent').textContent = '0%';
        
        // Reset preset buttons
        document.querySelectorAll('.preset-btn').forEach(btn => btn.classList.remove('active'));
        
        // Hide all result sections
        this.showSection(null);
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
            
            const sortedJobs = Object.values(jobs).sort((a, b) => 
                new Date(b.created_at) - new Date(a.created_at)
            );
            
            jobsList.innerHTML = sortedJobs.slice(0, 10).map(job => {
                const statusClass = job.status;
                const time = new Date(job.created_at).toLocaleString();
                const url = job.url ? (job.url.length > 40 ? job.url.substring(0, 40) + '...' : job.url) : 'Unknown';
                
                let downloadLink = '';
                if (job.status === 'completed' && job.output_file) {
                    downloadLink = `<a href="/api/download/${job.job_id}">Download</a>`;
                }
                
                return `
                    <div class="job-item">
                        <div class="job-info">
                            <div class="job-name">${job.name || 'Unnamed'}</div>
                            <div class="job-meta">${time} • ${url}</div>
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
