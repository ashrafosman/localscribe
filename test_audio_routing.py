#!/usr/bin/env python3
"""
Test script to identify which audio device configuration captures both speakers and mic
"""

import subprocess
import time
import os
from pathlib import Path

def test_device(device_id, device_name):
    """Test an audio device to see what it captures"""
    print(f"\n🎧 Testing Device {device_id}: {device_name}")
    print("=" * 60)
    
    # Change to whisper directory
    whisper_dir = Path("/Users/ashraf.osman/Documents/Work/whisper.cpp")
    os.chdir(whisper_dir)
    
    # Build command
    if device_id == -1:
        cmd = ["./stream", "-m", "models/ggml-small.en-tdrz.bin", "-t", "8", "-kc", "-tdrz", "-f", f"test_device_default.txt"]
    else:
        cmd = ["./stream", "-m", "models/ggml-small.en-tdrz.bin", "-t", "8", "-kc", "-tdrz", "-c", str(device_id), "-f", f"test_device_{device_id}.txt"]
    
    print(f"Command: {' '.join(cmd)}")
    print("\n🗣️ Please speak AND play some audio from your computer...")
    print("⏱️ Recording for 10 seconds...")
    
    # Start recording
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Wait for recording
    time.sleep(10)
    
    # Stop recording
    process.terminate()
    process.wait()
    
    # Read the results
    if device_id == -1:
        output_file = "test_device_default.txt"
    else:
        output_file = f"test_device_{device_id}.txt"
    
    if Path(output_file).exists():
        with open(output_file, 'r') as f:
            content = f.read().strip()
        
        print(f"\n📝 Captured Content:")
        print("-" * 40)
        print(content if content else "[No content captured]")
        print("-" * 40)
        
        # Analyze content
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        word_count = len(' '.join(lines).split())
        
        print(f"📊 Analysis:")
        print(f"   • Lines captured: {len(lines)}")
        print(f"   • Word count: {word_count}")
        print(f"   • Quality: {'Good' if word_count > 3 else 'Poor/Silent'}")
        
        # Clean up
        Path(output_file).unlink()
        
        return word_count > 3
    else:
        print("❌ No output file created")
        return False

def main():
    """Test different audio devices to find the one that captures both mic and speakers"""
    print("🎙️ LocalScribe Audio Device Tester")
    print("=" * 60)
    print("This will test different audio devices to find which one")
    print("can capture both your microphone AND computer speakers.")
    print("\nFor each test:")
    print("1. Speak into your microphone")  
    print("2. Play audio from your computer (YouTube, music, etc.)")
    print("3. Wait for the test to complete")
    print("\n" + "=" * 60)
    
    input("Press Enter to start testing...")
    
    # Test devices in order of priority
    test_devices = [
        (-1, "System Default"),
        (2, "BlackHole 2ch"),
        (7, "Aggregate Device"),
        (8, "Aggregate Device (2)"),
        (5, "Microsoft Teams Audio"),
        (6, "ZoomAudioDevice"),
        (3, "MacBook Pro Microphone")
    ]
    
    good_devices = []
    
    for device_id, device_name in test_devices:
        try:
            result = test_device(device_id, device_name)
            if result:
                good_devices.append((device_id, device_name))
                print(f"✅ {device_name} captures audio well!")
            else:
                print(f"❌ {device_name} captured little/no audio")
        except Exception as e:
            print(f"❌ Error testing {device_name}: {e}")
        
        print("\n" + "-" * 60)
    
    # Summary
    print("\n🎯 SUMMARY:")
    print("=" * 60)
    if good_devices:
        print("✅ Devices that capture audio well:")
        for device_id, device_name in good_devices:
            print(f"   • Device {device_id}: {device_name}")
        
        print(f"\n💡 RECOMMENDATION:")
        best_device = good_devices[0]
        print(f"   Use Device {best_device[0]}: {best_device[1]}")
        print(f"   This device should capture both mic and speakers!")
    else:
        print("❌ No devices captured audio well.")
        print("💡 You may need to configure audio routing in:")
        print("   • System Preferences → Sound")
        print("   • Audio MIDI Setup app")
        print("   • Or install/configure BlackHole properly")

if __name__ == "__main__":
    main()