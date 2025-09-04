import subprocess
import threading
import time
import uuid
import re
from datetime import datetime
from pathlib import Path
import requests
import os
import signal
from config import Config

class MeetingService:
    def __init__(self):
        self.active_recordings = {}
        self.config = Config()
        self.audio_devices = None
        self.prompts_cache = None
        
    def get_audio_devices(self):
        """Get list of available audio capture devices"""
        if self.audio_devices is not None:
            return self.audio_devices
            
        try:
            # Change to whisper.cpp directory
            original_cwd = os.getcwd()
            os.chdir(self.config.WHISPER_CPP_PATH)
            
            # Run stream with invalid capture device to get device list
            cmd = ['./stream', '-c', '-2']  # Invalid device ID to trigger device listing
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Give it a moment to list devices then kill it
            time.sleep(1)
            process.terminate()
            stdout, stderr = process.communicate(timeout=5)
            
            # Parse device list from output
            devices = []
            output = stdout + stderr
            
            for line in output.split('\n'):
                if 'Capture device #' in line:
                    # Extract device info: "init:    - Capture device #0: 'Device Name'"
                    parts = line.split('#')
                    if len(parts) > 1:
                        device_part = parts[1]
                        device_id = device_part.split(':')[0].strip()
                        device_name = device_part.split("'")[1] if "'" in device_part else f"Device {device_id}"
                        
                        devices.append({
                            'id': int(device_id),
                            'name': device_name
                        })
            
            # Add default device option
            devices.insert(0, {'id': -1, 'name': 'Default Device'})
            
            self.audio_devices = devices
            return devices
            
        except Exception as e:
            print(f"Error getting audio devices: {e}")
            # Return default device as fallback
            return [{'id': -1, 'name': 'Default Device'}]
            
        finally:
            os.chdir(original_cwd)
    
    def get_available_prompts(self):
        """Get list of available summarization prompts"""
        if self.prompts_cache is not None:
            return self.prompts_cache
            
        prompts = []
        app_dir = Path(__file__).parent
        
        # Define prompt files and their display names
        prompt_files = {
            'meeting': 'Executive Meeting',
            'technical': 'Technical Review', 
            'sales': 'Sales Call',
            'standup': 'Daily Standup'
        }
        
        for file_key, display_name in prompt_files.items():
            prompt_file = app_dir / f"{file_key}.txt"
            if prompt_file.exists():
                prompts.append({
                    'id': file_key,
                    'name': display_name,
                    'file': str(prompt_file)
                })
        
        # Cache the results
        self.prompts_cache = prompts
        return prompts
    
    def get_prompt_content(self, prompt_id):
        """Get the content of a specific prompt"""
        prompts = self.get_available_prompts()
        
        for prompt in prompts:
            if prompt['id'] == prompt_id:
                try:
                    with open(prompt['file'], 'r') as f:
                        return f.read().strip()
                except Exception as e:
                    print(f"Error reading prompt file {prompt['file']}: {e}")
                    break
        
        # Fallback to default meeting prompt
        default_file = Path(__file__).parent / "meeting.txt"
        if default_file.exists():
            with open(default_file, 'r') as f:
                return f.read().strip()
        
        # Hard-coded fallback
        return "Summarize this meeting transcript with key points, action items, and attendees."

    def start_recording(self, meeting_name, audio_device_id=-1, prompt_type='meeting'):
        """Start a new meeting recording"""
        # Validate configuration
        errors = self.config.validate_paths()
        if errors:
            raise Exception(f"Configuration errors: {', '.join(errors)}")
        
        # Generate unique meeting ID
        meeting_id = str(uuid.uuid4())
        
        # Sanitize meeting name
        sanitized_name = self.config.sanitize_filename(meeting_name)
        
        # Generate filenames with current date
        current_date = datetime.now().strftime("%Y-%m-%d")
        base_filename = f"{current_date}_{sanitized_name}"
        transcript_filename = f"{base_filename}.txt"
        summary_filename = f"{base_filename}.txt-summarized.txt"
        
        # Create meeting record
        meeting_record = {
            'id': meeting_id,
            'name': meeting_name,
            'sanitized_name': sanitized_name,
            'audio_device_id': audio_device_id,
            'prompt_type': prompt_type,
            'start_time': datetime.now(),
            'transcript_filename': transcript_filename,
            'summary_filename': summary_filename,
            'transcript_path': None,
            'summary_path': None,
            'process': None,
            'status': 'starting',
            'callbacks': []
        }
        
        self.active_recordings[meeting_id] = meeting_record
        
        # Start recording in a separate thread
        thread = threading.Thread(target=self._run_recording, args=(meeting_id,))
        thread.daemon = True
        thread.start()
        
        return meeting_id
    
    def stop_recording(self, meeting_id):
        """Stop an active recording"""
        if meeting_id not in self.active_recordings:
            raise Exception("Meeting not found or not active")
        
        meeting = self.active_recordings[meeting_id]
        
        if meeting['process'] and meeting['process'].poll() is None:
            # Send SIGINT to gracefully stop the recording
            try:
                meeting['process'].send_signal(signal.SIGINT)
                meeting['status'] = 'stopping'
                
                # Wait a moment for graceful shutdown, then force kill if needed
                try:
                    meeting['process'].wait(timeout=5)
                except subprocess.TimeoutExpired:
                    meeting['process'].kill()
                    meeting['process'].wait()
                
            except Exception as e:
                print(f"Error stopping recording process: {e}")
                meeting['status'] = 'error'
                raise
        
        return True
    
    def get_meeting_status(self, meeting_id):
        """Get the current status of a meeting"""
        if meeting_id not in self.active_recordings:
            return None
        
        return self.active_recordings[meeting_id]['status']
    
    def add_status_callback(self, meeting_id, callback):
        """Add a callback to be notified of status changes"""
        if meeting_id in self.active_recordings:
            self.active_recordings[meeting_id]['callbacks'].append(callback)
    
    def _run_recording(self, meeting_id):
        """Run the actual recording process"""
        meeting = self.active_recordings[meeting_id]
        
        try:
            # Update status
            meeting['status'] = 'recording'
            self._notify_callbacks(meeting_id, 'recording', 'Recording started')
            
            # Change to whisper.cpp directory
            original_cwd = os.getcwd()
            os.chdir(self.config.WHISPER_CPP_PATH)
            
            # Build whisper.cpp command - simplified to match working version
            cmd = [
                './stream',
                '-m', str(self.config.WHISPER_MODEL_PATH)
            ]
            
            # Add optional parameters that work reliably
            if self.config.WHISPER_THREADS != 4:  # Only add if different from default
                cmd.extend(['-t', str(self.config.WHISPER_THREADS)])
                
            # Don't use -kc and -tdrz together as they might conflict
            
            # Only add capture device if not default (-1)
            if meeting['audio_device_id'] != -1:
                cmd.extend(['-c', str(meeting['audio_device_id'])])
                print(f"Using audio device #{meeting['audio_device_id']}")
            else:
                print("Using default audio device")
            
            cmd.extend(['-f', meeting['transcript_filename']])
            
            print(f"Running whisper.cpp command: {' '.join(cmd)}")
            
            # Start the whisper.cpp process
            meeting['process'] = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Stream output in real-time
            self._stream_transcription(meeting_id)
            
            # Wait for the process to complete
            meeting['process'].wait()
            
            if meeting['process'].returncode == 0 or meeting['process'].returncode == -2:  # -2 is SIGINT (graceful stop)
                meeting['status'] = 'processing'
                self._notify_callbacks(meeting_id, 'processing', 'Processing and summarizing...')
                
                # Process the recording
                self._process_recording(meeting_id)
                
            else:
                meeting['status'] = 'error'
                print(f"Recording failed with code {meeting['process'].returncode}")
                self._notify_callbacks(meeting_id, 'error', 'Recording failed')
                
        except Exception as e:
            meeting['status'] = 'error'
            print(f"Recording error: {e}")
            self._notify_callbacks(meeting_id, 'error', f'Recording error: {str(e)}')
        
        finally:
            # Restore working directory
            try:
                os.chdir(original_cwd)
            except:
                pass
            
            # Clean up
            if meeting_id in self.active_recordings:
                if meeting['status'] != 'complete':
                    meeting['status'] = 'error'
    
    def _stream_transcription(self, meeting_id):
        """Stream real-time transcription output"""
        meeting = self.active_recordings[meeting_id]
        process = meeting['process']
        
        import threading
        import queue
        
        def read_output(stream, output_queue, stream_name):
            """Read from a stream and put lines in queue"""
            try:
                while True:
                    line = stream.readline()
                    if not line:
                        break
                    output_queue.put((stream_name, line.strip()))
            except Exception as e:
                print(f"Error reading {stream_name}: {e}")
        
        try:
            # Create queue for output
            output_queue = queue.Queue()
            
            # Start threads to read both stdout and stderr
            stdout_thread = threading.Thread(target=read_output, args=(process.stdout, output_queue, 'stdout'))
            stderr_thread = threading.Thread(target=read_output, args=(process.stderr, output_queue, 'stderr'))
            
            stdout_thread.daemon = True
            stderr_thread.daemon = True
            
            stdout_thread.start()
            stderr_thread.start()
            
            # Process output from both streams
            while process.poll() is None or not output_queue.empty():
                try:
                    stream_name, line = output_queue.get(timeout=1)
                    
                    if line:
                        # Remove ANSI escape sequences
                        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                        clean_line = ansi_escape.sub('', line)
                        
                        # Remove other common terminal control sequences
                        clean_line = clean_line.replace('[2K', '').strip()
                        
                        # Only log non-empty raw output for debugging
                        if clean_line:
                            print(f"Raw output ({stream_name}): '{clean_line}'")  # Debug all output
                        
                        # Filter out system messages and only send actual transcription
                        # Skip system messages, but allow transcribed text
                        skip_patterns = [
                            'whisper_init_from_file',
                            'whisper_init_with_params',
                            'whisper_model_load',
                            'whisper_backend_init',
                            'ggml_metal_init',
                            'whisper_init_state',
                            'main: processing',
                            'main: n_new_line',
                            '[ Silence ]',
                            '[BLANK_AUDIO]',
                            '[Start speaking]',
                            'init:',
                            'whisper_print_timings',
                            'found ',
                            'attempt to open',
                            'obtained spec',
                            'sample rate:',
                            'format:',
                            'channels:',
                            'samples per frame:'
                        ]
                        
                        should_skip = any(pattern in clean_line for pattern in skip_patterns)
                        
                        # Additional filtering for meaningful transcription
                        is_meaningful = (
                            clean_line and 
                            not should_skip and 
                            clean_line.strip() and 
                            not clean_line.isspace() and
                            clean_line != '.' and  # Skip standalone periods
                            clean_line != '..' and  # Skip multiple periods
                            clean_line != '...' and  # Skip ellipsis
                            len(clean_line.strip()) > 1 and  # Must be more than 1 character
                            not clean_line.strip().replace('.', '').strip() == ''  # Not just periods
                        )
                        
                        if is_meaningful:
                            # Check for duplicates by storing last sent transcription in the dict
                            last_transcription = meeting.get('_last_transcription', '')
                            if last_transcription != clean_line:
                                print(f"Transcription output: '{clean_line}'")  # Debug output
                                meeting['_last_transcription'] = clean_line
                                
                                # Send cleaned transcription text via callback
                                for callback in meeting.get('callbacks', []):
                                    try:
                                        callback(meeting_id, 'transcription', clean_line)
                                    except Exception as e:
                                        print(f"Transcription callback error: {e}")
                            else:
                                print(f"Skipping duplicate transcription: '{clean_line}'")
                    
                except queue.Empty:
                    continue
                except Exception as e:
                    print(f"Queue processing error: {e}")
                    break
            
        except Exception as e:
            print(f"Streaming error: {e}")
    
    def _process_recording(self, meeting_id):
        """Process the recording (summarize and move files)"""
        meeting = self.active_recordings[meeting_id]
        
        try:
            # Run summarization
            transcript_path = Path(meeting['transcript_filename'])
            if transcript_path.exists():
                # Use custom summarization with selected prompt
                self._summarize_with_prompt(meeting_id, transcript_path)
                
                # Move files to output directory
                self._move_files(meeting_id)
                
                meeting['status'] = 'complete'
                self._notify_callbacks(meeting_id, 'complete', 'Meeting processing complete')
                
            else:
                meeting['status'] = 'error'
                self._notify_callbacks(meeting_id, 'error', 'Transcript file not found')
                
        except Exception as e:
            meeting['status'] = 'error'
            print(f"Processing error: {e}")
            self._notify_callbacks(meeting_id, 'error', f'Processing error: {str(e)}')
    
    def _summarize_with_prompt(self, meeting_id, transcript_path):
        """Summarize transcript using selected prompt type"""
        meeting = self.active_recordings[meeting_id]
        prompt_content = self.get_prompt_content(meeting['prompt_type'])
        
        try:
            # Read transcript
            with open(transcript_path, 'r') as file:
                transcript_text = file.read()
            
            # Call Perplexity API with custom prompt
            summary = self._call_summarization_api(transcript_text, prompt_content)
            
            # Write summary file
            summary_path = Path(meeting['summary_filename'])
            with open(summary_path, 'w') as summary_file:
                summary_file.write(summary)
            
            print(f"Summarization complete using {meeting['prompt_type']} prompt")
                
        except Exception as e:
            print(f"Summarization error: {e}")
            raise
    
    def _call_summarization_api(self, transcript_text, prompt_content):
        """Call Perplexity API for summarization"""
        url = "https://api.perplexity.ai/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.config.PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "sonar",
            "messages": [
                {"role": "system", "content": prompt_content},
                {"role": "user", "content": f"Please summarize the following meeting transcript accordingly:\n\n{transcript_text}"}
            ]
        }
        
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            raise Exception(f"API Error: {response.status_code}, {response.text}")
    
    def _move_files(self, meeting_id):
        """Move transcript and summary files to output directory"""
        meeting = self.active_recordings[meeting_id]
        
        # Move transcript
        transcript_src = Path(meeting['transcript_filename'])
        if transcript_src.exists():
            transcript_dst = self.config.CALLS_OUTPUT_PATH / meeting['transcript_filename']
            transcript_src.rename(transcript_dst)
            meeting['transcript_path'] = str(transcript_dst)
        
        # Move summary
        summary_src = Path(meeting['summary_filename'])
        if summary_src.exists():
            summary_dst = self.config.CALLS_OUTPUT_PATH / meeting['summary_filename']
            summary_src.rename(summary_dst)
            meeting['summary_path'] = str(summary_dst)
    
    def _notify_callbacks(self, meeting_id, status, message):
        """Notify all callbacks about status change"""
        meeting = self.active_recordings.get(meeting_id)
        if meeting and 'callbacks' in meeting:
            for callback in meeting['callbacks']:
                try:
                    callback(meeting_id, status, message)
                except Exception as e:
                    print(f"Callback error: {e}")
    
    def get_meeting_files(self):
        """Get list of all meeting files"""
        files = []
        
        if not self.config.CALLS_OUTPUT_PATH.exists():
            return files
        
        # Look for transcript files
        for transcript_file in self.config.CALLS_OUTPUT_PATH.glob("*.txt"):
            if transcript_file.name.endswith("-summarized.txt"):
                continue
                
            # Extract meeting info from filename
            parts = transcript_file.stem.split('_', 1)
            if len(parts) >= 2:
                date_str = parts[0]
                name = parts[1]
            else:
                date_str = "unknown"
                name = transcript_file.stem
            
            # Look for corresponding summary file
            summary_file = transcript_file.parent / f"{transcript_file.name}-summarized.txt"
            
            file_info = {
                'name': name.replace('_', ' ').title(),
                'date': date_str,
                'size': self._format_file_size(transcript_file.stat().st_size),
                'transcript_path': str(transcript_file),
                'summary_path': str(summary_file) if summary_file.exists() else None
            }
            
            files.append(file_info)
        
        # Sort by date (newest first)
        files.sort(key=lambda x: x['date'], reverse=True)
        
        return files
    
    def _format_file_size(self, size_bytes):
        """Format file size in human readable format"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
    
    def cleanup_completed_meetings(self):
        """Clean up completed meetings from memory"""
        to_remove = []
        for meeting_id, meeting in self.active_recordings.items():
            if meeting['status'] in ['complete', 'error']:
                # Keep for a while to allow status queries, then remove
                if hasattr(meeting, 'end_time'):
                    if (datetime.now() - meeting['end_time']).seconds > 300:  # 5 minutes
                        to_remove.append(meeting_id)
                else:
                    meeting['end_time'] = datetime.now()
        
        for meeting_id in to_remove:
            del self.active_recordings[meeting_id]
    
    def cleanup_all_meetings(self):
        """Clean up all active meetings and processes"""
        for meeting_id, meeting in list(self.active_recordings.items()):
            try:
                # Stop any running processes
                if meeting.get('process') and meeting['process'].poll() is None:
                    print(f"Stopping recording process for meeting {meeting_id}")
                    try:
                        meeting['process'].send_signal(signal.SIGINT)
                        meeting['process'].wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        meeting['process'].kill()
                        meeting['process'].wait()
                    except Exception as e:
                        print(f"Error stopping process for meeting {meeting_id}: {e}")
                
                # Update status
                if meeting['status'] in ['recording', 'processing']:
                    meeting['status'] = 'interrupted'
                
            except Exception as e:
                print(f"Error cleaning up meeting {meeting_id}: {e}")
        
        # Clear all recordings
        self.active_recordings.clear()