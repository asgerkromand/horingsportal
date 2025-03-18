#!/bin/zsh

count_file_extensions() {
    local folder="${1:-.}"  # Default to current directory if not specified
    local keywords=("${@:2}")  # Capture keywords passed as arguments
    local timestamp=$(date +"%Y-%m-%d_%H-%M-%S")
    OUTPUT_DIR="/Users/asgerkromand/Library/CloudStorage/OneDrive-UniversityofCopenhagen/2. SODAS/5 horingsportal/data/constructed/count_file_ext"
    
    # Create output directory
    echo "Creating output directory: $OUTPUT_DIR"
    mkdir -p "$OUTPUT_DIR"  # Ensure the folder exists

    # Generate output file name based on keywords
    OUTPUT_FILE="$OUTPUT_DIR/file_distribution_${timestamp}.txt"
    echo "Output file: $OUTPUT_FILE"

    echo "Function: count_file_extensions" > "$OUTPUT_FILE"
    echo "Date: $(date)" >> "$OUTPUT_FILE"
    echo "Directory: $folder" >> "$OUTPUT_FILE"
    if [ ${#keywords[@]} -gt 0 ]; then
        echo "Keywords: ${keywords[*]}" >> "$OUTPUT_FILE"
    fi
    echo "-------------------------" >> "$OUTPUT_FILE"
    echo "Extension,Count" >> "$OUTPUT_FILE"

    # Count file extensions
    echo "Running find command on: $folder"
    
    # Progress bar for case folders
    total_cases=$(find "$folder" -mindepth 1 -maxdepth 1 -type d | wc -l)
    count=0

    # Declare associative array to store extension counts in zsh
    typeset -A ext_count

    find "$folder" -mindepth 1 -maxdepth 1 -type d | while read -r case_folder; do
        # Extract case number from folder name
        case_number=$(basename "$case_folder")
        case_number_filtered=$(echo "$case_number" | tr -cd '[:alnum:]')

        # Filter out unwanted files based on keywords
        find "$case_folder" -type f | while read -r file; do
            filename=$(basename "$file")
            ext="${filename##*.}"

            # Skip files that match the case number or contain excluded extensions
            exclude=0
            if [[ "$filename" =~ "$case_number_filtered" ]]; then
                exclude=1
            fi
            if [ $exclude -eq 1 ]; then
                continue
            fi

            # Apply keyword filter if keywords are provided
            if [ ${#keywords[@]} -gt 0 ]; then
                keyword_match=0
                for keyword in "${keywords[@]}"; do
                    if [[ "$filename" == *"$keyword"* ]]; then
                        keyword_match=1
                        break
                    fi
                done
                if [ $keyword_match -eq 0 ]; then
                    continue
                fi
            fi

            # Count extensions
            if [[ "$ext" != "$filename" && "$ext" != "" ]]; then
                # Handle special characters in extension names safely
                (( ext_count["$ext"]++ ))
            fi
        done

        # Update progress bar
        count=$((count + 1))
        progress=$((100 * count / total_cases))
        echo -ne "Processing case folder: $case_number [$progress%]\r"
    done

    echo -ne "\n"  # Move to the next line after progress bar

    # Sort the extensions by count in descending order and output the results to the output file
    for ext in $(for ext in ${(k)ext_count}; do echo "$ext,${ext_count[$ext]}"; done | sort -t',' -k2,2nr); do
        echo "$ext" >> "$OUTPUT_FILE"
    done

    echo "Results saved to $OUTPUT_FILE"
}

# Run the function when the script is executed
count_file_extensions "$@"