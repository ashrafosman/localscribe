#!/bin/bash

# Create whisper subfolder
mkdir -p whisper

# Copy the existing stream executable
cp /Users/ashraf.osman/Documents/Work/whisper.cpp/stream whisper/

echo "Stream executable copied to: $(pwd)/whisper/stream"
echo "Usage: ./whisper/stream -m /path/to/model.bin [options]"