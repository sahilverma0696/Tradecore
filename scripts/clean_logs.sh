#!/bin/bash

echo "Starting comprehensive log and Excel file cleanup..."

# Absolute path of the reports directory to exclude
EXCLUDE_DIR="$(realpath ./reports)"

# Clean .log files everywhere
find . -type f -name "*.log" -print -delete

# Clean .xlsx files EXCEPT in ./reports
find . -type f -name "*.xlsx" | while read -r file; do
    FILE_PATH="$(realpath "$file")"
    if [[ "$FILE_PATH" != "$EXCLUDE_DIR"* ]]; then
        echo "Deleting $FILE_PATH"
        rm "$file"
    else
        echo "Skipping $FILE_PATH"
    fi
done

# Remove empty directories (except ./reports and its subdirs)
find . -type d -empty | while read -r dir; do
    DIR_PATH="$(realpath "$dir")"
    if [[ "$DIR_PATH" != "$EXCLUDE_DIR"* ]]; then
        echo "Removing empty directory $DIR_PATH"
        rmdir "$dir"
    fi
done

echo "Cleanup complete."

# Clear the terminal screen
clear
