import os
import subprocess
import logging
from pathlib import Path
from pdf2image import convert_from_path
from PIL import Image
import shutil
import argparse
from tqdm import tqdm  # For progress bar

# Setup logging
logging.basicConfig(
    filename="conversion_errors.log",
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def count_folders_with_matching_files(data_dir, patterns):
    """Counts the number of unique folders that contain files matching any of the patterns."""
    matching_folders = set()

    for root, _, files in os.walk(data_dir):
        if any(any(pattern.lower() in file.lower() for pattern in patterns) for file in files):
            matching_folders.add(root)  # Add the folder if at least one file matches

    return len(matching_folders)

def convert_to_format(input_path, output_format, output_dir, data_dir, patterns):
    """Convert different file types to the specified format (pdf, png, or jpg)."""
    try:
        input_path = Path(input_path)
        ext = input_path.suffix.lower()

        # Skip files that don't match the patterns
        if not any(pattern.lower() in input_path.name.lower() for pattern in patterns):
            return

        # Calculate relative path to maintain folder structure
        relative_path = input_path.relative_to(data_dir)
        folder_id = relative_path.parts[0]  # Extract folder ID

        # Create output file path, preserving directory structure
        output_file = Path(output_dir) / relative_path.with_suffix(f".{output_format}")
        output_file.parent.mkdir(parents=True, exist_ok=True)

        if output_file.exists():
            logging.info(f"Skipping {input_path}, already converted.")
            return

        # Preserve original file-domain in output filename
        original_file_name = input_path.stem
        original_file_extension = ext[1:]

        if ext in ['.doc', '.docx', '.rtf', '.txt', '.htm', '.html', '.mht', '.xlsx', '.xls']:
            pdf_output = output_file.with_suffix(".pdf")
            subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(pdf_output.parent), str(input_path)], check=True)
            if output_format in ['png', 'jpg']:
                convert_pdf_to_images(pdf_output, output_format, output_dir)

        elif ext in ['.msg', '.oft']:
            converted = output_file.with_suffix(".eml")
            subprocess.run(["msgconvert", "--outfile", str(converted), str(input_path)], check=True)
            subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(pdf_output.parent), str(converted)], check=True)
            if output_format in ['png', 'jpg']:
                convert_pdf_to_images(pdf_output, output_format, output_dir)

        elif ext in ['.tif', '.tiff', '.jpg', '.jpeg', '.png']:
            images = convert_from_path(str(input_path)) if ext in ['.tif', '.tiff'] else [Image.open(input_path)]
            if output_format == 'pdf':
                images[0].save(output_file, save_all=True, append_images=images[1:])
            else:
                for i, img in enumerate(images):
                    img.save(Path(output_dir) / f"{original_file_name}_{original_file_extension}_{i}.{output_format}", output_format.upper())

        elif ext in ['.zip']:
            unzip_path = Path(output_dir) / relative_path.stem
            shutil.unpack_archive(str(input_path), unzip_path)
            for file in Path(unzip_path).rglob('*'):
                convert_to_format(file, output_format, output_dir, data_dir, patterns)

        elif ext in ['.pdf']:
            if output_format == 'pdf':
                shutil.copy(input_path, output_dir / relative_path)
            else:
                convert_pdf_to_images(input_path, output_format, output_dir)
        else:
            logging.warning(f"Skipping unknown format: {input_path} in folder ID: {folder_id}")

    except subprocess.CalledProcessError as e:
        logging.error(f"Error converting {input_path} in folder ID: {folder_id}: {e}")
    except FileNotFoundError:
        logging.error(f"File not found: {input_path} in folder ID: {folder_id}")
    except Exception as e:
        logging.error(f"Unexpected error processing {input_path} in folder ID: {folder_id}: {e}")

def convert_pdf_to_images(pdf_path, image_format, output_dir):
    """Convert a PDF file to PNG or JPG images."""
    images = convert_from_path(str(pdf_path))
    original_file_name = pdf_path.stem
    original_file_extension = pdf_path.suffix[1:]

    for i, img in enumerate(images):
        img.save(Path(output_dir) / f"{original_file_name}_{original_file_extension}_{i}.{image_format}", image_format.upper())

def main():
    parser = argparse.ArgumentParser(description="Convert files to pdf, png, or jpg.")
    parser.add_argument("--format", choices=['pdf', 'png', 'jpg'], required=True, help="Output format: pdf, png, or jpg")
    parser.add_argument("--data_dir", required=True, help="Path to the input data directory")
    parser.add_argument("--output_dir", required=True, help="Path to the output directory")
    parser.add_argument("--patterns", required=True, help="Comma-separated list of filename patterns to match (e.g., 'ringssvar,ringsvar')")
    
    args = parser.parse_args()
    patterns = args.patterns.split(",")  # Convert pattern string to list

    Path(args.output_dir).mkdir(exist_ok=True)

    # Count how many folders need to be processed
    num_folders_to_process = count_folders_with_matching_files(args.data_dir, patterns)

    if num_folders_to_process == 0:
        print("No matching files found. Exiting.")
        return

    # Display progress bar using tqdm
    with tqdm(total=num_folders_to_process, desc="Processing Folders", unit="folder") as pbar:
        for root, _, files in os.walk(args.data_dir):
            subfolder_has_valid_files = False  # Track if a valid file exists in the subfolder
            for file in files:
                file_path = Path(root) / file
                if any(pattern.lower() in file.lower() for pattern in patterns):
                    convert_to_format(file_path, args.format, args.output_dir, args.data_dir, patterns)
                    subfolder_has_valid_files = True

            # If no valid files were found, remove the empty output subfolder
            relative_subfolder = Path(root).relative_to(args.data_dir)
            output_subfolder = Path(args.output_dir) / relative_subfolder
            if not subfolder_has_valid_files and output_subfolder.exists():
                shutil.rmtree(output_subfolder)  # Remove empty output folder
            
            if subfolder_has_valid_files:
                pbar.update(1)  # Update progress bar only if the folder had matching files

    print(f"Conversion to {args.format} completed. Check 'conversion_errors.log' for issues.")

if __name__ == "__main__":
    main()