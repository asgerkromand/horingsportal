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

def count_folders_with_matching_files(data_dir, patterns):
    """Counts the number of unique folders that contain files matching any of the patterns."""
    matching_folders = set()

    for root, _, files in os.walk(data_dir):
        if any(
            any(pattern.lower() in file.lower() for pattern in patterns)
            for file in files
        ):
            matching_folders.add(root)  # Add the folder if at least one file matches

    return len(matching_folders)


def convert_to_format(input_path, output_dir, output_format, patterns):
    """Convert different file types to the specified format (pdf, png, or jpg)."""
    case_name = input_path.parent.name

    try:
        ext = input_path.suffix.lower()

        if ext in [".doc", ".docx", ".rtf", ".txt", ".htm", ".mht"]:
            if output_format == "mht":
                logging.warning(
                    f"Skipping MHT conversion for {input_path} in folder ID: {case_name}"
                )
                return
            else:
                doc_to_pdf(input_path, output_dir)

        elif ext in [".ppt"]:
            pass # Not implemented

        elif ext in [".msg", ".oft"]:
            convert_msg_input(input_path, output_dir, output_format, patterns)

        elif ext in [".tif", ".jpg", ".jpeg", ".png"]:
            image_to_pdf(input_path, output_dir, output_format)

        elif ext in [".zip"]:
            zip_to_pdf(input_path, output_dir, output_format, patterns)

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

def zip_to_pdf(zip_path, output_dir, output_format, patterns):
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
                    convert_to_format(file_path, output_subfolder, output_format, patterns)

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

def main():
    parser = argparse.ArgumentParser(description="Convert files to pdf, png, or jpg.")
    parser.add_argument(
        "--input_dir", required=True, help="Path to the input data directory"
    )
    parser.add_argument(
        "--output_dir", required=True, help="Path to the output directory"
    )
    parser.add_argument(
        "--format",
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

    # Convert to Path objects
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    # Save the logging file in the output directory
    logging.basicConfig(
        filename=output_dir / "conversion_errors.log",
        level=logging.ERROR,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    # Check if the input directory exists
    if not os.path.exists(input_dir):
        print(f"Input directory '{input_dir}' not found. Exiting.")
        return

    # Make a subfolder called hearing_answer_to_{format} in the output directory
    output_format_dir = output_dir / f"hearing_answer_to_{args.format}"
    output_format_dir.mkdir(parents=True, exist_ok=True)

    # Count how many folders need to be processed
    num_folders_to_process = count_folders_with_matching_files(input_dir, patterns)

    # Display progress bar using tqdm
    with tqdm(
        total=num_folders_to_process, desc="Processing Folders", unit="folder"
    ) as pbar:
        for root, _, files in os.walk(input_dir):
            subfolder_has_valid_files = (
                False  # Track if a valid file exists in the subfolder
            )

            output_case_folder = output_format_dir / Path(root).name
            output_case_folder.mkdir(parents=True, exist_ok=True)

            for file in files:
                file_path, file = manual_fix_filename(Path(root) / file)
                if any(pattern.lower() in file.lower() for pattern in patterns):
                    output = output_case_folder / file
                    output.mkdir(parents=True, exist_ok=True)
                    print(output)
                    print(file)
                    convert_to_format(file_path, output, args.format, patterns)

                    if args.format != "pdf":
                        path_to_pdf = Path(output) / f"{file_path.stem}.pdf"
                        convert_pdf_to_images(path_to_pdf, args.format, output)

                    subfolder_has_valid_files = True

            # If no valid files were found, remove the empty output subfolder
            if not subfolder_has_valid_files:
                shutil.rmtree(output_case_folder)

            if subfolder_has_valid_files:
                pbar.update(
                    1
                )  # Update progress bar only if the folder had matching files

            # Clean unwanted files
            clean_unwanted_files(output_case_folder, args.format)


if __name__ == "__main__":
    main()
