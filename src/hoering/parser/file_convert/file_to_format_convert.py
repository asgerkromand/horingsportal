import os
import subprocess
import logging
from pathlib import Path
from pdf2image import convert_from_path
from PIL import Image
import shutil
import argparse
from tqdm import tqdm  # For progress bar
from hoering.parser.file_convert.resources.msg_oft_conversion import convert_msg_input
from bs4 import BeautifulSoup
import unicodedata
import ftfy  # Install with: pip install ftfy
import zipfile
import json

def load_progress(progress_file):
    """Load the progress of processed folders and files."""
    progress = {}
    if progress_file.exists():
        with open(progress_file, 'r') as f:
            for line in f:
                data = json.loads(line.strip())
                progress[data['folder']] = data['files']
    return progress

def save_progress(progress_file, progress):
    """Save the progress of processed folders and files."""
    with open(progress_file, 'a') as f:  # 'a' mode to append to the file
        for folder, files in progress.items():
            f.write(json.dumps({'folder': folder, 'files': files}) + '\n')

def count_files_using_bash(input_dir, patterns):
    """Call the external Bash script to count files that match certain patterns."""
    try:
        # Convert the patterns list into a single string, joined by "|"
        pattern_string = "|".join(patterns)  

        # Call the Bash script with input directory and pattern string
        bash_command = ["./resources/count_files.sh", str(input_dir), pattern_string]

        result = subprocess.run(
            bash_command, capture_output=True, text=True, check=True
        )

        num_files = int(result.stdout.strip())  # Convert result to integer
        logging.info(f"Found {num_files} matching files.")
        return num_files

    except subprocess.CalledProcessError as e:
        logging.error(f"Error running Bash script: {e}")
        return 0


def convert_to_format(input_path, output_dir, output_format, patterns, file_extension_count):
    """Convert different file types to the specified format (pdf, png, or jpg)."""
    case_name = input_path.parent.name

    try:
        ext = input_path.suffix.lower()

        # Track the file before any conversion
        track_output_files(input_path, file_extension_count)

        if ext in [".doc", ".docx", ".rtf", ".txt", ".htm", ".mht"]:
            if output_format == "mht":
                logging.warning(
                    f"Skipping MHT conversion for {input_path} in folder ID: {case_name}"
                )
                return
            else:
                doc_to_pdf(input_path, output_dir)

        elif ext in [".ppt"]:
            pass  # Not implemented

        elif ext in [".msg", ".oft"]:
            convert_msg_input(input_path, output_dir, output_format, patterns)

        elif ext in [".tif", ".jpg", ".jpeg", ".png"]:
            image_to_pdf(input_path, output_dir, output_format)

        elif ext in [".zip"]:
            zip_to_pdf(input_path, output_dir, output_format, patterns, file_extension_count)

        elif ext in [".pdf"]:
            shutil.copy(input_path, output_dir)

        elif ext in [".xls", ".xlsx"]:
            xls_to_pdf(input_path, output_dir)

        else:
            logging.warning(
                f"Skipping unknown format: {input_path} in folder ID: {case_name}"
            )

    except subprocess.CalledProcessError as e:
        logging.error(f"Error converting {input_path} in folder ID: {case_name}: {e}")
    except FileNotFoundError:
        logging.error(f"File not found: {input_path} in folder ID: {case_name}")
    except Exception as e:
        logging.error(
            f"Unexpected error processing {input_path} in folder ID: {case_name}: {e}"
        )

def zip_to_pdf(zip_path, output_dir, output_format, patterns, file_extension_count):
    """Handle zip file extraction and conversion."""

    # Create a temporary folder to unzip the contents of the zip file
    temp_extract_dir = output_dir / "temp_unzip"
    temp_extract_dir.mkdir(parents=True, exist_ok=True)

    # Create a new output directory
    new_output_dir = output_dir.parent

    try:
        # Unzip the contents to the temporary directory
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_extract_dir)
        
        # Walk through the unzipped contents (including subfolders)
        for root, _, files in os.walk(temp_extract_dir):
            for file in files:
                file_path = Path(root) / file
                
                # Check if the file matches the patterns
                if any(pattern.lower() in file.lower() for pattern in patterns):
                    # Create a subfolder in the output directory with the file's name (NOT the ZIP's name)
                    output_subfolder = new_output_dir / file_path.stem
                    output_subfolder.mkdir(parents=True, exist_ok=True)
                    
                    # Convert the file to the desired format
                    convert_to_format(file_path, output_subfolder, output_format, patterns, file_extension_count)

        # Remove the temporary directory
        shutil.rmtree(temp_extract_dir.parent)
        
    except Exception as e:
        logging.error(f"Error processing zip file {zip_path}: {e}")

def image_to_pdf(input_path, output_dir, output_format):
    """Convert an .tif, .jpg,. .jpeg, .png to a PDF file."""
    images = [Image.open(input_path)]
    if output_format == "pdf":
        images[0].save(
            Path(output_dir) / f"{input_path.stem}.pdf", "PDF", resolution=100.0, save_all=True
        )
    elif output_format in ["png", "jpg"]:
        for i, img in enumerate(images):
            img.save(
                Path(output_dir)
                / f"{input_path.stem}_{input_path.suffix[1:]}_{i}.{output_format}",
                output_format.upper(),
            )

def convert_txt_to_utf8(input_path):
    """Ensure TXT file is UTF-8 encoded to prevent character loss."""
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            content = f.read()
        with open(input_path, "w", encoding="utf-8") as f:
            f.write(content)
    except UnicodeDecodeError:
        with open(input_path, "r", encoding="windows-1252") as f:
            content = f.read()
        with open(input_path, "w", encoding="utf-8") as f:
            f.write(content)

def convert_doc_to_pdf(input_path, output_dir):
    """Convert standard document formats (.txt, .doc, .docx, etc.) to PDF."""
    subprocess.run(
        [
            "soffice", "--headless", "--convert-to", "pdf",
            "--outdir", str(output_dir), str(input_path)
        ],
        check=True,
    )
    return Path(output_dir) / f"{input_path.stem}.pdf"

def doc_to_pdf(input_path, output_dir):
    """Convert documents (.txt, .docx, .mht, etc.) to PDF."""
    input_path, output_dir = Path(input_path), Path(output_dir)

    # File handlers mapped by extension
    conversion_map = {
        #".mht": convert_mht_to_pdf, # Not implemented
        ".txt": lambda p, o: (convert_txt_to_utf8(p), convert_doc_to_pdf(p, o))[1],  # Ensure UTF-8 first
    }

    convert_function = conversion_map.get(input_path.suffix.lower(), convert_doc_to_pdf)
    pdf_output = convert_function(input_path, output_dir)

    return pdf_output

def xls_to_pdf(input_path, output_dir):
    """Convert a .xls, .xlsx to a PDF file."""
    pdf_output = output_dir.with_suffix(".pdf")
    subprocess.run(
        [
            "soffice",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(pdf_output.parent),
            str(input_path),
        ],
        check=True,
    )


def convert_pdf_to_images(pdf_path, image_format, output_dir):
    """Convert a PDF file to PNG or JPG images."""
    images = convert_from_path(pdf_path)
    original_file_name = pdf_path.stem
    original_file_extension = pdf_path.suffix[1:]

    for i, img in enumerate(images):
        img.save(
            Path(output_dir)
            / f"{original_file_name}_{original_file_extension}_{i}.{image_format}",
            image_format.upper(),
        )

def clean_unwanted_files(output_case_folder, output_format):
    for root, _, files in os.walk(output_case_folder):
        for file in files:
            if not file.lower().endswith(f".{output_format}"):
                os.remove(Path(root) / file)

def manual_fix_filename(filepath):
    """Manually fix known corrupted characters in filenames."""
    filename = filepath.name
    fixed_filename = filename.replace("�", "oe").replace("H�ringssvar", "Hoeringssvar")
    
    if fixed_filename != filename:
        new_path = filepath.parent / fixed_filename
        os.rename(filepath, new_path)
        new_filename = new_path.name
        return new_path, new_filename
    return filepath, filename

def track_output_files(file_path, file_extension_count):
    """Track the output files and their original extensions."""
    original_extension = file_path.suffix.lower()
    
    # Increment the counter for this extension type
    if original_extension not in file_extension_count:
        file_extension_count[original_extension] = 0
    file_extension_count[original_extension] += 1

def main():
    parser = argparse.ArgumentParser(description="Convert files to pdf, png, or jpg.")
    parser.add_argument(
        "--input_dir", "-i", required=True, help="Path to the input data directory"
    )
    parser.add_argument(
        "--output_dir", "-o", required=True, help="Path to the output directory"
    )
    parser.add_argument(
        "--format", '-f',
        choices=["pdf", "png", "jpg"],
        help="Output format: pdf, png, or jpg",
        default="pdf",
    )
    parser.add_argument(
        "--patterns",
        help="Comma-separated list of filename patterns to match (e.g., 'ringssvar,ringsvar,svar')",
        default="ingssvar,ingsvar,svar",
    )

    args = parser.parse_args()
    patterns = args.patterns.split(",")  # Convert pattern string to list

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    # Save the logging file for errors in the output directory
    logging.basicConfig(
        filename=output_dir / "logs" /"conversion_errors.log",
        level=logging.ERROR,  # Log errors during the conversion process
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    # Initialize the file extension count dictionary
    file_extension_count = {}

    # Check if the input directory exists
    if not os.path.exists(input_dir):
        print(f"Input directory '{input_dir}' not found. Exiting.")
        return

    # Check if the output directory is the same as the input directory
    if input_dir == output_dir:
        print("Output directory cannot be the same as the input directory. Exiting.")
        raise SystemExit

    # Make a subfolder called hearing_answer_to_{format} in the output directory
    output_format_dir = output_dir / f"hearing_answer_to_{args.format}"
    output_format_dir.mkdir(parents=True, exist_ok=True)

    # Count how many files need to be processed using Bash
    num_files_to_process = count_files_using_bash(input_dir, patterns)
    print(f"Total files to process: {num_files_to_process}")  # Debugging line to ensure the count is correct

    # Modify the progress file path to be inside the 'hearing_answer_to_{format}' folder
    progress_file = output_format_dir / "processing_progress.jsonl"

    # Load the progress file (if it exists)
    progress = load_progress(progress_file)

    # Display progress bar using tqdm
    with tqdm(
        total=num_files_to_process, desc="Processing Files", unit="file", dynamic_ncols=True, mininterval=0.5
    ) as pbar:
        for root, _, files in os.walk(input_dir):
            folder_name = Path(root).name
            output_case_folder = output_format_dir / folder_name
            output_case_folder.mkdir(parents=True, exist_ok=True)

            # Skip folder if already processed
            if folder_name in progress:
                already_processed_files = progress[folder_name]
            else:
                already_processed_files = []

            folder_has_matching_files = False

            for file in files:
                if file in already_processed_files:
                    continue  # Skip already processed files

                file_path, file = manual_fix_filename(Path(root) / file)
                if any(pattern.lower() in file.lower() for pattern in patterns):
                    output = output_case_folder / file
                    convert_to_format(file_path, output, args.format, patterns, file_extension_count)

                    if args.format != "pdf":
                        path_to_pdf = Path(output) / f"{file_path.stem}.pdf"
                        convert_pdf_to_images(path_to_pdf, args.format, output)

                    # Mark file as processed
                    already_processed_files.append(file)
                    pbar.update(1)
                    folder_has_matching_files = True

            # Update progress for this folder
            if folder_has_matching_files:
                progress[folder_name] = already_processed_files

                # Save progress after processing the folder
                save_progress(progress_file, progress)

            # If no valid files were found in the folder, remove the empty output subfolder
            if not folder_has_matching_files:
                shutil.rmtree(output_case_folder)

            # Clean unwanted files after processing files
            clean_unwanted_files(output_case_folder, args.format)

    # Final log of the file extension count
    final_log_path = output_dir / "file_extension_summary.log"
    with open(final_log_path, "w") as f:
        f.write("Final file extension counts:\n")
        for ext, count in file_extension_count.items():
            f.write(f"{ext}: {count}\n")

    # Optionally print to console
    print("Final file extension count summary has been saved to:", final_log_path)
    logging.info("File extension count summary logged successfully.")

if __name__ == "__main__":
    main()
