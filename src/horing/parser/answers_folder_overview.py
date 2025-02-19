import os
import json

def find_and_save_matches(directory, patterns, output_file):
    """
    Finds files matching the given patterns, organizes them by folder, 
    and saves the result as a JSONL file.
    
    Args:
        directory (str): The root directory to search in.
        patterns (list of str): A list of string patterns to match filenames.
        output_file (str): Path to the output JSONL file.
    """
    matches = {}

    # Walk through the directory
    for root, _, files in os.walk(directory):
        for file in files:
            if any(pattern.lower() in file.lower() for pattern in patterns):
                folder_name = os.path.basename(root)
                if folder_name not in matches:
                    matches[folder_name] = []
                matches[folder_name].append(file)
    
    # Save the results to a JSONL file
    with open(output_file, "w") as f:
        for folder, files in matches.items():
            json_line = {"folder": folder, "files": files}
            f.write(json.dumps(json_line) + "\n")

    print(f"Results saved to {output_file}")

def parse_args():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--directory", type=str, default=".", help="Root directory to search"
    )
    parser.add_argument(
        "--patterns",
        nargs="+",
        type=str,
        help="File name patterns",
    )
    parser.add_argument(
        "--output_file",
        type=str,
        default="folder_matches.jsonl",
        help="Output JSONL file",
    )
    return parser.parse_args()

if __name__ == "__main__":
    # Set arguments
    args = parse_args()
    directory = args.directory
    patterns = args.patterns
    output_file = args.output_file

    # Find and save matches
    find_and_save_matches(directory, patterns, output_file)

    # Example command line usage:
    # python answers_folder_overview.py --directory /path/to/directory --patterns pattern1 pattern2 --output_file output.jsonl

