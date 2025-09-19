## Quick install (macOS)

```bash
curl -fsSL https://raw.githubusercontent.com/aandreyev/transcription/main/install-macos.sh | bash
```

This will install Python 3.12 (via Homebrew if needed), clone/update the app to `~/Applications/Transcription`, run setup, and create a double-clickable `Start Transcription.command`.

Open the admin page at `http://127.0.0.1:8005/admin` to set API keys and folders.

### Auto-start on login (optional)

```bash
cd ~/Applications/Transcription
bash scripts/install-launchagent.sh
```

To remove:

```bash
bash scripts/uninstall-launchagent.sh
```

# Audio Processor

An intelligent audio transcription and processing system that automatically monitors a folder for audio files, transcribes them using Deepgram, processes them with OpenAI, and generates intelligent summaries with smart file naming.

## Features

- **Automatic File Monitoring**: Watches a designated folder for new audio files
- **High-Quality Transcription**: Uses Deepgram's Nova-2 model with speaker diarization
- **AI-Powered Analysis**: OpenAI GPT-4 processes transcripts to extract key information
- **Intelligent File Naming**: Automatically generates descriptive filenames based on content
- **Web Dashboard**: Real-time monitoring and management interface
- **Comprehensive Logging**: Detailed logging with job tracking
- **Health Monitoring**: System health checks and status reporting

## Supported Audio Formats

- MP3 (.mp3)
- WAV (.wav)
- M4A (.m4a)
- MP4 (.mp4)
- MOV (.mov)

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <repository-url>
cd audio-processor

# Run the setup script (recommended)
./setup.sh

# OR install manually:
# pip install -r requirements.txt
```

### 2. Configuration

1. Copy the example environment file:
```bash
cp config/.env.example config/.env
```

2. Edit `config/.env` with your settings:
```bash
# API Keys
DEEPGRAM_API_KEY=your_deepgram_key_here
OPENAI_API_KEY=your_openai_key_here

# Folder Paths (customize for your system)
WATCH_FOLDER=/path/to/your/input/folder
PROCESSED_FOLDER=/path/to/your/processed/folder
ERROR_FOLDER=/path/to/your/error/folder
OUTPUT_FOLDER=/path/to/your/output/folder
```

### 3. Create Required Folders

```bash
# Create the folder structure (adjust paths as needed)
mkdir -p ~/AudioProcessor/{input,processed,error,output}
mkdir -p data logs
```

### 4. Run the Application

```bash
# If you used the setup script:
./run.sh

# OR manually activate virtual environment and run:
source venv/bin/activate
python main.py
```

The application will start and display:
- Web interface at: http://127.0.0.1:8000
- File monitoring status
- System health information

## How It Works

1. **File Detection**: The system monitors the watch folder for new audio files
2. **File Validation**: Checks file format and ensures it's completely uploaded
3. **Transcription**: Sends audio to Deepgram for transcription with speaker diarization
4. **AI Processing**: OpenAI analyzes the transcript to extract:
   - Meeting summary
   - Key discussion points
   - Action items
   - Decisions made
   - Participant information
5. **Intelligent Naming**: Generates descriptive filenames based on:
   - Date information
   - Participant names
   - Meeting topic
   - Meeting type
   - Duration
6. **Output Generation**: Creates markdown files with:
   - AI analysis and summary
   - Full transcript
   - Metadata
7. **File Management**: Moves processed files to appropriate folders

## Configuration

### Main Configuration (`config/config.yaml`)

The main configuration file controls all aspects of the application:

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

### Environment Variables (`.env`)

```bash
# Required API Keys
DEEPGRAM_API_KEY=your_deepgram_key_here
OPENAI_API_KEY=your_openai_key_here

# Folder Paths
WATCH_FOLDER=/path/to/input/folder
PROCESSED_FOLDER=/path/to/processed/folder
ERROR_FOLDER=/path/to/error/folder
OUTPUT_FOLDER=/path/to/output/folder

# Database
DATABASE_URL=sqlite:///data/audio_processor.db
```

## Web Dashboard

Access the web dashboard at `http://127.0.0.1:8000` to:

- Monitor system health
- View processing statistics
- Track recent jobs
- Check service connections
- View processing logs

## API Endpoints

- `GET /` - Web dashboard
- `GET /api/health` - System health status
- `GET /api/stats` - Processing statistics
- `GET /api/jobs` - List jobs with filtering
- `GET /api/jobs/{job_id}` - Get specific job details
- `POST /api/process` - Manually trigger file processing
- `GET /api/logs` - Get application logs

## File Naming Intelligence

The system generates intelligent filenames using multiple information sources:

### Format
`YYYYMMDD [Meeting Type] with [Participants] re [Topic] - [Duration]min`

### Examples
- `20240115 Meeting with John Smith and Sarah Jones re Budget Review - 45min`
- `20240116 Call with Client re Contract Negotiation - 30min`
- `20240117 Interview with Jane Doe re Software Engineer Position - 60min`

### Information Sources
1. **AI Analysis**: Extracts participants, topics, and meeting types from transcript
2. **Filename Parsing**: Analyzes original filename for clues
3. **File Metadata**: Uses creation dates and audio metadata
4. **Audio Properties**: Includes duration information

## Troubleshooting

### Common Issues

1. **API Key Errors**
   - Ensure your Deepgram and OpenAI API keys are valid
   - Check that keys are properly set in the `.env` file

2. **Folder Permission Issues**
   - Ensure the application has read/write access to all configured folders
   - Check folder paths are correct and exist

3. **File Processing Failures**
   - Check the error folder for failed files
   - Review logs for specific error messages
   - Ensure audio files are in supported formats

4. **Web Interface Not Loading**
   - Check if port 8000 is available
   - Verify the web server started successfully in logs

### Logs

Logs are stored in the `logs/` directory with daily rotation:
- Application logs: `logs/audio_processor_YYYYMMDD.log`
- Database logs: Stored in SQLite database
- Web access logs: Console output

### Health Checks

The system performs automatic health checks for:
- Deepgram API connectivity
- OpenAI API connectivity
- Database connectivity
- Folder accessibility

## Development

### Project Structure

```
audio-processor/
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── config/
│   ├── config.yaml        # Main configuration
│   └── .env              # Environment variables
├── src/
│   ├── core/             # Core processing logic
│   │   ├── database.py   # Database operations
│   │   ├── deepgram_client.py  # Deepgram integration
│   │   ├── openai_client.py    # OpenAI integration
│   │   ├── file_namer.py       # Intelligent naming
│   │   ├── processor.py        # Main processing pipeline
│   │   └── file_monitor.py     # File monitoring
│   ├── utils/            # Utility modules
│   │   ├── config_manager.py   # Configuration management
│   │   └── logger.py          # Logging utilities
│   └── web/              # Web interface
│       └── app.py        # FastAPI application
├── data/                 # Database files
└── logs/                # Log files
```

### Adding New Features

1. **New Processing Steps**: Add to `src/core/processor.py`
2. **New API Endpoints**: Add to `src/web/app.py`
3. **New Configuration**: Update `config/config.yaml`
4. **New Dependencies**: Add to `requirements.txt`

## License

[Add your license information here]

## Support

[Add support contact information here]
