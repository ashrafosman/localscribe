#!/usr/bin/env python3
"""
LocalScribe CLI - Command Line Recording Interface
Directly controls whisper.cpp for reliable audio capture
"""

import sys
import os
import signal
import subprocess
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from config import Config
from meeting_service import MeetingService
import argparse

class LocalScribeCLI:
    def __init__(self):
        self.meeting_service = MeetingService()
        self.current_recording = None
        self.is_recording = False
        
    def list_audio_devices(self):
        """List available audio devices"""
        try:
            devices = self.meeting_service.get_audio_devices()
            print("\nAvailable Audio Devices:")
            print("=" * 40)
            for i, device in enumerate(devices):
                print(f"  {i}: {device['name']}")
            print()
            
            print("💡 Audio Capture Options:")
            print("   • Device 0 (System Default): Captures microphone only - works immediately")
            print("   • Devices with 'Multi-Input': May capture both speakers and mic")
            print("   • Devices with 'Requires Setup': Need audio routing configuration")
            print("   • Run --setup-audio for detailed setup instructions")
            print()
            
            return devices
        except Exception as e:
            print(f"Error listing audio devices: {e}")
            return []
    
    def list_prompts(self):
        """List available summary prompts"""
        try:
            prompts = self.meeting_service.get_available_prompts()
            print("\nAvailable Summary Types:")
            print("=" * 40)
            for i, prompt in enumerate(prompts):
                print(f"  {i}: {prompt['name']}")
            print()
            return prompts
        except Exception as e:
            print(f"Error listing prompts: {e}")
            return []
    
    def start_interactive_recording(self):
        """Start an interactive recording session"""
        print("🎙️📝 LocalScribe - Interactive Recording")
        print("=" * 50)
        
        # Get meeting name
        while True:
            meeting_name = input("Enter meeting name: ").strip()
            if meeting_name:
                break
            print("Meeting name cannot be empty.")
        
        # Show and select audio device
        devices = self.list_audio_devices()
        if not devices:
            print("No audio devices found!")
            return
        
        while True:
            try:
                device_input = input(f"Select audio device (0-{len(devices)-1}, default=0): ").strip()
                if not device_input:
                    device_idx = 0
                    device_id = devices[0]['id']
                    break
                else:
                    device_idx = int(device_input)
                    if 0 <= device_idx < len(devices):
                        device_id = devices[device_idx]['id']
                        break
                    else:
                        print(f"Please enter a number between 0 and {len(devices)-1}")
            except ValueError:
                print("Please enter a valid number")
        
        print(f"Selected: {devices[device_idx]['name']}")
        
        # Show and select prompt type
        prompts = self.list_prompts()
        if prompts:
            while True:
                try:
                    prompt_input = input(f"Select summary type (0-{len(prompts)-1}, default=0): ").strip()
                    if not prompt_input:
                        prompt_idx = 0
                        prompt_type = prompts[0]['id']
                        break
                    else:
                        prompt_idx = int(prompt_input)
                        if 0 <= prompt_idx < len(prompts):
                            prompt_type = prompts[prompt_idx]['id']
                            break
                        else:
                            print(f"Please enter a number between 0 and {len(prompts)-1}")
                except ValueError:
                    print("Please enter a valid number")
            
            print(f"Selected: {prompts[prompt_idx]['name']}")
        else:
            prompt_type = 'meeting'
        
        # Start recording
        self.start_recording(meeting_name, device_id, prompt_type)
    
    def start_recording(self, meeting_name, device_id=-1, prompt_type='meeting'):
        """Start a recording session"""
        try:
            print(f"\n🎬 Starting recording: {meeting_name}")
            print(f"📱 Audio device: {device_id}")
            print(f"📋 Summary type: {prompt_type}")
            print("=" * 50)
            
            # Set up status callback for clean real-time transcription
            def status_callback(meeting_id, status, message):
                if status == 'transcription':
                    # Clean real-time transcription output
                    print(f"{message}", end=" ", flush=True)
                elif status in ['recording', 'processing', 'complete']:
                    print(f"\nℹ️  {message}")
                else:
                    print(f"ℹ️  {message}")
            
            # Start the recording
            self.current_recording = self.meeting_service.start_recording(
                meeting_name, device_id, prompt_type
            )
            self.meeting_service.add_status_callback(self.current_recording, status_callback)
            self.is_recording = True
            
            print(f"✅ Recording started! Meeting ID: {self.current_recording}")
            print("🗣️  Speak now... Press Ctrl+C to stop recording")
            print("=" * 50)
            
            # Wait for user to stop recording
            try:
                while self.is_recording:
                    time.sleep(1)
                    # Check if recording is still active
                    status = self.meeting_service.get_meeting_status(self.current_recording)
                    if status in ['complete', 'error']:
                        break
            except KeyboardInterrupt:
                print("\n⏹️  Stopping recording...")
                self.stop_recording()
            
        except Exception as e:
            print(f"❌ Error starting recording: {e}")
    
    def stop_recording(self):
        """Stop the current recording"""
        if not self.current_recording:
            print("No active recording to stop")
            return
        
        try:
            self.meeting_service.stop_recording(self.current_recording)
            print("⏹️  Recording stopped. Processing...")
            
            # Wait for processing to complete
            while True:
                status = self.meeting_service.get_meeting_status(self.current_recording)
                if status == 'complete':
                    print("✅ Recording complete and summarized!")
                    break
                elif status == 'error':
                    print("❌ Error processing recording")
                    break
                time.sleep(1)
                
            self.is_recording = False
            self.current_recording = None
            
        except Exception as e:
            print(f"❌ Error stopping recording: {e}")
    
    def list_recordings(self):
        """List all recorded meetings"""
        try:
            files = self.meeting_service.get_meeting_files()
            if not files:
                print("No recordings found.")
                return
            
            print("\n📁 Recorded Meetings:")
            print("=" * 60)
            for i, file_info in enumerate(files, 1):
                print(f"{i}. {file_info['name']} ({file_info['date']}) - {file_info['size']}")
                if file_info['summary_path']:
                    print(f"   📝 Transcript: {file_info['transcript_path']}")
                    print(f"   📋 Summary: {file_info['summary_path']}")
                else:
                    print(f"   📝 Transcript: {file_info['transcript_path']}")
                    print(f"   📋 Summary: Not available")
                print()
                
        except Exception as e:
            print(f"❌ Error listing recordings: {e}")
    
    def show_audio_setup(self):
        """Show detailed audio setup instructions"""
        print("🎙️ LocalScribe Audio Setup Guide")
        print("=" * 50)
        print()
        print("🎤 DEFAULT: System Default (Device 0)")
        print("   • Works immediately - no setup required")
        print("   • Captures microphone input only")
        print("   • Good for: Recording your voice, in-person meetings")
        print()
        print("🔊 ADVANCED: Capture SPEAKERS + MICROPHONE")
        print("   • Requires audio routing setup (steps below)")
        print("   • Captures both your voice AND computer audio")
        print("   • Good for: Video calls, system audio, presentations")
        print()
        print("📋 Step 1: Open Audio MIDI Setup")
        print("   • Applications → Utilities → Audio MIDI Setup")
        print()
        print("📋 Step 2: Create Multi-Output Device")
        print("   • Click '+' → Create Multi-Output Device")
        print("   • Check: Your speakers/headphones")
        print("   • Check: BlackHole 2ch")
        print("   • Name it: 'Speakers + BlackHole'")
        print()
        print("📋 Step 3: Create Aggregate Device")
        print("   • Click '+' → Create Aggregate Device")
        print("   • Check: Your microphone")
        print("   • Check: BlackHole 2ch")
        print("   • Name it: 'Mic + BlackHole'")
        print()
        print("📋 Step 4: Configure macOS Audio")
        print("   • System Preferences → Sound → Output")
        print("   • Select: 'Speakers + BlackHole'")
        print()
        print("📋 Step 5: Use in LocalScribe")
        print("   • Select a device with 'Multi-Input' in the name")
        print("   • Or a device with 'System Audio + Mic' if properly configured")
        print()
        print("✅ Now LocalScribe will capture both speakers and microphone!")
        print()
        print("🚀 QUICK START: Just use Device 0 (System Default) to get started!")
        print()

def main():
    parser = argparse.ArgumentParser(description='LocalScribe CLI - Smart Meeting Transcription')
    parser.add_argument('--list-devices', action='store_true', help='List available audio devices')
    parser.add_argument('--list-prompts', action='store_true', help='List available summary prompts')
    parser.add_argument('--list-recordings', action='store_true', help='List recorded meetings')
    parser.add_argument('--record', action='store_true', help='Start interactive recording')
    parser.add_argument('--setup-audio', action='store_true', help='Show audio setup instructions')
    parser.add_argument('--meeting-name', type=str, help='Meeting name for recording')
    parser.add_argument('--device-id', type=int, default=-1, help='Audio device ID')
    parser.add_argument('--prompt-type', type=str, default='meeting', help='Summary prompt type')
    
    args = parser.parse_args()
    
    # Validate configuration
    errors = Config.validate_paths()
    if errors:
        print("❌ Configuration errors:")
        for error in errors:
            print(f"  - {error}")
        print("\nPlease fix these issues before running LocalScribe.")
        sys.exit(1)
    
    cli = LocalScribeCLI()
    
    # Handle different commands
    if args.list_devices:
        cli.list_audio_devices()
    elif args.list_prompts:
        cli.list_prompts()
    elif args.list_recordings:
        cli.list_recordings()
    elif args.setup_audio:
        cli.show_audio_setup()
    elif args.record:
        cli.start_interactive_recording()
    elif args.meeting_name:
        # Direct recording with specified parameters
        cli.start_recording(args.meeting_name, args.device_id, args.prompt_type)
    else:
        # Default: show help and start interactive mode
        print("🎙️📝 LocalScribe - Smart Meeting Transcription")
        print("=" * 50)
        print("Usage options:")
        print("  python record_cli.py --record              # Interactive recording")
        print("  python record_cli.py --setup-audio         # Audio setup guide")
        print("  python record_cli.py --list-devices        # List audio devices")
        print("  python record_cli.py --list-recordings     # Show past recordings")
        print("  python record_cli.py --meeting-name 'Meeting Name'  # Quick recording")
        print("")
        print("💡 First time? Run: python record_cli.py --setup-audio")
        print("")
        
        choice = input("Start interactive recording? (y/N): ").strip().lower()
        if choice in ['y', 'yes']:
            cli.start_interactive_recording()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)