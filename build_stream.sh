#!/bin/bash

# Create whisper subfolder
mkdir -p whisper

# Clone or copy whisper.cpp source
if [ ! -d "whisper/whisper.cpp" ]; then
    echo "Cloning whisper.cpp..."
    git clone https://github.com/ggerganov/whisper.cpp.git whisper/whisper.cpp
fi

cd whisper/whisper.cpp

# Build using CMake
echo "Building whisper.cpp..."
cmake -B build
cmake --build build --config Release

# Copy stream executable to parent whisper folder  
cp build/bin/stream ../stream 2>/dev/null || cp build/stream ../stream 2>/dev/null || echo "Stream executable not found in expected locations"

echo "Stream executable created at: $(pwd)/../stream"
echo "Usage: ./whisper/stream -m /path/to/model.bin [options]"