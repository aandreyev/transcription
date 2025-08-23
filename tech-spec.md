# Technical Specification: Audio Processor Application

## Architecture Overview
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Web UI        │    │   Core Engine    │    │   External APIs │
│   (FastAPI)     │◄──►│   (Python)       │◄──►│   Deepgram      │
│   - Dashboard   │    │   - File Monitor │    │   OpenAI        │
│   - Logs        │    │   - Processor    │    └─────────────────┘
│   - Config      │    │   - Database     │
└─────────────────┘    └──────────────────┘
                                │
                       ┌──────────────────┐
                       │   SQLite DB      │
                       │   - Jobs         │
                       │   - Logs         │
                       │   - Config       │
                       └──────────────────┘
```

## Project Structure
```
audio-processor/
├── config/
│   ├── config.yaml              # Main configuration
│   └── .env                     # API keys & secrets
├── src/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── file_monitor.py      # File watching logic
│   │   ├── processor.py         # Main processing pipeline
│   │   ├── deepgram_client.py   # Deepgram integration
│   │   ├── openai_client.py     # OpenAI integration
│   │   ├── file_namer.py        # Intelligent file naming
│   │   └── database.py          # SQLite operations
│   ├── web/
│   │   ├── __init__.py
│   │   ├── app.py              # FastAPI application
│   │   ├── routes.py           # API endpoints
│   │   └── templates/          # HTML templates
│   │       ├── dashboard.html
│   │       ├── logs.html
│   │       └── config.html
│   └── utils/
│       ├── __init__.py
│       ├── logger.py           # Centralized logging
│       └── config_manager.py   # Configuration handling
├── static/                     # CSS/JS for web UI
├── data/
│   ├── input/                  # Watch folder
│   ├── processed/              # Completed files
│   ├── error/                  # Failed files
│   └── output/                 # Generated summaries
├── logs/                       # Application logs
├── tests/                      # Unit tests
├── requirements.txt
├── main.py                     # Application entry point
└── README.md
```

## Core Components

### 1. Configuration Management (`config/config.yaml`)
```yaml
# Application Settings
app:
  name: "Audio Processor"
  version: "1.0.0"
  debug: false

# File Processing
processing:
  watch_folder: "{{WATCH_FOLDER}}"
  processed_folder: "{{PROCESSED_FOLDER}}"
  error_folder: "{{ERROR_FOLDER}}"
  output_folder: "{{OUTPUT_FOLDER}}"
  file_stability_wait: 10  # seconds
  supported_formats: [".mp3", ".wav", ".m4a", ".mp4", ".mov"]

# External APIs
deepgram:
  model: "nova-2"
  features:
    punctuate: true
    paragraphs: true
    speaker_diarize: true
    smart_format: true
    utt_split: 1.5

openai:
  model: "gpt-4o"
  temperature: 0.7
  max_tokens: 2000

# Web Interface
web:
  host: "127.0.0.1"
  port: 8000
  auto_reload: false

# Logging
logging:
  level: "INFO"
  max_file_size: "10MB"
  backup_count: 5
```

### 2. Environment Variables (`.env`)
```bash
# API Keys
DEEPGRAM_API_KEY=your_deepgram_key_here
OPENAI_API_KEY=your_openai_key_here

# Folder Paths (customize for your system)
WATCH_FOLDER=/Users/yourusername/OneDrive/AudioProcessor/input
PROCESSED_FOLDER=/Users/yourusername/OneDrive/AudioProcessor/processed
ERROR_FOLDER=/Users/yourusername/OneDrive/AudioProcessor/error
OUTPUT_FOLDER=/Users/yourusername/OneDrive/AudioProcessor/output

# Database
DATABASE_URL=sqlite:///data/audio_processor.db
```

### 3. Database Schema (SQLite)
```sql
-- Jobs table
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    status TEXT NOT NULL, -- 'pending', 'processing', 'completed', 'failed'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    transcript_length INTEGER,
    output_file TEXT
);

-- Logs table
CREATE TABLE logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER,
    level TEXT NOT NULL,
    message TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs (id)
);

-- Configuration table
CREATE TABLE config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 4. Web Interface Features

**Dashboard (`/`)**
- Current processing status
- Recent jobs (last 10)
- System health indicators
- Quick stats (processed today, success rate)

**Jobs View (`/jobs`)**
- Paginated list of all jobs
- Filter by status/date
- View individual job details
- Download output files

**Logs View (`/logs`)**
- Real-time log streaming
- Filter by level/job
- Search functionality

**Configuration (`/config`)**
- Edit processing settings
- Test API connections
- Folder path management

### 5. Key Improvements Over Original PRD

**Enhanced Error Handling:**
- Retry logic for API failures (3 attempts with exponential backoff)
- File lock detection before processing
- Graceful handling of corrupted files
- Automatic recovery from network issues

**Centralized Logging:**
- Structured logging with job correlation
- Log rotation to prevent disk space issues
- Different log levels for debugging vs production
- Web-based log viewing

**Progress Tracking:**
- Real-time status updates
- Processing time metrics
- Success/failure rates
- File size and duration tracking

**Simple Monitoring:**
- Health check endpoint (`/health`)
- Basic metrics collection
- Email notifications for failures (optional)

### 6. Processing Pipeline
```
1. File Detection → 2. Validation → 3. Transcription → 4. AI Processing → 5. Output Generation → 6. Cleanup
     ↓                    ↓              ↓               ↓                  ↓                   ↓
   Log Event         Check Format    Deepgram API    OpenAI API        Save Results      Move Files
   Update DB         File Stability   + Retry Logic   + Retry Logic     Update DB         Update Status
```

### 7. Deployment Strategy

**Development:**
- Run with `python main.py`
- Auto-reload enabled
- Debug logging

**Production:**
- Use systemd service (Linux) or launchd (macOS)
- Process monitoring with automatic restart
- Log rotation configured
- Health checks enabled

### 8. Intelligent File Naming System

**Naming Convention Format:**
`YYYYMMDD Meeting with [Participants] re [Topic] - [Duration]min`

**Examples:**
- `20250720 Meeting with John Smith re Shareholder Agreement - 45min`
- `20250721 Call with Legal Team re Contract Review - 23min`
- `20250722 Board Meeting re Q4 Results - 120min`

**Information Sources & Extraction Strategy:**

1. **Date Extraction (Priority Order):**
   - File creation/modification timestamp
   - Date patterns in original filename
   - Recording date from audio metadata
   - Fallback to processing date

2. **Content Analysis via AI:**
   ```yaml
   naming_prompt: |
     Analyze this meeting transcript and extract:
     1. Meeting participants (names mentioned as speakers or attendees)
     2. Main topic/purpose of the meeting
     3. Meeting type (e.g., "Meeting", "Call", "Interview", "Presentation")
     
     Format response as JSON:
     {
       "participants": ["Name1", "Name2"],
       "topic": "Brief topic description",
       "meeting_type": "Meeting/Call/Interview"
     }
     
     Transcript: {transcript}
   ```

3. **Filename Parsing Rules:**
   - Extract existing date patterns (YYYY-MM-DD, DD-MM-YYYY, etc.)
   - Identify common meeting keywords ("meeting", "call", "interview")
   - Parse participant names from filename
   - Extract topic keywords

4. **Metadata Extraction:**
   - Audio duration for filename suffix
   - Recording timestamp from file properties
   - Device/location information if available

**Implementation Components:**

```python
# New module: src/core/file_namer.py
class IntelligentFileNamer:
    def generate_name(self, original_file, transcript, metadata):
        # 1. Extract date from multiple sources
        date = self._extract_date(original_file, metadata)
        
        # 2. Parse existing filename for clues
        filename_info = self._parse_filename(original_file)
        
        # 3. Use AI to extract meeting details
        ai_info = self._extract_meeting_info(transcript)
        
        # 4. Combine information with fallbacks
        return self._build_filename(date, filename_info, ai_info, metadata)
```

**Database Schema Addition:**
```sql
-- Add to jobs table
ALTER TABLE jobs ADD COLUMN original_filename TEXT;
ALTER TABLE jobs ADD COLUMN suggested_filename TEXT;
ALTER TABLE jobs ADD COLUMN final_filename TEXT;
ALTER TABLE jobs ADD COLUMN naming_confidence REAL; -- 0.0 to 1.0
ALTER TABLE jobs ADD COLUMN manual_override BOOLEAN DEFAULT FALSE;
```

**Web Interface Enhancement:**
- **Filename Preview**: Show suggested name before processing completion
- **Manual Override**: Allow users to edit suggested filenames
- **Naming History**: Track naming patterns for learning
- **Confidence Indicators**: Show how confident the system is about extracted information

### 9. AI Prompt Templates
```yaml
prompts:
  summary: |
    Analyze this meeting transcript and provide:
    1. Executive Summary (2-3 sentences)
    2. Key Discussion Points (bullet points)
    3. Action Items (with responsible parties if mentioned)
    4. Decisions Made (explicit decisions only)
    5. Next Steps
    
    Format as markdown with clear sections.
    
    Transcript: {transcript}
    
  action_items: |
    Extract all action items from this transcript.
    Format as: "- [Person]: Task description (Due: date if mentioned)"
    Only include explicit tasks, not general discussion points.
    
    Transcript: {transcript}
    
  naming_extraction: |
    Analyze this meeting transcript and extract key information for file naming.
    
    Extract:
    1. All participant names (people speaking or mentioned as attendees)
    2. Main meeting topic or purpose (be concise, 2-4 words)
    3. Meeting type (Meeting/Call/Interview/Presentation/Discussion)
    
    Rules:
    - For participants: Use full names when available, otherwise first names
    - For topic: Focus on the main subject (e.g., "Budget Review", "Contract Negotiation")
    - Be concise but descriptive
    
    Return as JSON only:
    {
      "participants": ["Name1", "Name2"],
      "topic": "Main Topic",
      "meeting_type": "Meeting"
    }
    
    Transcript: {transcript}
```

## Implementation Priority

### Phase 1: Core Functionality
1. Basic file monitoring
2. Deepgram integration
3. OpenAI processing
4. Simple logging

### Phase 2: Web Interface
1. FastAPI setup
2. Basic dashboard
3. Job status display
4. Configuration management

### Phase 3: Enhancement
1. Advanced error handling
2. Retry logic
3. Performance monitoring
4. Email notifications

## Requirements

### Python Dependencies
```
fastapi>=0.104.0
uvicorn>=0.24.0
watchdog>=3.0.0
deepgram-sdk>=3.0.0
openai>=1.0.0
python-dotenv>=1.0.0
pyyaml>=6.0.0
sqlalchemy>=2.0.0
jinja2>=3.1.0
python-multipart>=0.0.6
aiofiles>=23.0.0
```

### System Requirements
- Python 3.9+
- SQLite 3
- 2GB RAM minimum
- 10GB disk space for logs and processed files

## Security Considerations

1. **API Keys**: Stored in `.env` file, never committed to version control
2. **File Access**: Restricted to configured directories only
3. **Web Interface**: Local access only by default (127.0.0.1)
4. **Database**: SQLite file permissions restricted to application user
5. **Logging**: No sensitive data logged (API keys, personal information)

## Monitoring & Maintenance

### Health Checks
- API connectivity tests
- Disk space monitoring
- Processing queue status
- Database connectivity

### Maintenance Tasks
- Log rotation (automatic)
- Database cleanup (old jobs after 90 days)
- Temporary file cleanup
- Configuration backup

This specification balances robustness with simplicity, perfect for processing 5 audio files per day with a clean, functional web interface.
