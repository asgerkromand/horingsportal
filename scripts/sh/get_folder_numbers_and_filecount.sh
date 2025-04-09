#!/bin/zsh

# Check if the correct number of arguments is provided
if [[ $# -ne 2 ]]; then
    echo "Usage: $0 <input_directory> <output_file>"
    exit 1
fi

# Set input directory and output file from arguments
INPUT_DIR=$1
OUTPUT_FILE=$2

# Check if the input directory exists
if [[ ! -d "$INPUT_DIR" ]]; then
    echo "Error: Input directory '$INPUT_DIR' does not exist."
    exit 1
fi

# Initialize JSON output
echo "{" > "$OUTPUT_FILE"

# Loop through first-level subdirectories
first=true
for subdir in "$INPUT_DIR"/*; do
    if [[ -d "$subdir" ]]; then
        folder_name=$(basename "$subdir")  # Extract folder name

        # Collect file names in an array
        file_list=()
        for file in "$subdir"/*; do
            [[ -f "$file" ]] && file_list+=("\"$(basename "$file")\"")
        done

        # JSON formatting (avoid trailing comma)
        if $first; then
            first=false
        else
            echo "," >> "$OUTPUT_FILE"
        fi

        # Output folder name and list of files in JSON format
        echo "  \"$folder_name\": [$(IFS=,; echo "${file_list[*]}")]" >> "$OUTPUT_FILE"
    fi
done

# Close JSON file
echo "" >> "$OUTPUT_FILE"
echo "}" >> "$OUTPUT_FILE"

echo "File names saved to $OUTPUT_FILE"