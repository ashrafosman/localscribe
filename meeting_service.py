import subprocess
import threading
import time
import uuid
import re
import base64
import io
import queue
from datetime import datetime
from pathlib import Path
import requests
import os
import signal
import numpy as np
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
            # Run stream with invalid capture device to get device list
            cmd = [str(self.config.WHISPER_STREAM_PATH), '-c', '-2']  # Invalid device ID to trigger device listing
            
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
            
            # Add system default as the first option (easiest to use)
            final_devices = [{'id': -1, 'name': 'System Default'}]
            
            # Find and label special devices
            other_devices = []
            for device in devices:
                if 'blackhole' in device['name'].lower():
                    device['name'] = f"{device['name']} (System Audio + Mic - Requires Setup)"
                elif 'aggregate' in device['name'].lower():
                    device['name'] = f"{device['name']} (Multi-Input - May Capture Both)"
                other_devices.append(device)
            
            # Add all other devices after system default
            final_devices.extend(other_devices)
            
            self.audio_devices = final_devices
            return final_devices
        except Exception as e:
            print(f"Error getting audio devices: {e}")
            # Return default device as fallback
            return [{'id': -1, 'name': 'Default Device'}]
            
        finally:
            pass  # No directory change cleanup needed
    
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
            'standup': 'Daily Standup',
            'one_on_one': '1:1 Meeting',
            'staff': 'Staff Meeting'
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

    def _extract_whisper_text(self, data):
        """Extract transcript text from a Whisper API response."""
        if isinstance(data, str):
            return data.strip()
        if not isinstance(data, dict):
            return str(data).strip()
        if "predictions" in data and isinstance(data["predictions"], list) and data["predictions"]:
            prediction = data["predictions"][0]
            if isinstance(prediction, str):
                return prediction.strip()
            if isinstance(prediction, list):
                return " ".join(str(item).strip() for item in prediction if str(item).strip())
            if isinstance(prediction, dict):
                if "transcription" in prediction:
                    return str(prediction["transcription"]).strip()
                if "transcript" in prediction:
                    return str(prediction["transcript"]).strip()
                if "text" in prediction:
                    return str(prediction["text"]).strip()
                if "generated_text" in prediction:
                    return str(prediction["generated_text"]).strip()
                if "segments" in prediction and isinstance(prediction["segments"], list):
                    segments = [
                        str(seg.get("text")).strip()
                        for seg in prediction["segments"]
                        if isinstance(seg, dict) and seg.get("text")
                    ]
                    return " ".join(seg for seg in segments if seg)
                return self._extract_whisper_text(prediction)
            return str(prediction).strip()
        if "text" in data:
            return str(data["text"]).strip()
        if "transcription" in data:
            return str(data["transcription"]).strip()
        if "transcript" in data:
            return str(data["transcript"]).strip()
        if "output" in data:
            return str(data["output"]).strip()
        if "choices" in data and data["choices"]:
            message = data["choices"][0].get("message", {})
            return self._extract_message_content(message).strip()
        return ""

    def _call_whisper_api(self, audio_base64):
        """Call Whisper API with a base64-encoded WAV payload."""
        headers = {
            "Content-Type": "application/json"
        }
        if self.config.WHISPER_API_TOKEN:
            headers["Authorization"] = f"Bearer {self.config.WHISPER_API_TOKEN}"

        payload = {"inputs": [audio_base64]}
        response = requests.post(self.config.WHISPER_API_URL, json=payload, headers=headers, timeout=30)
        if response.status_code != 200:
            raise Exception(f"API Error: {response.status_code}, {response.text}")
        return response.json()

    def check_whisper_api_ready(self):
        """Check if the Whisper API endpoint is reachable."""
        if not self.config.WHISPER_API_URL:
            raise Exception("WHISPER_API_URL is not configured")
        sample_rate = self.config.WHISPER_API_SAMPLE_RATE
        audio = np.zeros(int(sample_rate * 0.5), dtype=np.float32)
        audio_int16 = (audio * 32767).astype(np.int16)
        byte_io = io.BytesIO()
        from scipy.io import wavfile
        wavfile.write(byte_io, sample_rate, audio_int16)
        encoded_audio = base64.b64encode(byte_io.getvalue()).decode('utf-8')
        self._call_whisper_api(encoded_audio)
        return True

    def start_recording(self, meeting_name, audio_device_id=-1, prompt_type='meeting', audio_device_name=None):
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

        # Ensure uniqueness to avoid overwrite prompts
        def unique_name(base: str):
            candidate_txt = f"{base}.txt"
            candidate_sum = f"{base}.txt-summarized.txt"
            if not Path(candidate_txt).exists() and not Path(candidate_sum).exists():
                return candidate_txt, candidate_sum
            i = 2
            while True:
                candidate_txt = f"{base}_{i}.txt"
                candidate_sum = f"{base}_{i}.txt-summarized.txt"
                if not Path(candidate_txt).exists() and not Path(candidate_sum).exists():
                    return candidate_txt, candidate_sum
                i += 1

        transcript_filename, summary_filename = unique_name(base_filename)
        
        # Create meeting record
        meeting_record = {
            'id': meeting_id,
            'name': meeting_name,
            'sanitized_name': sanitized_name,
            'audio_device_id': audio_device_id,
            'audio_device_name': audio_device_name,
            'prompt_type': prompt_type,
            'start_time': datetime.now(),
            'transcript_filename': transcript_filename,
            'summary_filename': summary_filename,
            'transcript_path': None,
            'summary_path': None,
            'process': None,
            'whisper_mode': None,
            'stop_event': None,
            'stop_requested': False,
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
        meeting['stop_requested'] = True

        if meeting.get('whisper_mode') == 'api':
            stop_event = meeting.get('stop_event')
            if stop_event:
                stop_event.set()
                meeting['status'] = 'stopping'
        
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
            if meeting.get('stop_requested'):
                meeting['status'] = 'error'
                self._notify_callbacks(meeting_id, 'error', 'Recording stopped before start')
                return

            use_api = self.config.WHISPER_MODE == 'api' and bool(self.config.WHISPER_API_URL)
            fallback_reason = None
            if use_api:
                try:
                    self.check_whisper_api_ready()
                except Exception as e:
                    use_api = False
                    fallback_reason = str(e)
            if meeting.get('stop_requested'):
                meeting['status'] = 'error'
                self._notify_callbacks(meeting_id, 'error', 'Recording stopped before start')
                return

            if use_api:
                meeting['whisper_mode'] = 'api'
                self._run_api_recording(meeting_id)
                return

            # Update status
            meeting['whisper_mode'] = 'local'
            meeting['status'] = 'recording'
            status_message = 'Recording started'
            if fallback_reason:
                status_message = "Recording started (using local transcription; API unavailable)"
            self._notify_callbacks(meeting_id, 'recording', status_message)
            
            # Build whisper.cpp command - match the working implementation exactly
            cmd = [
                str(self.config.WHISPER_STREAM_PATH),
                '-m', str(self.config.WHISPER_MODEL_PATH),
                '-t', str(self.config.WHISPER_THREADS),
                '-kc',
                '-tdrz'  # This was missing! Critical for transcription quality
            ]

            # Only add capture device if not using system default (-1)
            # When device_id is -1, we let whisper.cpp choose its own default
            # This matches the working implementation behavior
            if meeting['audio_device_id'] != -1:
                cmd.extend(['-c', str(meeting['audio_device_id'])])
            # When no -c flag is provided, whisper.cpp uses its own default device selection
            
            cmd.extend(['-f', meeting['transcript_filename']])
            # Removed debug command output for clean CLI experience
            
            # Debug: print the command
            print(f"Running command: {' '.join(cmd)}")
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
            # Clean up process if it's still running
            if 'process' in locals() and meeting['process'] and meeting['process'].poll() is None:
                try:
                    meeting['process'].terminate()
                    meeting['process'].wait(timeout=5)
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
                        
                        # Removed raw output logging for clean CLI experience
                        
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
                                meeting['_last_transcription'] = clean_line
                                
                                # Send cleaned transcription text via callback
                                for callback in meeting.get('callbacks', []):
                                    try:
                                        callback(meeting_id, 'transcription', clean_line)
                                    except Exception as e:
                                        # Only show critical errors, not debug info
                                        pass
                    
                except queue.Empty:
                    continue
                except Exception as e:
                    print(f"Queue processing error: {e}")
                    break
            
        except Exception as e:
            print(f"Streaming error: {e}")

    def _run_api_recording(self, meeting_id):
        """Run recording using Whisper API"""
        meeting = self.active_recordings[meeting_id]
        stop_event = threading.Event()
        meeting['stop_event'] = stop_event
        meeting['status'] = 'recording'
        self._notify_callbacks(meeting_id, 'recording', 'Recording started (API)')

        audio_queue = queue.Queue()
        sample_rate = self.config.WHISPER_API_SAMPLE_RATE
        chunk_duration = self.config.WHISPER_API_CHUNK_DURATION
        device_id = meeting['audio_device_id']
        device_name = meeting.get('audio_device_name')
        transcript_path = Path(meeting['transcript_filename'])

        def record_audio():
            import sounddevice as sd
            try:
                stream_device = None if device_id == -1 else device_id
                if device_name:
                    try:
                        devices = sd.query_devices()
                        matches = [
                            idx for idx, dev in enumerate(devices)
                            if isinstance(dev.get('name'), str)
                            and device_name.lower() in dev['name'].lower()
                            and dev.get('max_input_channels', 0) > 0
                        ]
                        if matches:
                            stream_device = matches[0]
                    except Exception:
                        pass
                try:
                    device_info = sd.query_devices(stream_device, 'input')
                    max_channels = int(device_info.get('max_input_channels', 0))
                except Exception:
                    max_channels = 1

                if max_channels < 1:
                    raise Exception("Selected device has no input channels")
                channels = 1 if max_channels >= 1 else max_channels
                try:
                    default_in = sd.query_devices(None, 'input')
                    default_channels = int(default_in.get('max_input_channels', 1))
                except Exception:
                    default_channels = 1

                def callback(indata, frames, time_info, status):
                    if status:
                        print(status)
                    audio_queue.put(indata.copy())

                stream_channels = channels
                stream_device_choice = stream_device
                try:
                    with sd.InputStream(
                        device=stream_device_choice,
                        samplerate=sample_rate,
                        channels=stream_channels,
                        callback=callback,
                        blocksize=int(sample_rate * chunk_duration)
                    ):
                        while not stop_event.is_set():
                            time.sleep(0.1)
                except Exception:
                    stream_device_choice = None
                    stream_channels = 1 if default_channels >= 1 else channels
                    with sd.InputStream(
                        device=stream_device_choice,
                        samplerate=sample_rate,
                        channels=stream_channels,
                        callback=callback,
                        blocksize=int(sample_rate * chunk_duration)
                    ):
                        while not stop_event.is_set():
                            time.sleep(0.1)
            except Exception as e:
                meeting['status'] = 'error'
                stop_event.set()
                self._notify_callbacks(meeting_id, 'error', f'Recording error: {e}')

        def transcription_worker():
            with open(transcript_path, 'a') as transcript_file:
                while not stop_event.is_set() or not audio_queue.empty():
                    try:
                        audio_data = audio_queue.get(timeout=0.5)
                    except queue.Empty:
                        continue

                    try:
                        from scipy.io import wavfile

                        if audio_data.ndim > 1:
                            audio_data = np.mean(audio_data, axis=1)
                        audio_int16 = (audio_data * 32767).astype(np.int16)
                        byte_io = io.BytesIO()
                        wavfile.write(byte_io, sample_rate, audio_int16)
                        encoded_audio = base64.b64encode(byte_io.getvalue()).decode('utf-8')

                        response = self._call_whisper_api(encoded_audio)
                        transcript_text = self._extract_whisper_text(response)

                        if transcript_text:
                            last_transcription = meeting.get('_last_transcription', '')
                            if last_transcription != transcript_text:
                                meeting['_last_transcription'] = transcript_text
                                transcript_file.write(transcript_text + '\n')
                                transcript_file.flush()
                                for callback in meeting.get('callbacks', []):
                                    try:
                                        callback(meeting_id, 'transcription', transcript_text)
                                    except Exception:
                                        pass
                    except Exception as e:
                        print(f"Whisper API error: {e}")
                    time.sleep(1)

        record_thread = threading.Thread(target=record_audio, daemon=True)
        worker_thread = threading.Thread(target=transcription_worker, daemon=True)
        record_thread.start()
        worker_thread.start()

        while not stop_event.is_set():
            time.sleep(0.2)

        record_thread.join(timeout=5)
        worker_thread.join(timeout=5)

        if meeting['status'] == 'error':
            return

        meeting['status'] = 'processing'
        self._notify_callbacks(meeting_id, 'processing', 'Processing and summarizing...')
        self._process_recording(meeting_id)
    
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
        """Call summarization API"""
        messages = [
            {"role": "system", "content": prompt_content},
            {"role": "user", "content": f"Please summarize the following meeting transcript accordingly:\n\n{transcript_text}"}
        ]
        return self._call_chat_api(messages)

    def _extract_message_content(self, message):
        """Normalize model response content to a string."""
        if isinstance(message, str):
            return message
        if not isinstance(message, dict):
            return str(message)
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                    continue
                if not isinstance(item, dict):
                    parts.append(str(item))
                    continue
                if "text" in item and isinstance(item["text"], str):
                    parts.append(item["text"])
                if "summary_text" in item and isinstance(item["summary_text"], str):
                    parts.append(item["summary_text"])
                if "summary" in item and isinstance(item["summary"], list):
                    for summary in item["summary"]:
                        if isinstance(summary, dict) and isinstance(summary.get("summary_text"), str):
                            parts.append(summary["summary_text"])
            return "\n".join([part for part in parts if part])
        return str(content) if content is not None else ""

    def _call_chat_api(self, messages, extra_payload=None):
        """Call summary/chat API with custom messages"""
        url = self.config.SUMMARY_API_URL

        headers = {
            "Content-Type": "application/json"
        }
        if self.config.SUMMARY_API_TOKEN:
            headers["Authorization"] = f"Bearer {self.config.SUMMARY_API_TOKEN}"

        payload = {
            "model": self.config.SUMMARY_API_MODEL,
            "messages": messages
        }
        if extra_payload:
            payload.update(extra_payload)

        response = requests.post(url, json=payload, headers=headers)

        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict) and "choices" in data:
                message = data["choices"][0].get("message", {})
                return self._extract_message_content(message)
            if isinstance(data, dict) and "predictions" in data:
                prediction = data["predictions"][0]
                if isinstance(prediction, dict) and "choices" in prediction:
                    message = prediction["choices"][0].get("message", {})
                    return self._extract_message_content(message)
                if isinstance(prediction, dict) and "generated_text" in prediction:
                    return prediction["generated_text"]
                return self._extract_message_content(prediction)
            return self._extract_message_content(data)
        else:
            raise Exception(f"API Error: {response.status_code}, {response.text}")

    def summarize_text(self, transcript_text, prompt_content):
        """Summarize text with a custom prompt"""
        if not transcript_text.strip():
            raise ValueError("Transcript text is empty")
        if not prompt_content.strip():
            raise ValueError("Prompt content is empty")
        return self._call_summarization_api(transcript_text, prompt_content)

    def ask_question(self, transcript_text, question):
        """Answer a question based on the transcript"""
        if not transcript_text.strip():
            raise ValueError("Transcript text is empty")
        if not question.strip():
            raise ValueError("Question is empty")

        system_prompt = (
            "You are a meeting assistant. Answer the user's question using only the meeting transcript. "
            "If the answer is not in the transcript, say you don't know. Keep the response concise."
        )
        user_prompt = f"Transcript:\n{transcript_text}\n\nQuestion: {question}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        return self._call_chat_api(messages)

    def check_summary_ready(self):
        """Check if the summary model endpoint is reachable"""
        messages = [
            {"role": "system", "content": "You are a test assistant."},
            {"role": "user", "content": "Respond with OK."}
        ]
        self._call_chat_api(messages, extra_payload={"max_tokens": 4})
        return True
    
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
        
        # Look for transcript files (today only)
        today = datetime.now().date()
        for transcript_file in self.config.CALLS_OUTPUT_PATH.glob("*.txt"):
            if transcript_file.name.endswith("-summarized.txt"):
                continue

            mtime = datetime.fromtimestamp(transcript_file.stat().st_mtime).date()
            if mtime != today:
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
                'mtime': transcript_file.stat().st_mtime,
                'size': self._format_file_size(transcript_file.stat().st_size),
                'transcript_path': str(transcript_file),
                'summary_path': str(summary_file) if summary_file.exists() else None
            }
            
            files.append(file_info)
        
        # Sort by modification time (newest first)
        files.sort(key=lambda x: x['mtime'], reverse=True)

        for file_info in files:
            file_info.pop('mtime', None)
        
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
