#!/bin/bash

# LocalScribe Startup Script

# Prompt the user for a filename
echo "Please enter the name of the file (without extension):"
read filename_base

# Check if the filename is not empty
if [ -z "$filename_base" ]; then
    echo "Error: Filename cannot be empty."
    exit 1
fi



cd /Users/ashraf.osman/Documents/Work/Dev/meeting/LocalScribe

echo "Starting LocalScribe..." 

python record_cli.py  --quick -n "$filename_base"