#!/bin/bash

input_dir=$1
patterns=$2

# Ensure patterns are properly formatted for grep
if [ -z "$patterns" ]; then
    find "$input_dir" -type f | wc -l
else
    find "$input_dir" -type f | grep -iE "$(echo $patterns | sed 's/,/|/g')" | wc -l
fi