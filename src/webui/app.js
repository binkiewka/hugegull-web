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
            },
            default: {
                duration: 45,
                fps: 30,
                crf: 28,
                minClip: 3,
                maxClip: 9,
                aspectRatio: '',
                outputFormat: 'mp4'
            }
        };
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadCustomPresets();
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

        // Add URL button
        document.getElementById('addUrlBtn').addEventListener('click', () => this.addUrlInput());

        // Clear URLs button
        document.getElementById('clearUrlsBtn').addEventListener('click', () => this.clearUrls());

        // Action buttons
        document.getElementById('generateBtn').addEventListener('click', () => this.startGeneration());
        document.getElementById('newVideoBtn').addEventListener('click', () => this.reset());
        document.getElementById('retryBtn').addEventListener('click', () => this.reset());
        document.getElementById('resumeBtn').addEventListener('click', () => this.resumeJob());
        document.getElementById('downloadBtn').addEventListener('click', () => {
            document.getElementById('resultSection').style.display = 'none';
        });

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

        // Custom presets logic
        document.getElementById('savePresetBtn').addEventListener('click', () => this.saveCustomPreset());
        document.getElementById('deletePresetBtn').addEventListener('click', () => this.deleteCustomPreset());
        document.getElementById('applyPresetBtn').addEventListener('click', () => {
            const select = document.getElementById('customPresetSelect');
            if (select && select.value) {
                this.applyCustomPreset(select.value);
            }
        });
        document.getElementById('customPresetSelect').addEventListener('change', (e) => {
            const hasValue = (e.target.value !== "");
            document.getElementById('applyPresetBtn').style.display = hasValue ? 'flex' : 'none';
            document.getElementById('deletePresetBtn').style.display = hasValue ? 'flex' : 'none';
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
        
        // Open Advanced Settings
        document.getElementById('advancedSettings').style.display = 'block';
    }

    loadCustomPresets() {
        try {
            const saved = localStorage.getItem('hugegull_custom_presets');
            if (saved) {
                this.customPresets = JSON.parse(saved);
            } else {
                this.customPresets = {};
            }
        } catch (e) {
            this.customPresets = {};
        }
        this.updateCustomPresetDropdown();
    }

    updateCustomPresetDropdown() {
        const select = document.getElementById('customPresetSelect');
        const deleteBtn = document.getElementById('deletePresetBtn');
        
        // Keep the first default option
        const defaultOption = select.options[0];
        select.innerHTML = '';
        select.appendChild(defaultOption);

        const keys = Object.keys(this.customPresets);
        if (keys.length === 0) {
            select.disabled = true;
            deleteBtn.style.display = 'none';
        } else {
            select.disabled = false;
            keys.forEach(name => {
                const opt = document.createElement('option');
                opt.value = name;
                opt.textContent = name;
                select.appendChild(opt);
            });
        }
    }

    saveCustomPreset() {
        const name = prompt("Enter a name for this preset:");
        if (!name || name.trim() === "") return;

        const cleanName = name.trim();
        const settings = this.getSettings();
        
        // Remove settings that shouldn't be saved in generic presets
        delete settings.name;
        delete settings.urls;
        delete settings.resume;

        this.customPresets[cleanName] = settings;
        localStorage.setItem('hugegull_custom_presets', JSON.stringify(this.customPresets));
        
        this.updateCustomPresetDropdown();
        document.getElementById('customPresetSelect').value = cleanName;
        document.getElementById('deletePresetBtn').style.display = 'flex';
        document.getElementById('applyPresetBtn').style.display = 'flex';
    }

    deleteCustomPreset() {
        const select = document.getElementById('customPresetSelect');
        const presetName = select.value;
        
        if (!presetName || presetName === "") return;
        
        if (confirm(`Are you sure you want to delete the preset "${presetName}"?`)) {
            delete this.customPresets[presetName];
            localStorage.setItem('hugegull_custom_presets', JSON.stringify(this.customPresets));
            this.updateCustomPresetDropdown();
            select.value = "";
            document.getElementById('deletePresetBtn').style.display = 'none';
            document.getElementById('applyPresetBtn').style.display = 'none';
        }
    }

    applyCustomPreset(presetName) {
        document.querySelectorAll('.preset-btn').forEach(btn => btn.classList.remove('active'));
        
        if (!presetName || presetName === "") {
            return;
        }

        const preset = this.customPresets[presetName];
        if (!preset) return;

        // Apply settings mapping backend keys to UI inputs
        document.getElementById('duration').value = preset.duration;
        document.getElementById('fps').value = preset.fps;
        document.getElementById('crf').value = preset.crf;
        document.getElementById('minClip').value = preset.min_clip_duration;
        document.getElementById('maxClip').value = preset.max_clip_duration;
        document.getElementById('aspectRatio').value = preset.aspect_ratio || '';
        document.getElementById('outputFormat').value = preset.output_format;
        document.getElementById('gpu').value = preset.gpu || '';
        document.getElementById('skipStart').value = preset.skip_start || 0;
        document.getElementById('skipEnd').value = preset.skip_end || 0;
        
        const sceneToggle = document.getElementById('sceneDetection');
        sceneToggle.checked = preset.scene_detection;
        // Trigger generic change event to update sort dropdown visibility
        sceneToggle.dispatchEvent(new Event('change'));
        
        const sortSelect = document.getElementById('sortBy');
        sortSelect.value = preset.sort_by || 'index';

        document.getElementById('advancedSettings').style.display = 'block';
    }

    addUrlInput() {
        const container = document.getElementById('urlInputs');
        const input = document.createElement('input');
        input.type = 'text';
        input.className = 'url-input';
        input.placeholder = 'https://... or /path/to/video.mp4';
        container.appendChild(input);
        input.focus();
    }

    clearUrls() {
        const container = document.getElementById('urlInputs');
        container.innerHTML = '<input type="text" class="url-input" placeholder="https://youtube.com/watch?v=... or .m3u8 stream or /path/to/video.mp4" />';
    }

    getUrls() {
        const inputs = document.querySelectorAll('.url-input');
        const urls = [];
        inputs.forEach(input => {
            const url = input.value.trim();
            if (url) urls.push(url);
        });
        return urls;
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

    async startGeneration() {
        const urls = this.getUrls();
        const name = document.getElementById('name').value.trim();

        if (urls.length === 0) {
            alert('Please enter at least one video URL');
            return;
        }

        // Disable buttons and show immediate feedback
        const generateBtn = document.getElementById('generateBtn');
        generateBtn.disabled = true;
        generateBtn.innerHTML = '⏳ Starting...';

        const settings = this.getSettings();

        try {
            const response = await fetch('/api/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    urls: urls,  // Send array of URLs
                    name: name || undefined,
                    settings
                })
            });

            if (!response.ok) {
                throw new Error('Failed to start generation');
            }

            const data = await response.json();
            this.jobId = data.job_id;

            // Reset buttons
            generateBtn.disabled = false;
            generateBtn.innerHTML = '🎬 Generate Video';

            this.showSection('progressSection');
            // Show initial loading state
            document.getElementById('progressText').textContent = 'Initializing...';
            document.getElementById('logOutput').innerHTML = '<div class="log-line info">Starting job ' + this.jobId + '...</div>';
            this.connectWebSocket(this.jobId);

        } catch (err) {
            // Re-enable buttons on error
            generateBtn.disabled = false;
            generateBtn.innerHTML = '🎬 Generate Video';
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
        if (data.progress_percent !== undefined && data.progress_percent > 0) {
            // Priority to real-time progress percentages (e.g., during scene scanning)
            const percent = Math.round(data.progress_percent);
            
            // If we're processing clips, also show the clip count text
            if (data.total_clips && data.completed_clips !== undefined && data.total_clips > 0) {
                progressText.textContent = `Clip ${data.completed_clips} of ${data.total_clips}`;
            } else {
                progressText.textContent = `Analyzing & Processing...`;
            }
            
            progressPercent.textContent = `${percent}%`;
            this.updateProgress(percent);
            
        } else if (data.total_clips && data.completed_clips !== undefined && data.total_clips > 0) {
            // Fallback to legacy total_clips ratio
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
        ['progressSection', 'resultSection', 'errorSection'].forEach(id => {
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
        
        // Clear URL inputs
        this.clearUrls();
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
