from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
from datetime import datetime

from src.core import Database, AudioProcessor, FileMonitor
from src.utils import ConfigManager, log_info, log_error

# Pydantic models for API
class JobResponse(BaseModel):
    id: int
    filename: str
    status: str
    created_at: str
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    transcript_length: Optional[int] = None
    suggested_filename: Optional[str] = None
    final_filename: Optional[str] = None
    naming_confidence: Optional[float] = None

class StatsResponse(BaseModel):
    total: int
    status_counts: Dict[str, int]
    today: int
    success_rate: float

class HealthResponse(BaseModel):
    healthy: bool
    connections: Dict[str, bool]
    folders: Dict[str, bool]
    stats: StatsResponse

class ProcessFileRequest(BaseModel):
    file_path: str

class SettingsRequest(BaseModel):
    deepgram_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    watch_folder: Optional[str] = None
    processed_folder: Optional[str] = None
    error_folder: Optional[str] = None
    output_folder: Optional[str] = None

def create_app() -> FastAPI:
    """Create and configure the FastAPI application"""
    
    config = ConfigManager()
    app = FastAPI(
        title="Audio Processor",
        description="Intelligent audio transcription and processing system",
        version=config.get('app.version', '1.0.0')
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Initialize components
    db = Database()
    processor: Optional[AudioProcessor] = None
    
    # Global file monitor instance (will be set by main app)
    file_monitor = None

    def get_processor() -> Optional[AudioProcessor]:
        nonlocal processor
        if processor is None:
            try:
                processor = AudioProcessor()
            except Exception as e:
                # Likely missing API keys; keep as None so admin can configure
                log_error(f"Processor init failed (likely missing keys): {e}")
                processor = None
        return processor
    
    @app.get("/", response_class=HTMLResponse)
    async def root():
        """Serve the main dashboard"""
        return """
        <!DOCTYPE html>
        <html lang=\"en\">
        <head>
            <meta charset=\"utf-8\" />
            <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
            <title>Audio Processor</title>
            <link rel="stylesheet" href="https://unpkg.com/@picocss/pico@2/css/pico.min.css" />
            <style>
                /* Lightweight, Pico-friendly pills and badges */
                .brand { display: flex; align-items: center; gap: .5rem; }
                .brand .app-icon {
                    display: inline-grid; place-items: center; width: 28px; height: 28px;
                    border-radius: 8px; background: linear-gradient(135deg,#4c8dff,#7aa8ff); color: #fff;
                }
                .brand small { display: block; margin-top: .125rem; }
                .mini-stats { display: flex; flex-wrap: wrap; gap: .5rem; margin-top: .5rem; align-items: center; }
                .pill { display: inline-flex; align-items: center; gap: .375rem; padding: .25rem .5rem; border-radius: 999px; border: 1px solid #E5E7EB; background: #fff; font-size: .75rem; color: #334155; }
                .dot { width: .5rem; height: .5rem; border-radius: 999px; display: inline-block; background: #94A3B8; }
                .dot-success { background: #22C55E; }
                .dot-danger { background: #EF4444; }
                .badge { display: inline-flex; align-items: center; padding: .15rem .5rem; border-radius: 999px; font-size: .75rem; border: 1px solid #E5E7EB; background: #F8FAFC; color: #334155; }
                .badge-green  { border-color: #BBF7D0; background: #ECFDF5; color: #166534; }
                .badge-amber  { border-color: #FDE68A; background: #FFFBEB; color: #92400E; }
                .badge-rose   { border-color: #FECDD3; background: #FFF1F2; color: #9F1239; }
                .badge-indigo { border-color: #C7D2FE; background: #EEF2FF; color: #3730A3; }
                .toolbar-row { display: flex; align-items: center; gap: 0.75rem; }
                .toolbar-row input, .toolbar-row select, .toolbar-row button { 
                    height: 2.5rem; margin: 0; padding: 0.5rem; box-sizing: border-box; 
                    border: 1px solid #ccc; border-radius: 0.375rem; font-size: 0.875rem;
                }
                .toolbar-row input { flex: 1; }
                .toolbar-row select { width: 140px; flex-shrink: 0; }
                .toolbar-row button { flex-shrink: 0; background: #1d4ed8; color: white; cursor: pointer; }
            </style>
        </head>
        <body>
            <header class="container">
                <nav>
                    <ul>
                        <li>
                            <div class="brand">
                                <span class="app-icon">🎵</span>
                                <div>
                                    <strong>Audio Processor</strong>
                                    <small class="secondary">Real-time transcription & smart naming</small>
                                </div>
                            </div>
                        </li>
                    </ul>
                    <ul></ul>
                </nav>
                <div id="mini-stats" class="mini-stats"></div>
            </header>
            <main class="container">
                <div class="grid gap-5">
                    <div class="bg-white border border-neutral-200 rounded-xl shadow-sm">
                        <div class="px-4 py-4 border-b border-neutral-200">
                            <div class="toolbar-row">
                                <input id="search" placeholder="Search filename..." />
                                <select id="statusFilter">
                                    <option value="">All statuses</option>
                                    <option value="completed">Completed</option>
                                    <option value="processing">Processing</option>
                                    <option value="failed">Failed</option>
                                    <option value="pending">Pending</option>
                                </select>
                                <button id="refreshBtn">Refresh</button>
                            </div>
                        </div>
                        <div class="w-full overflow-auto">
                            <table class="w-full text-sm">
                                <thead class="bg-neutral-50 text-neutral-600 text-xs uppercase">
                                    <tr>
                                        <th class="py-2 px-3 text-left w-20 font-medium">ID</th>
                                        <th class="py-2 px-3 text-left font-medium">Filename</th>
                                        <th class="py-2 px-3 text-left w-36 font-medium">Status</th>
                                        <th class="py-2 px-3 text-left w-56 font-medium">Created</th>
                                        <th class="py-2 px-3 text-left font-medium">Suggested Name</th>
                                        <th class="py-2 px-3 text-left w-28 font-medium">Confidence</th>
                                    </tr>
                                </thead>
                                <tbody id="jobs-tbody" class="divide-y divide-neutral-100">
                                    <tr><td colspan="6" class="text-neutral-500 italic py-5 px-3">Loading...</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                    
                </div>
            </main>
            
            <script>
                function dbg(msg) {
                    try {
                        const el = document.getElementById('debug');
                        if (el) { el.textContent = String(msg); }
                        // eslint-disable-next-line no-console
                        console.log('[UI]', msg);
                    } catch (_) {}
                }
                const state = { jobs: [], stats: null, health: null };
                const tbody = document.getElementById('jobs-tbody');
                const searchEl = document.getElementById('search');
                const filterEl = document.getElementById('statusFilter');
                const miniStatsEl = document.getElementById('mini-stats');
                const refreshBtn = document.getElementById('refreshBtn');
                const statusTabs = document.getElementById('statusTabs');

                if (refreshBtn) refreshBtn.addEventListener('click', () => loadData());
                if (searchEl) searchEl.addEventListener('input', () => renderJobs());
                if (filterEl) filterEl.addEventListener('change', () => loadJobs());
                if (statusTabs) {
                    statusTabs.addEventListener('click', (e) => {
                        const btn = e.target.closest('button[data-status]');
                        if (!btn) return;
                        const val = btn.getAttribute('data-status') || '';
                        if (filterEl) filterEl.value = val;
                        [...statusTabs.querySelectorAll('button')].forEach(b => b.classList.remove('ring-2','ring-sky-300'));
                        btn.classList.add('ring-2','ring-sky-300');
                        loadJobs();
                    });
                }

                async function loadData() {
                    try {
                        dbg('Loading data…');
                        await Promise.all([loadHealth(), loadStats(), loadJobs()]);
                        dbg(`Loaded: jobs=${state.jobs?.length || 0}`);
                    } catch (e) {
                        dbg(`Load error: ${e && e.message ? e.message : e}`);
                    }
                }

                async function loadHealth() {
                    try {
                        const res = await fetch('/api/health');
                        if (!res.ok) throw new Error(`Health ${res.status}`);
                        state.health = await res.json();
                        renderHealth();
                        renderMiniStats();
                    } catch (e) {
                        console.error(e);
                        const hc = document.getElementById('health-content');
                        if (hc) hc.innerHTML = '<div class="muted">Failed to load health.</div>';
                        dbg('Health load failed');
                    }
                }

                async function loadStats() {
                    try {
                        const res = await fetch('/api/stats');
                        if (!res.ok) throw new Error(`Stats ${res.status}`);
                        state.stats = await res.json();
                        renderStats();
                        renderMiniStats();
                    } catch (e) {
                        console.error(e);
                        const sc = document.getElementById('stats-content');
                        if (sc) sc.innerHTML = '<div class="muted">Failed to load statistics.</div>';
                        dbg('Stats load failed');
                    }
                }

                async function loadJobs() {
                    try {
                        const status = filterEl.value ? `&status=${encodeURIComponent(filterEl.value)}` : '';
                        const res = await fetch(`/api/jobs?limit=50${status}`);
                        if (!res.ok) throw new Error(`Jobs ${res.status}`);
                        state.jobs = await res.json();
                        renderJobs();
                        dbg(`Jobs loaded: ${state.jobs && state.jobs.length}`);
                    } catch (e) {
                        console.error(e);
                        tbody.innerHTML = '<tr><td colspan="6" class="muted" style="padding:20px">Failed to load jobs.</td></tr>';
                        dbg('Jobs load failed');
                    }
                }

                function renderMiniStats() {
                    if (!miniStatsEl) return;
                    const parts = [];
                    if (state.health) {
                        const h = state.health;
                        const ok = v => v ? 'dot-success' : 'dot-danger';
                        const pill = (content) => `<span class=\"pill\">${content}</span>`;
                        parts.push(pill(`<span class=\"dot ${ok(h.healthy)}\"></span>Overall`));
                        parts.push(pill(`<span class=\"dot ${ok(h.connections.deepgram)}\"></span>Deepgram`));
                        parts.push(pill(`<span class=\"dot ${ok(h.connections.openai)}\"></span>OpenAI`));
                        parts.push(pill(`<span class=\"dot ${ok(h.connections.database)}\"></span>Database`));
                        parts.push(pill(`<span class=\"dot ${ok(h.folders.watch)}\"></span>Watch`));
                        parts.push(pill(`<span class=\"dot ${ok(h.folders.processed)}\"></span>Processed`));
                        parts.push(pill(`<span class=\"dot ${ok(h.folders.error)}\"></span>Error`));
                        parts.push(pill(`<span class=\"dot ${ok(h.folders.output)}\"></span>Output`));
                    }
                    if (state.stats) {
                        const pillPlain = (label, value) => `<span class=\"pill\">${label}: <strong>${value}</strong></span>`;
                        parts.push(pillPlain('Total', state.stats.total));
                        parts.push(pillPlain('Today', state.stats.today));
                        parts.push(pillPlain('Success', `${state.stats.success_rate}%`));
                    }
                    miniStatsEl.innerHTML = parts.join(' ');
                }

                function renderHealth() {
                    const h = state.health; if (!h) return;
                    const ok = v => `<span class=\"dot ${v ? 'dot-success' : 'dot-danger'}\"></span>${v ? 'OK' : 'Issue'}`;
                    const hc = document.getElementById('health-content');
                    if (hc) hc.innerHTML = `
                        <div class=\"kpi\"><div>Overall</div><div class=\"value\">${h.healthy ? 'Healthy' : 'Issues Detected'}</div></div>
                        <div class=\"kpi\"><div>Deepgram</div><div>${ok(h.connections.deepgram)}</div></div>
                        <div class=\"kpi\"><div>OpenAI</div><div>${ok(h.connections.openai)}</div></div>
                        <div class=\"kpi\"><div>Database</div><div>${ok(h.connections.database)}</div></div>
                        <div class=\"kpi\"><div>Watch Folder</div><div>${ok(h.folders.watch)}</div></div>
                        <div class=\"kpi\"><div>Processed Folder</div><div>${ok(h.folders.processed)}</div></div>
                        <div class=\"kpi\"><div>Error Folder</div><div>${ok(h.folders.error)}</div></div>
                        <div class=\"kpi\"><div>Output Folder</div><div>${ok(h.folders.output)}</div></div>
                    `;
                }

                function renderStats() {
                    const s = state.stats; if (!s) return;
                    const sc = document.getElementById('stats-content');
                    if (sc) sc.innerHTML = `
                        <div class=\"kpi\"><div>Total Jobs</div><div class=\"value\">${s.total}</div></div>
                        <div class=\"kpi\"><div>Today's Jobs</div><div class=\"value\">${s.today}</div></div>
                        <div class=\"kpi\"><div>Success Rate</div><div class=\"value\">${s.success_rate}%</div></div>
                        <div class=\"kpi\"><div>Completed</div><div>${s.status_counts.completed || 0}</div></div>
                        <div class=\"kpi\"><div>Processing</div><div>${s.status_counts.processing || 0}</div></div>
                        <div class=\"kpi\"><div>Failed</div><div>${s.status_counts.failed || 0}</div></div>
                        <div class=\"kpi\"><div>Pending</div><div>${s.status_counts.pending || 0}</div></div>
                    `;
                }

                function renderJobs() {
                    const q = (searchEl && searchEl.value) ? searchEl.value.toLowerCase() : '';
                    const rows = state.jobs
                        .filter(j => !q || j.filename.toLowerCase().includes(q))
                        .map(job => {
                            const created = formatDate(job.created_at);
                            const conf = job.naming_confidence ? (job.naming_confidence * 100).toFixed(1) + '%' : '-';
                            return `
                                <tr class=\"hover:bg-neutral-50 dark:hover:bg-neutral-800/60\">
                                    <td>${job.id}</td>
                                    <td class=\"text-neutral-800 dark:text-neutral-100\">${escapeHtml(job.filename)}</td>
                                    <td><span class=\"${statusBadgeClass(job.status)}\">${job.status}</span></td>
                                    <td>${created}</td>
                                    <td class=\"text-neutral-700 dark:text-neutral-300\">${job.suggested_filename ? escapeHtml(job.suggested_filename) : '-'} </td>
                                    <td>${conf}</td>
                                </tr>
                            `;
                        });
                    tbody.innerHTML = rows.length ? rows.join('') : `<tr><td colspan=\"6\" class=\"text-gray-500 italic py-5 px-3\">No jobs found.</td></tr>`;
                }

                function escapeHtml(value) {
                    try {
                        const span = document.createElement('span');
                        span.textContent = value == null ? '' : String(value);
                        return span.innerHTML;
                    } catch (_) {
                        return value == null ? '' : String(value);
                    }
                }

                function formatDate(value) {
                    try {
                        if (!value) return '-';
                        // Normalize "YYYY-MM-DD HH:MM:SS" to ISO for Safari
                        const iso = typeof value === 'string' && value.indexOf(' ') > -1 ? value.replace(' ', 'T') : value;
                        const d = new Date(iso);
                        return isNaN(d.getTime()) ? value : d.toLocaleString();
                    } catch (_) { return value || '-'; }
                }

                if (document.readyState === 'loading') {
                    document.addEventListener('DOMContentLoaded', () => {
                        dbg('DOM ready');
                        loadData();
                        setInterval(loadData, 30000);
                    });
                } else {
                    dbg('DOM already ready');
                    loadData();
                    setInterval(loadData, 30000);
                }
                function statusBadgeClass(s) {
                    const base = 'badge';
                    switch ((s || '').toLowerCase()) {
                        case 'completed':
                            return base + ' badge-green';
                        case 'processing':
                            return base + ' badge-amber';
                        case 'failed':
                            return base + ' badge-rose';
                        case 'pending':
                        default:
                            return base + ' badge-indigo';
                    }
                }
            </script>
        </body>
        </html>
        """

    @app.get("/admin")
    async def admin_page():
        """Serve static admin page"""
        admin_path = os.path.join(os.path.dirname(__file__), 'admin.html')
        if not os.path.exists(admin_path):
            raise HTTPException(status_code=404, detail="Admin page not found")
        return FileResponse(admin_path, media_type='text/html')
    
    @app.get("/api/health", response_model=HealthResponse)
    async def get_health():
        """Get system health status"""
        try:
            # Try full health via processor; fall back if not available
            p = get_processor()
            if p is not None:
                health = p.get_health_status()
                return HealthResponse(**health)
            # Fallback health without processor (e.g., keys missing)
            cfg = ConfigManager()
            folders = {
                'watch': cfg.get("processing.watch_folder"),
                'processed': cfg.get("processing.processed_folder"),
                'error': cfg.get("processing.error_folder"),
                'output': cfg.get("processing.output_folder"),
            }
            folder_status = {}
            for name, path in folders.items():
                try:
                    folder_status[name] = bool(path and os.path.exists(path) and os.access(path, os.W_OK))
                except Exception:
                    folder_status[name] = False
            stats = db.get_job_stats()
            return HealthResponse(
                healthy=False,
                connections={
                    'deepgram': False,
                    'openai': bool(os.getenv('OPENAI_API_KEY')),
                    'database': True,
                },
                folders=folder_status,
                stats=stats,
            )
        except Exception as e:
            log_error(f"Error getting health status: {e}")
            raise HTTPException(status_code=500, detail="Failed to get health status")
    
    @app.get("/api/stats", response_model=StatsResponse)
    async def get_stats():
        """Get processing statistics"""
        try:
            stats = db.get_job_stats()
            return StatsResponse(**stats)
        except Exception as e:
            log_error(f"Error getting stats: {e}")
            raise HTTPException(status_code=500, detail="Failed to get statistics")
    
    @app.get("/api/jobs", response_model=List[JobResponse])
    async def get_jobs(status: Optional[str] = None, limit: int = 50, offset: int = 0):
        """Get jobs with optional filtering"""
        try:
            jobs = db.get_jobs(status=status, limit=limit, offset=offset)
            return [JobResponse(**job) for job in jobs]
        except Exception as e:
            log_error(f"Error getting jobs: {e}")
            raise HTTPException(status_code=500, detail="Failed to get jobs")
    
    @app.get("/api/jobs/{job_id}", response_model=JobResponse)
    async def get_job(job_id: int):
        """Get specific job details"""
        try:
            job = db.get_job(job_id)
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")
            return JobResponse(**job)
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error getting job {job_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to get job")
    
    @app.post("/api/process")
    async def process_file(request: ProcessFileRequest, background_tasks: BackgroundTasks):
        """Manually trigger processing of a specific file"""
        try:
            file_path = request.file_path
            
            if not os.path.exists(file_path):
                raise HTTPException(status_code=404, detail="File not found")
            
            # Process file in background
            p = get_processor()
            if p is None:
                raise HTTPException(status_code=400, detail="Service not configured. Please set API keys on /admin")
            background_tasks.add_task(p.process_file, file_path)
            
            return {"message": "File processing started", "file_path": file_path}
            
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error starting file processing: {e}")
            raise HTTPException(status_code=500, detail="Failed to start processing")
    
    @app.get("/api/monitor/status")
    async def get_monitor_status():
        """Get file monitor status"""
        try:
            # This would need to be set by the main application
            if file_monitor:
                status = file_monitor.get_status()
                return status
            else:
                return {"running": False, "message": "Monitor not initialized"}
        except Exception as e:
            log_error(f"Error getting monitor status: {e}")
            raise HTTPException(status_code=500, detail="Failed to get monitor status")
    
    @app.get("/api/logs")
    async def get_logs(job_id: Optional[int] = None, level: Optional[str] = None, 
                      limit: int = 100, offset: int = 0):
        """Get application logs"""
        try:
            logs = db.get_logs(job_id=job_id, level=level, limit=limit, offset=offset)
            return logs
        except Exception as e:
            log_error(f"Error getting logs: {e}")
            raise HTTPException(status_code=500, detail="Failed to get logs")

    @app.get("/api/settings")
    async def get_settings():
        """Read current settings from environment/config"""
        try:
            cfg = ConfigManager()
            return {
                "deepgram_api_key": bool(os.getenv("DEEPGRAM_API_KEY")),
                "openai_api_key": bool(os.getenv("OPENAI_API_KEY")),
                "watch_folder": os.getenv("WATCH_FOLDER") or cfg.get("processing.watch_folder"),
                "processed_folder": os.getenv("PROCESSED_FOLDER") or cfg.get("processing.processed_folder"),
                "error_folder": os.getenv("ERROR_FOLDER") or cfg.get("processing.error_folder"),
                "output_folder": os.getenv("OUTPUT_FOLDER") or cfg.get("processing.output_folder"),
            }
        except Exception as e:
            log_error(f"Error reading settings: {e}")
            raise HTTPException(status_code=500, detail="Failed to read settings")

    @app.post("/api/settings")
    async def save_settings(req: SettingsRequest):
        """Persist settings into config/.env so app can use them next start"""
        try:
            os.makedirs("config", exist_ok=True)
            path = os.path.join("config", ".env")

            # Load existing lines to preserve unknown keys
            existing: Dict[str, str] = {}
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        for line in f:
                            if not line.strip() or line.strip().startswith("#"):
                                continue
                            if "=" in line:
                                k, v = line.strip().split("=", 1)
                                existing[k] = v
                except Exception:
                    pass

            def q(value: Optional[str]) -> Optional[str]:
                if value is None:
                    return None
                # Quote values to be safe with spaces
                v = value.replace('"', '\\"')
                return f'"{v}"'

            updates = {
                "DEEPGRAM_API_KEY": q(req.deepgram_api_key) if req.deepgram_api_key is not None else existing.get("DEEPGRAM_API_KEY"),
                "OPENAI_API_KEY": q(req.openai_api_key) if req.openai_api_key is not None else existing.get("OPENAI_API_KEY"),
                "WATCH_FOLDER": q(req.watch_folder) if req.watch_folder is not None else existing.get("WATCH_FOLDER"),
                "PROCESSED_FOLDER": q(req.processed_folder) if req.processed_folder is not None else existing.get("PROCESSED_FOLDER"),
                "ERROR_FOLDER": q(req.error_folder) if req.error_folder is not None else existing.get("ERROR_FOLDER"),
                "OUTPUT_FOLDER": q(req.output_folder) if req.output_folder is not None else existing.get("OUTPUT_FOLDER"),
            }

            # Write merged
            with open(path, "w", encoding="utf-8") as f:
                f.write("# Managed by admin UI\n")
                for k, v in updates.items():
                    if v is not None:
                        f.write(f"{k}={v}\n")

            return {"message": "Settings saved. Restart app to apply."}
        except Exception as e:
            log_error(f"Error saving settings: {e}")
            raise HTTPException(status_code=500, detail="Failed to save settings")
    
    return app
