#!/bin/bash

input_dir=$1
patterns=$2

# Ensure patterns are properly formatted for grep
if [ -z "$patterns" ]; then
    # If no patterns are provided, count all files by extension
    find "$input_dir" -type f | sed -E 's/.*\.([^.]+)$/\1/' | sort | uniq -c | awk '{print $2 ": " $1}'
else
    # If patterns are provided, count files matching the patterns by extension
    find "$input_dir" -type f | grep -iE "$(echo $patterns | sed 's/,/|/g')" | sed -E 's/.*\.([^.]+)$/\1/' | sort | uniq -c | awk '{print $2 ": " $1}'
fi