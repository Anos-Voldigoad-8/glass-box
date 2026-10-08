// GLASS BOX Dashboard JavaScript
// Real-time agent observability dashboard

class GlassboxDashboard {
    constructor() {
        this.ws = null;
        this.sessions = new Map();
        this.selectedSessionId = null;
        this.traceData = null;
        this.isConnected = false;
        this.replayInterval = null;
        this.isPlaying = false;
        this.currentStep = 0;
        
        this.init();
    }
    
    init() {
        this.setupUI();
        this.connectWebSocket();
        this.startClock();
        this.loadInitialData();
    }
    
    setupUI() {
        // Get DOM elements
        this.connectionStatus = document.getElementById('connection-status');
        this.statusText = document.getElementById('status-text');
        this.sessionsList = document.getElementById('sessions-list');
        this.traceContent = document.getElementById('trace-content');
        this.sessionSearch = document.getElementById('session-search');
        this.statusFilter = document.getElementById('status-filter');
        this.replayBtn = document.getElementById('replay-btn');
        this.diffBtn = document.getElementById('diff-btn');
        this.clearBtn = document.getElementById('clear-btn');
        this.traceRefresh = document.getElementById('trace-refresh');
        this.traceViewMode = document.getElementById('trace-view-mode');
        this.replayControls = document.getElementById('replay-controls');
        this.prevStepBtn = document.getElementById('prev-step');
        this.playPauseBtn = document.getElementById('play-pause');
        this.nextStepBtn = document.getElementById('next-step');
        this.replaySlider = document.getElementById('replay-slider');
        this.replayTime = document.getElementById('replay-time');
        this.diffControls = document.getElementById('diff-controls');
        this.diffSessionSelect = document.getElementById('diff-session-select');
        this.diffCompareBtn = document.getElementById('diff-compare');
        
        // Metrics elements
        this.totalTokensEl = document.getElementById('total-tokens');
        this.totalCostEl = document.getElementById('total-cost');
        this.avgLatencyEl = document.getElementById('avg-latency');
        this.errorCountEl = document.getElementById('error-count');
        this.systemMessageEl = document.getElementById('system-message');
        this.memoryUsageEl = document.getElementById('memory-usage');
        
        // Event listeners
        this.sessionSearch.addEventListener('input', (e) => this.filterSessions(e.target.value));
        this.statusFilter.addEventListener('change', () => this.filterSessions());
        this.replayBtn.addEventListener('click', () => this.toggleReplayMode());
        this.diffBtn.addEventListener('click', () => this.toggleDiffMode());
        this.clearBtn.addEventListener('click', () => this.clearData());
        this.traceRefresh.addEventListener('click', () => this.refreshTrace());
        this.traceViewMode.addEventListener('change', () => this.renderTrace());
        this.prevStepBtn.addEventListener('click', () => this.previousStep());
        this.playPauseBtn.addEventListener('click', () => this.togglePlay());
        this.nextStepBtn.addEventListener('click', () => this.nextStep());
        this.replaySlider.addEventListener('input', (e) => this.seekTo(parseInt(e.target.value)));
        this.diffCompareBtn.addEventListener('click', () => this.compareTraces());
        
        // Set initial state
        this.updateConnectionStatus(false);
        this.showMessage("Disconnected from server");
    }
    
    connectWebSocket() {
        try {
            this.ws = new WebSocket(`ws://${window.location.hostname}:8080/live`);
            
            this.ws.onopen = () => {
                this.isConnected = true;
                this.updateConnectionStatus(true);
                this.showMessage("Connected to server");
            };
            
            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            };
            
            this.ws.onclose = () => {
                this.isConnected = false;
                this.updateConnectionStatus(false);
                this.showMessage("Disconnected from server - reconnecting...");
                // Attempt to reconnect after 3 seconds
                setTimeout(() => this.connectWebSocket(), 3000);
            };
            
            this.ws.onerror = (error) => {
                console.error("WebSocket error:", error);
                this.showMessage("Connection error");
            };
        } catch (error) {
            console.error("Failed to create WebSocket:", error);
            this.showMessage("Failed to connect to server");
        }
    }
    
    updateConnectionStatus(connected) {
        this.isConnected = connected;
        const dot = this.connectionStatus.querySelector('.dot');
        dot.classList.toggle('connected', connected);
        dot.classList.toggle('connected', connected);
        this.statusText.textContent = connected ? 'Connected' : 'Disconnected';
    }
    
    showMessage(message) {
        this.systemMessageEl.textContent = message;
        // Clear message after 5 seconds
        setTimeout(() => {
            if (this.systemMessageEl.textContent === message) {
                this.systemMessageEl.textContent = 'Ready';
            }
        }, 5000);
    }
    
    startClock() {
        setInterval(() => {
            const now = new Date();
            const timeString = now.toLocaleTimeString();
            document.getElementById('clock').textContent = timeString;
        }, 1000);
    }
    
    loadInitialData() {
        // Fetch initial sessions
        fetch('http://localhost:8080/sessions')
            .then(response => response.json())
            .then(data => {
                this.sessions.clear();
                data.forEach(session => {
                    this.sessions.set(session.id, session);
                });
                this.renderSessions();
            })
            .catch(error => {
                console.error("Failed to load initial sessions:", error);
                this.showMessage("Failed to load initial data");
            });
    }
    
    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'trace_update':
                this.handleTraceUpdate(data.payload);
                break;
            case 'session_update':
                this.handleSessionUpdate(data.payload);
                break;
            case 'metrics_update':
                this.updateMetrics(data.payload);
                break;
            default:
                console.log("Unknown message type:", data.type);
        }
    }
    
    handleTraceUpdate(traceData) {
        // Update or add session
        const sessionId = traceData.trace_id || traceData.id;
        if (!this.sessions.has(sessionId)) {
            // Create session object from trace data
            const session = {
                id: sessionId,
                agent_name: traceData.agent_name || 'Unknown',
                status: traceData.status || 'unknown',
                start_time: traceData.start_time || new Date().toISOString(),
                trace: traceData
            };
            this.sessions.set(sessionId, session);
        }
        
        // If this is the selected session, update the trace view
        if (this.selectedSessionId === sessionId) {
            this.traceData = traceData;
            this.renderTrace();
        }
        
        // Update session list
        this.renderSessions();
    }
    
    handleSessionUpdate(sessionData) {
        this.sessions.set(sessionData.id, sessionData);
        this.renderSessions();
        
        // If this is the selected session, update trace if needed
        if (this.selectedSessionId === sessionData.id) {
            // Update session info in UI
            const sessionElement = this.sessionsList.querySelector(`[data-session-id="${sessionData.id}"]`);
            if (sessionElement) {
                // Update UI elements
            }
        }
    }
    
    updateMetrics(metrics) {
        this.totalTokensEl.textContent = this.formatNumber(metrics.total_tokens || 0);
        this.totalCostEl.textContent = `$${(metrics.total_cost || 0).toFixed(2)}`;
        this.avgLatencyEl.textContent = `${Math.round(metrics.avg_latency || 0)}ms`;
        this.errorCountEl.textContent = metrics.error_count || 0;
        
        // Update memory usage (simulated)
        const memoryUsage = Math.random() * 50 + 50; // Random between 50-100 MB
        this.memoryUsageEl.textContent = `${memoryUsage.toFixed(1)} MB`;
    }
    
    renderSessions() {
        // Clear and rebuild sessions list
        this.sessionsList.innerHTML = '';
        
        // Apply filters
        const filteredSessions = Array.from(this.sessions.values())
            .filter(session => {
                // Text search
                if (this.sessionSearch.value.trim() !== '') {
                    const searchTerm = this.sessionSearch.value.toLowerCase();
                    if (!session.agent_name.toLowerCase().includes(searchTerm) && 
                        !session.id.toLowerCase().includes(searchTerm)) {
                        return false;
                    }
                }
                
                // Status filter
                if (this.statusFilter.value !== 'all' && session.status !== this.statusFilter.value) {
                    return false;
                }
                
                return true;
            })
            .sort((a, b) => {
                // Sort by most recent first
                return new Date(b.start_time) - new Date(a.start_time);
            });
        
        // Add session items to list
        filteredSessions.forEach(session => {
            const sessionElement = document.createElement('div');
            sessionElement.className = 'session-item';
            sessionElement.dataset.sessionId = session.id;
            if (session.id === this.selectedSessionId) {
                sessionElement.classList.add('active');
            }
            
            sessionElement.innerHTML = `
                <div class="session-info">
                    <div class="session-name">${session.agent_name}</div>
                    <div class="session-meta">
                        <span class="session-status ${session.status}">${this.capitalizeFirstLetter(session.status)}</span>
                        <span class="session-time">${this.formatTime(new Date(session.start_time))}</span>
                    </div>
                </div>
                <div class="session-id">${session.id.substring(0, 8)}...</div>
            `;
            
            sessionElement.addEventListener('click', () => {
                this.selectSession(session.id);
            });
            
            this.sessionsList.appendChild(sessionElement);
        });
        
        // Update dropdown for diff comparison
        this.updateDiffSessionSelect();
    }
    
    updateDiffSessionSelect() {
        // Clear and repopulate
        this.diffSessionSelect.innerHTML = '<option value="">Select session...</option>';
        
        Array.from(this.sessions.values())
            .filter(session => session.id !== this.selectedSessionId)
            .forEach(session => {
                const option = document.createElement('option');
                option.value = session.id;
                option.textContent = `${session.agent_name} (${session.id.substring(0, 8)}...)`;
                this.diffSessionSelect.appendChild(option);
            });
    }
    
    selectSession(sessionId) {
        this.selectedSessionId = sessionId;
        
        // Update UI
        document.querySelectorAll('.session-item').forEach(item => {
            item.classList.toggle('active', item.dataset.sessionId === sessionId);
        });
        
        // Fetch full trace data
        fetch(`http://localhost:8080/sessions/${sessionId}/trace`)
            .then(response => response.json())
            .then(traceData => {
                this.traceData = traceData;
                this.renderTrace();
                this.updateSessionMetrics(sessionId);
            })
            .catch(error => {
                console.error("Failed to load trace:", error);
                this.showMessage("Failed to load trace data");
                this.traceContent.innerHTML = '<div class="error-state">Failed to load trace data</div>';
            });
    }
    
    updateSessionMetrics(sessionId) {
        // Fetch session-specific metrics
        // For now, we'll use the global metrics which should be sufficient for demo
    }
    
    renderTrace() {
        if (!this.traceData) {
            this.traceContent.innerHTML = '<div class="empty-state">Select a session to view its trace</div class="section-title">Sessions</h3>...</div>';
            return;
        }
        
        const viewMode = this.traceViewMode.value;
        
        switch (viewMode) {
            case 'tree':
                this.renderTraceTree();
                break;
            case 'timeline':
                this.renderTraceTimeline();
                break;
            case 'logs':
                this.renderTraceLogs();
                break;
            default:
                this.renderTraceTree();
        }
    }
    
    renderTraceTree() {
        if (!this.traceData || !this.traceData.spans) {
            this.traceContent.innerHTML = '<div class="error-state">No trace data available</div>';
            return;
        }
        
        // Build tree structure
        const rootSpans = this.traceData.spans.filter(span => !span.parent_id);
        
        if (rootSpans.length === 0) {
            this.traceContent.innerHTML = '<div class="empty-state">No root spans found</div>';
            return;
        }
        
        const treeHTML = rootSpans.map(span => this.renderSpanTree(span, 0)).join('');
        this.traceContent.innerHTML = `<div class="trace-tree">${treeHTML}</div>`;
    }
    
    renderSpanTree(span, depth) {
        const indent = 'px'.repeat(Math.max(0, depth - 1));
        const isLastChild = true; // Simplified - in reality we'd need to check siblings
        
        return `
            <div class="trace-node" style="margin-left: ${depth * 20}px;">
                <div class="trace-node-icon ${this.getSpanTypeClass(span.span_type)}">
                    ${this.getSpanTypeIcon(span.span_type)}
                </div>
                <div class="trace-node-content">
                    <div class="trace-node-header">
                        <span class="trace-node-name">${span.name || 'Unnamed Span'}</span>
                        <span class="trace-node-type ${span.span_type}">${this.formatSpanType(span.span_type)}</span>
                        <span class="trace-node-status ${span.status}">${this.capitalizeFirstLetter(span.status)}</span>
                    </div>
                    <div class="trace-node-meta">
                        ${span.duration_ms !== undefined ? `<span class="trace-node-meta-item"><i>Duration:</i> ${span.duration_ms.toFixed(1)}ms</span>` : ''}
                        ${span.token_usage ? `<span class="trace-node-meta-item"><i>Tokens:</i> ${this.formatNumber(span.token_usage.total_tokens || 0)}</span>` : ''}
                    </div>
                    ${span.metadata && Object.keys(span.metadata).length > 0 ? 
                        `<div class="trace-node-body"><strong>Metadata:</span><br><pre>${JSON.stringify(span.metadata, null, 2)}</pre></div>` : ''}
                </div>
                ${span.children && span.children.length > 0 ? 
                    `<div class="trace-node-children">${span.children.map(child => this.renderSpanTree(child, depth + 1)).join('')}</div>` : ''}
            </div>
        `;
    }
    
    getSpanTypeClass(type) {
        switch (type) {
            case 'llm_call': return 'llm_call';
            case 'tool_call': return 'tool_call';
            case 'reasoning': return 'reasoning';
            case 'error': return 'error';
            default: return '';
        }
    }
    
    getSpanTypeIcon(type) {
        switch (type) {
            case 'llm_call': return '🤖';
            case 'tool_call': return '🔧';
            case 'reasoning': return '💭';
            case 'error': return '❌';
            default: return '▫️';
        }
    }
    
    formatSpanType(type) {
        return type.replace('_', ' ').toUpperCase();
    }
    
    renderTraceTimeline() {
        // Timeline view implementation
        if (!this.traceData || !this.traceData.spans) {
            this.traceContent.innerHTML = '<div class="error-state">No trace data available</div>';
            return;
        }
        
        const sortedSpans = [...this.traceData.spans].sort((a, b) => {
            return new Date(a.start_time) - new Date(b.start_time);
        });
        
        const timelineHTML = sortedSpans.map(span => `
            <div class="timeline-item">
                <div class="timeline-dot" style="background-color: ${this.getSpanTypeColor(span.span_type)};"></div>
                <div class="timeline-content">
                    <div class="timeline-header">
                        <span class="timeline-name">${span.name || 'Unnamed Span'}</span>
                        <span class="timeline-type">${this.formatSpanType(span.span_type)}</span>
                    </div>
                    <div class="timeline-meta">
                        <span>${this.formatTime(new Date(span.start_time))}</span>
                        <span>${span.duration_ms !== undefined ? `(${span.duration_ms.toFixed(1)}ms)` : ''}</span>
                    </div>
                </div>
            </div>
        `).join('');
        
        this.traceContent.innerHTML = `<div class="timeline-container">${timelineHTML}</div>`;
    }
    
    getSpanTypeColor(type) {
        switch (type) {
            case 'llm_call': return 'var(--accent-cyan)';
            case 'tool_call': return 'var(--accent-green)';
            case 'reasoning': return 'var(--accent-yellow)';
            case 'error': return 'var(--accent-red)';
            default: return 'var(--text-muted)';
        }
    }
    
    renderTraceLogs() {
        // Logs view implementation
        if (!this.traceData || !this.traceData.spans) {
            this.traceContent.innerHTML = '<div class="error-state">No trace data available</div>';
            return;
        }
        
        // Collect all logs from spans
        const allLogs = [];
        this.traceData.spans.forEach(span => {
            if (span.logs && Array.isArray(span.logs)) {
                span.logs.forEach(log => {
                    allLogs.push({
                        ...log,
                        span_name: span.name,
                        span_type: span.span_type,
                        timestamp: log.timestamp || new Date().toISOString()
                    });
                });
            }
        });
        
        // Sort by timestamp
        allLogs.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
        
        if (allLogs.length === 0) {
            this.traceContent.innerHTML = '<div class="empty-state">No log entries found</div>';
            return;
        }
        
        const logsHTML = allLogs.map(log => `
            <div class="log-entry">
                <span class="log-time">${this.formatTime(new Date(log.timestamp))}</span>
                <span class="log-level ${log.level.toLowerCase()}">${log.level.toUpperCase()}</span>
                <span class="log-source">[${log.span_name || 'unknown'}]</span>
                <span class="log-message">${log.message}</span>
                ${log.data && Object.keys(log.data).length > 0 ? 
                    `<span class="log-data">${JSON.stringify(log.data)}</span>` : ''}
            </div>
        `).join('');
        
        this.traceContent.innerHTML = `<div class="logs-container">${logsHTML}</div>`;
    }
    
    filterSessions(searchTerm = null) {
        if (searchTerm !== null) {
            this.sessionSearch.value = searchTerm;
        }
        this.renderSessions();
    }
    
    toggleReplayMode() {
        // Implementation for replay mode
        this.showMessage("Replay mode toggled");
    }
    
    toggleDiffMode() {
        // Implementation for diff mode
        this.showMessage("Diff mode toggled");
    }
    
    clearData() {
        if (confirm("Are you sure you want to clear all data?")) {
            // Clear local state
            this.sessions.clear();
            this.selectedSessionId = null;
            this.traceData = null;
            
            // Update UI
            this.sessionsList.innerHTML = '';
            this.traceContent.innerHTML = '<div class="empty-state">Select a session to view its trace</div>';
            this.updateMetrics({
                total_tokens: 0,
                total_cost: 0,
                avg_latency: 0,
                error_count: 0
            });
            
            this.showMessage("All data cleared");
        }
    }
    
    refreshTrace() {
        if (this.selectedSessionId) {
            this.selectSession(this.selectedSessionId);
        } else {
            this.showMessage("Please select a session first");
        }
    }
    
    // Replay controls
    toggleReplayMode() {
        const isVisible = this.replayControls.style.display !== 'none';
        this.replayControls.style.display = isVisible ? 'none' : 'block';
        this.diffControls.style.display = 'none';
        
        if (!isVisible && this.traceData) {
            this.initializeReplay();
        }
    }
    
    toggleDiffMode() {
        const isVisible = this.diffControls.style.display !== 'none';
        this.diffControls.style.display = isVisible ? 'none' : 'block';
        this.replayControls.style.display = 'none';
        
        if (!isVisible) {
            this.updateDiffSessionSelect();
        }
    }
    
    initializeReplay() {
        // Convert trace to steps for replay
        // This is a simplified implementation
        this.replaySteps = this.flattenTraceForReplay(this.traceData);
        this.currentStep = 0;
        this.replaySlider.max = Math.max(0, this.replaySteps.length - 1);
        this.replaySlider.value = 0;
        this.updateReplayDisplay();
    }
    
    flattenTraceForReplay(traceData) {
        // Flatten the trace tree into a linear sequence for replay
        const steps = [];
        
        const traverse = (span) => {
            steps.push({
                type: 'span',
                data: span,
                timestamp: new Date(span.start_time)
            });
            
            if (span.children) {
                span.children.forEach(child => traverse(child));
            }
        };
        
        (traceData.spans || []).forEach(span => {
            if (!span.parent_id) {
                traverse(span);
            }
        });
        
        return steps.sort((a, b) => a.timestamp - b.timestamp);
    }
    
    updateReplayDisplay() {
        if (!this.replaySteps) return;
        
        const step = this.replaySteps[this.currentStep];
        if (step) {
            // Update slider
            this.replaySlider.value = this.currentStep;
            
            // Update time display
            const totalTime = this.replaySteps.length > 0 ? 
                (new Date(this.replaySteps[this.replaySteps.length - 1].timestamp) - 
                 new Date(this.replaySteps[0].timestamp)) / 1000 : 0;
            const currentTime = this.replaySteps.length > 0 ? 
                (new Date(step.timestamp) - new Date(this.replaySteps[0].timestamp)) / 1000 : 0;
            
            this.replayTime.textContent = `${this.formatSeconds(currentTime)} / ${this.formatSeconds(totalTime)}`;
            
            // Highlight the current step in the trace view
            this.highlightReplayStep(step);
        }
    }
    
    highlightReplayStep(step) {
        // Implementation would highlight the corresponding element in the trace view
        // For now, we'll just update a status message
        this.showMessage(`Replaying: ${step.data.name || 'Unknown Step'} (${this.formatSpanType(step.data.span_type)})`);
    }
    
    previousStep() {
        if (this.currentStep > 0) {
            this.currentStep--;
            this.updateReplayDisplay();
        }
    }
    
    nextStep() {
        if (this.replaySteps && this.currentStep < this.replaySteps.length - 1) {
            this.currentStep++;
            this.updateReplayDisplay();
        }
    }
    
    togglePlay() {
        this.isPlaying = !this.isPlaying;
        this.playPauseBtn.textContent = this.isPlaying ? '⏸️ Pause' : '▶️ Play';
        
        if (this.isPlaying) {
            this.startReplay();
        } else {
            this.stopReplay();
        }
    }
    
    startReplay() {
        if (this.replayInterval) return;
        
        this.replayInterval = setInterval(() => {
            if (this.currentStep < (this.replaySteps.length - 1)) {
                this.currentStep++;
                this.updateReplayDisplay();
            } else {
                this.stopReplay();
            }
        }, 1000); // 1 second per step
    }
    
    stopReplay() {
        if (this.replayInterval) {
            clearInterval(this.replayInterval);
            this.replayInterval = null;
        }
        this.isPlaying = false;
        this.playPauseBtn.textContent = '▶️ Play';
    }
    
    seekTo(position) {
        if (this.replaySteps) {
            this.currentStep = Math.min(Math.max(0, position), this.replaySteps.length - 1);
            this.updateReplayDisplay();
        }
    }
    
    // Comparison functionality
    compareTraces() {
        const baseSessionId = this.selectedSessionId;
        const compareSessionId = this.diffSessionSelect.value;
        
        if (!baseSessionId || !compareSessionId) {
            this.showMessage("Please select both sessions to compare");
            return;
        }
        
        // Fetch both traces and compare
        Promise.all([
            fetch(`http://localhost:8080/sessions/${baseSessionId}/trace`).then(r => r.json()),
            fetch(`http://localhost:8080/sessions/${compareSessionId}/trace`).then(r => r.json())
        ])
        .then(([baseTrace, compareTrace]) => {
            this.showComparisonView(baseTrace, compareTrace);
        })
        .catch(error => {
            console.error("Failed to compare traces:", error);
            this.showMessage("Failed to compare traces");
        });
    }
    
    showComparisonView(baseTrace, compareTrace) {
        // Create a side-by-side comparison view
        this.traceContent.innerHTML = `
            <div class="comparison-container">
                <div class="comparison-side">
                    <h3>Base Session</h3>
                    <div class="trace-view" id="base-trace"></div>
                </div>
                <div class="comparison-side">
                    <h3>Comparison Session</h3>
                    <div class="trace-view" id="compare-trace"></div>
                </div>
            </div>
        `;
        
        // Render both traces (simplified - would need actual tree rendering)
        document.getElementById('base-trace').innerHTML = 
            `<pre>${JSON.stringify(baseTrace, null, 2)}</pre>`;
        document.getElementById('compare-trace').innerHTML = 
            `<pre>${JSON.stringify(compareTrace, null, 2)}</pre>`;
    }
    
    // Utility functions
    formatNumber(num) {
        return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    }
    
    formatTime(date) {
        return date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'});
    }
    
    formatSeconds(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    }
    
    capitalizeFirstLetter(string) {
        return string.charAt(0).toUpperCase() + string.slice(1);
    }
}

// Initialize the dashboard when the page loads
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new GlassboxDashboard();
});
