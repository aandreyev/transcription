That's an excellent approach! Building a local Python application gives you maximum control, privacy, and the flexibility to customize every step of the workflow. Deepgram is a fantastic choice for transcription due to its accuracy and robust speaker diarization.

Here's a breakdown of how you can build this Python application, along with code snippets and libraries you'll need.

Core Components of Your Python Application

Folder Monitoring: Detect new audio/video files in your OneDrive sync folder.

Deepgram Integration: Send files for transcription and retrieve results with speaker diarization.

LLM Integration (e.g., OpenAI): Send the Deepgram transcript to an LLM with specific prompts.

Output Management: Save the processed information (lists, summaries, etc.) to new files, potentially back into OneDrive or other locations.

Error Handling & Logging: Robustly handle issues and log activity for debugging.

Required Libraries

You'll need to install these:

Bash
pip install watchdog deepgram-sdk openai python-dotenv
watchdog: For monitoring the file system for changes (new files).

deepgram-sdk: The official Deepgram Python SDK for easy API interaction.

openai: The official OpenAI Python SDK for interacting with GPT models.

python-dotenv: To securely load API keys from a .env file.

msal / requests (for OneDrive uploads): OneDrive integration can be a bit more involved. We'll discuss options.

1. Folder Monitoring with watchdog

This library is perfect for continuously watching a directory for new files.

monitor_folder.py

Python
import time
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
WATCH_FOLDER = os.getenv("WATCH_FOLDER", "/path/to/your/onedrive/meetings")
PROCESSED_FOLDER = os.getenv("PROCESSED_FOLDER", "/path/to/your/onedrive/processed_meetings")
ERROR_FOLDER = os.getenv("ERROR_FOLDER", "/path/to/your/onedrive/error_meetings")

# Ensure output directories exist
os.makedirs(PROCESSED_FOLDER, exist_ok=True)
os.makedirs(ERROR_FOLDER, exist_ok=True)


class MyHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            file_path = event.src_path
            print(f"Detected new file: {file_path}")
            # Add a small delay to ensure the file is fully written,
            # especially for larger files being synced by OneDrive.
            time.sleep(5)
            # You would call your main processing function here
            process_audio_file(file_path)

def process_audio_file(file_path):
    print(f"Processing file: {file_path}")
    # Placeholder for the main logic
    # In a real application, you'd call Deepgram, then OpenAI, then save results.
    # For now, let's simulate success or failure.
    try:
        # Simulate transcription and AI processing
        print(f"Transcribing {file_path} with Deepgram...")
        transcription_result = transcribe_with_deepgram(file_path)
        print("Transcription complete. Applying AI prompts...")
        ai_processed_content = apply_llm_prompts(transcription_result)
        print("AI processing complete. Saving results...")
        save_results(file_path, ai_processed_content)

        # Move processed file
        base_name = os.path.basename(file_path)
        new_path = os.path.join(PROCESSED_FOLDER, base_name)
        os.rename(file_path, new_path)
        print(f"Successfully processed and moved {file_path} to {PROCESSED_FOLDER}")

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        # Move to error folder
        base_name = os.path.basename(file_path)
        new_path = os.path.join(ERROR_FOLDER, base_name)
        os.rename(file_path, new_path)
        print(f"Moved {file_path} to {ERROR_FOLDER} due to error.")


def main():
    event_handler = MyHandler()
    observer = Observer()
    observer.schedule(event_handler, WATCH_FOLDER, recursive=False) # recursive=True if you have subfolders

    print(f"Monitoring folder: {WATCH_FOLDER}")
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()

.env file (in the same directory as your script):

DEEPGRAM_API_KEY="YOUR_DEEPGRAM_API_KEY"
OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
WATCH_FOLDER="/Users/yourusername/OneDrive/Meetings/Input" # Adjust this path for your Mac Mini
PROCESSED_FOLDER="/Users/yourusername/OneDrive/Meetings/Processed"
ERROR_FOLDER="/Users/yourusername/OneDrive/Meetings/Errors"
Important: Replace the placeholder paths with your actual OneDrive sync folder paths on your Mac Mini. On macOS, OneDrive usually syncs to ~/OneDrive or ~/Library/CloudStorage/OneDrive-Personal.

2. Deepgram Integration (Transcription with Diarization)

This function will handle sending the audio file to Deepgram and parsing the diarized transcript.

Python
# deepgram_integration.py (create this new file)
import os
from deepgram import DeepgramClient, DeepgramClientOptions, FileSource
from dotenv import load_dotenv

load_dotenv()

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

def transcribe_with_deepgram(audio_file_path):
    try:
        # Configure Deepgram client with options
        config: DeepgramClientOptions = DeepgramClientOptions(
            verbose=1, # Set to 0 for less verbose logging
        )
        deepgram = DeepgramClient(DEEPGRAM_API_KEY, config)

        with open(audio_file_path, "rb") as audio_file:
            buffer_data = audio_file.read()

        payload: FileSource = {
            "buffer": buffer_data,
        }

        # Configure transcription options for diarization and smart formatting
        options = {
            "model": "nova-2",  # Recommended for accuracy, especially with diarization
            "punctuate": True,
            "paragraphs": True, # This can help structure the output
            "speaker_diarize": True, # Crucial for speaker identification
            "smart_format": True,   # Improves readability (e.g., numbers, dates)
            "utt_split": 1.5, # Split utterances after a 1.5 second pause
        }

        print(f"Sending {audio_file_path} to Deepgram for transcription...")
        response = deepgram.listen.prerecorded.v("1").transcribe_file(payload, options)

        # Process the response to get a readable transcript with speakers
        full_transcript = []
        if response.results and response.results.channels:
            for channel in response.results.channels:
                for alternative in channel.alternatives:
                    if alternative.paragraphs:
                        for paragraph in alternative.paragraphs.paragraphs:
                            speaker = paragraph.speaker
                            transcript_text = " ".join([word.word for word in paragraph.words])
                            full_transcript.append(f"[Speaker {speaker}]: {transcript_text}")
                    else:
                        # Fallback if paragraphs feature isn't ideal for some reason
                        # You might need to manually reconstruct with word-level speaker info
                        current_speaker = -1
                        current_utterance = []
                        for word_data in alternative.words:
                            if word_data.speaker != current_speaker:
                                if current_utterance:
                                    full_transcript.append(f"[Speaker {current_speaker}]: {' '.join(current_utterance)}")
                                current_speaker = word_data.speaker
                                current_utterance = [word_data.word]
                            else:
                                current_utterance.append(word_data.word)
                        if current_utterance:
                            full_transcript.append(f"[Speaker {current_speaker}]: {' '.join(current_utterance)}")

        return "\n".join(full_transcript)

    except Exception as e:
        print(f"Deepgram transcription error: {e}")
        raise

3. LLM Integration (OpenAI for AI Prompts)

This part will take the diarized transcript and apply your AI prompts.

Python
# llm_integration.py (create this new file)
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

def apply_llm_prompts(transcript_text):
    if not transcript_text:
        return "No transcript to process."

    # Define your prompts
    summary_prompt = "Summarize the following meeting transcript into key discussion points and action items. Identify who is responsible for each action item. Also, create a separate list of all decisions made during the meeting. \n\nTranscript:\n" + transcript_text
    
    # You can add more specific prompts for different types of lists if needed
    # For example:
    # tasks_prompt = "From the following transcript, extract all explicit tasks or to-do items, along with the person assigned to them if mentioned. Format as a bulleted list. \n\nTranscript:\n" + transcript_text
    # decisions_prompt = "List all explicit decisions made in the following meeting transcript. \n\nTranscript:\n" + transcript_text


    try:
        print("Sending transcript to OpenAI for summarization and list extraction...")
        # Use Chat Completion API for better control over responses
        response = client.chat.completions.create(
            model="gpt-4o",  # Or "gpt-4-turbo", "gpt-3.5-turbo" depending on your needs and cost
            messages=[
                {"role": "system", "content": "You are a helpful meeting assistant that summarizes transcripts and extracts key information."},
                {"role": "user", "content": summary_prompt}
            ],
            temperature=0.7, # Adjust creativity; lower for more factual, higher for more imaginative
            max_tokens=2000 # Adjust based on expected output length
        )

        processed_content = response.choices[0].message.content
        return processed_content

    except Exception as e:
        print(f"OpenAI API error: {e}")
        raise

4. Output Management (Saving to Files)

This will save the processed content. For OneDrive integration, the easiest way is to save to your local OneDrive sync folder, and OneDrive will handle the cloud sync.

Python
# output_management.py (create this new file)
import os
from datetime import datetime

def save_results(original_file_path, processed_content):
    # Determine the base filename (without extension)
    base_name = os.path.splitext(os.path.basename(original_file_path))[0]
    
    # Create a timestamp for uniqueness and sorting
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Define output filename
    output_filename = f"{base_name}_summary_{timestamp}.txt"
    
    # Use the PROCESSED_FOLDER defined in monitor_folder.py or a new one
    output_folder = os.getenv("PROCESSED_FOLDER") # Assuming PROCESSED_FOLDER is configured for output
    if not output_folder:
        output_folder = os.path.join(os.path.dirname(original_file_path), "AI_Processed_Output")
        os.makedirs(output_folder, exist_ok=True)

    output_path = os.path.join(output_folder, output_filename)

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(processed_content)
        print(f"Saved processed content to: {output_path}")
    except Exception as e:
        print(f"Error saving results to file: {e}")
        raise

Putting It All Together (Modify monitor_folder.py)

Now, integrate the functions into your process_audio_file function in monitor_folder.py.

monitor_folder.py (updated)

Python
import time
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from dotenv import load_dotenv

# Import your new modules
from deepgram_integration import transcribe_with_deepgram
from llm_integration import apply_llm_prompts
from output_management import save_results

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
WATCH_FOLDER = os.getenv("WATCH_FOLDER", "/path/to/your/onedrive/meetings/input")
PROCESSED_FOLDER = os.getenv("PROCESSED_FOLDER", "/path/to/your/onedrive/meetings/processed")
ERROR_FOLDER = os.getenv("ERROR_FOLDER", "/path/to/your/onedrive/meetings/errors")

# Ensure output directories exist
os.makedirs(WATCH_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)
os.makedirs(ERROR_FOLDER, exist_ok=True)


class MyHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            file_path = event.src_path
            print(f"Detected new file: {file_path}")
            # Add a small delay to ensure the file is fully written by OneDrive sync
            # This is crucial for larger files. Adjust as needed.
            time.sleep(10)
            self._process_file_safely(file_path)

    def _process_file_safely(self, file_path):
        """Wrapper to handle moving files to processed or error folders."""
        print(f"Attempting to process file: {file_path}")
        try:
            # Check if the file is still being written
            # Basic check: file size should stabilize.
            initial_size = -1
            for _ in range(5): # Check 5 times over 5*5=25 seconds
                current_size = os.path.getsize(file_path)
                if current_size == initial_size and current_size > 0:
                    print(f"File size stable for {file_path}. Proceeding.")
                    break
                initial_size = current_size
                time.sleep(5)
            else:
                # If loop completes, file size never stabilized or was 0
                if initial_size == 0:
                    raise ValueError(f"File {file_path} is empty. Skipping.")
                else:
                    print(f"Warning: File size for {file_path} did not stabilize after multiple checks. Proceeding anyway.")

            # Main processing logic
            print(f"Transcribing {file_path} with Deepgram...")
            transcription_result = transcribe_with_deepgram(file_path)
            print("Transcription complete. Applying AI prompts...")
            ai_processed_content = apply_llm_prompts(transcription_result)
            print("AI processing complete. Saving results...")
            save_results(file_path, ai_processed_content)

            # Move processed file to PROCESSED_FOLDER
            base_name = os.path.basename(file_path)
            new_path = os.path.join(PROCESSED_FOLDER, base_name)
            os.rename(file_path, new_path)
            print(f"Successfully processed and moved {file_path} to {PROCESSED_FOLDER}")

        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            # Move to error folder
            base_name = os.path.basename(file_path)
            new_path = os.path.join(ERROR_FOLDER, base_name)
            try:
                os.rename(file_path, new_path)
                print(f"Moved {file_path} to {ERROR_FOLDER} due to error.")
            except OSError as move_error:
                print(f"Could not move {file_path} to error folder: {move_error}. It might be locked or already moved.")


def main():
    event_handler = MyHandler()
    observer = Observer()
    observer.schedule(event_handler, WATCH_FOLDER, recursive=False)

    print(f"Monitoring folder: {WATCH_FOLDER}")
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()

How to Run Your Application

Create Project Folder: Create a new folder for your project (e.g., MeetingProcessor).

Create Files: Save the code snippets above into their respective .py files:

monitor_folder.py

deepgram_integration.py

llm_integration.py

output_management.py

.env

Set Up .env: Fill in your Deepgram and OpenAI API keys, and crucially, the correct paths for your OneDrive folders.

Deepgram API Key: Get this from your Deepgram console.

OpenAI API Key: Get this from your OpenAI platform.

OneDrive Paths: On your Mac Mini, the OneDrive sync folder is typically found in your home directory, often ~/OneDrive or under ~/Library/CloudStorage/OneDrive-Personal.

Example: /Users/yourusername/Library/CloudStorage/OneDrive-Personal/Meetings/Input

Install Dependencies: Open your terminal, navigate to your project folder, and run:

Bash
pip install watchdog deepgram-sdk openai python-dotenv
Run the Application:

Bash
python monitor_folder.py
This script will now run continuously in your terminal, watching the specified input folder.

Testing Your Workflow

Drop an audio or video file (MP3, WAV, M4A, MP4, etc.) into your designated WATCH_FOLDER in OneDrive.

Your Python script should detect the new file.

It will upload it to Deepgram for transcription.

It will then send the diarized transcript to OpenAI.

OpenAI will process it according to your prompts.

The final output (e.g., summary, lists) will be saved as a new text file in your PROCESSED_FOLDER.

The original audio/video file will be moved from WATCH_FOLDER to PROCESSED_FOLDER.

Next Steps & Enhancements

Error Reporting: Instead of just printing errors, you might want to send an email notification, log to a file, or integrate with a monitoring service.

Concurrency: For processing multiple files simultaneously, consider using threading or asyncio to handle Deepgram and OpenAI calls in parallel, especially if you expect many files to be dropped at once.

File Type Filtering: Add logic in MyHandler.on_created to only process specific audio/video file types.

Detailed Output: You could expand output_management.py to:

Save the raw Deepgram JSON response for debugging.

Generate different output formats (e.g., Markdown, HTML, CSV for action items).

Create separate files for summaries, action items, and decisions.

More Advanced AI Prompts: Experiment heavily with your OpenAI prompts to get exactly the kind of summaries, lists, and extractions you need. Be explicit about formatting (e.g., "Use markdown bullet points," "Format as a JSON object with 'summary', 'action_items', 'decisions' keys").

User Interface (Optional): If you want a more user-friendly experience than a terminal, consider building a simple GUI with Tkinter or PyQt, though this adds complexity.

Deployment: For "always-on" functionality, you'd typically run this script as a background service or daemon on your Mac Mini. You can use tools like launchd on macOS to ensure it starts on boot and restarts if it crashes.

This local Python application approach is robust and provides a great foundation for your automated transcription and AI analysis workflow!