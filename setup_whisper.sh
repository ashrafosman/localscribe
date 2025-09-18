#!/bin/bash

# Create whisper subfolder
mkdir -p whisper

# Copy the existing stream executable from your built whisper.cpp
if [ -f "/Users/ashraf.osman/Documents/Work/whisper.cpp/stream" ]; then
    echo "Copying existing stream executable..."
    cp /Users/ashraf.osman/Documents/Work/whisper.cpp/stream whisper/
    echo "Stream executable copied to: $(pwd)/whisper/stream"
else
    echo "Stream executable not found. Building whisper-cli instead..."
    
    # Clone whisper.cpp if not exists
    if [ ! -d "whisper/whisper.cpp" ]; then
        echo "Cloning whisper.cpp..."
        git clone https://github.com/ggerganov/whisper.cpp.git whisper/whisper.cpp
    fi
    
    cd whisper/whisper.cpp
    
    # Build using CMake
    echo "Building whisper.cpp..."
    cmake -B build
    cmake --build build --config Release
    
    # Copy whisper-cli executable to parent whisper folder
    if [ -f "build/bin/whisper-cli" ]; then
        cp build/bin/whisper-cli ../whisper-cli
        echo "Whisper CLI executable created at: $(pwd)/../whisper-cli"
        echo "Usage: ./whisper/whisper-cli -m /path/to/model.bin [options]"
    else
        echo "Build failed or whisper-cli not found"
    fi
fi