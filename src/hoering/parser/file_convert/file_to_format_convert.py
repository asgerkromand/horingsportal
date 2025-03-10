import os
import subprocess
import logging
from pathlib import Path
from pdf2image import convert_from_path
from PIL import Image
import shutil
import argparse
from tqdm import tqdm  # For progress bar
from hoering.parser.file_convert.resources.msg_conversion import convert_msg_input

# PROBLEMS
# When saving to .png the files are not placed in the subfolder
# Problems with saving to jpg. An error occurs..


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

        # Skip files that don't match the patterns
        if not any(pattern.lower() in input_path.name.lower() for pattern in patterns):
            return

        # Preserve original file-domain in output filename
        original_file_name = normalize_special_characters(input_path.stem)
        original_file_extension = ext[1:]

        if ext in [
            ".doc",
            ".docx",
            ".rtf",
            ".txt",
            ".htm",
            ".html",
            ".mht",
            ".xlsx",
            ".xls",
        ]:
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
            if output_format in ["png", "jpg"]:
                convert_pdf_to_images(pdf_output, output_format, output_dir)

        elif ext in [".msg", ".oft"]:
            convert_msg_input(input_path, output_dir, output_format, patterns)

        elif ext in [".tif", ".tiff", ".jpg", ".jpeg", ".png"]:
            images = (
                convert_from_path(str(input_path))
                if ext in [".tif", ".tiff"]
                else [Image.open(input_path)]
            )
            if output_format == "pdf":
                images[0].save(
                    output_dir, save_all=True, append_images=images[1:]
                )
            else:
                for i, img in enumerate(images):
                    img.save(
                        Path(output_dir)
                        / f"{original_file_name}_{original_file_extension}_{i}.{output_format}",
                        output_format.upper(),
                    )

        elif ext in [".zip"]:
            unzip_path = Path(output_dir) / input_path.stem
            shutil.unpack_archive(str(input_path), unzip_path)
            for file in Path(unzip_path).rglob("*"):
                convert_to_format(file, output_format, output_dir, patterns)

        elif ext in [".pdf"]:
            shutil.copy(input_path, output_dir)
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

def normalize_special_characters(filename):
    """Normalize specific special characters in filenames."""
    # Replace occurrences of 'h�' or 'H�' with 'hø' or 'Hø'
    normalized_filename = filename.replace("h�", "hoe").replace("H�", "Hoe")
    return normalized_filename

def clean_unwanted_files(output_case_folder, output_format):
    for root, _, files in os.walk(output_case_folder):
        for file in files:
            if not file.lower().endswith(f".{output_format}"):
                os.remove(Path(root) / file)

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
        help="Comma-separated list of filename patterns to match (e.g., 'ringssvar,ringsvar')",
        default="ringssvar,ringsvar",
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

    if num_folders_to_process == 0:
        print("No matching files found. Exiting.")
        return

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
                if any(pattern.lower() in file.lower() for pattern in patterns):
                    norm_filename = normalize_special_characters(file)
                    file_path = Path(root) / file # shouldn't be normalised as it is the input file
                    # Create a subfolder for each file inside the case folder (due to some file formats encompassing multiple files (e.g. msg))
                    output = output_case_folder / norm_filename
                    output.mkdir(parents=True, exist_ok=True)
                    convert_to_format(file_path, output, args.format, patterns)
                    if args.format != "pdf":
                        print('her')
                        path_to_pdf = Path(output) / f"{file_path.stem}.pdf"
                        convert_pdf_to_images(path_to_pdf, args.format, output)
                    
                    subfolder_has_valid_files = True

            ## If no valid files were found, remove the empty output subfolder
            # relative_subfolder = Path(root).relative_to(args.input_dir)
            # output_subfolder = Path(args.output_dir) / relative_subfolder
            # if not subfolder_has_valid_files and output_subfolder.exists():
            #    shutil.rmtree(output_subfolder)  # Remove empty output folder

            if subfolder_has_valid_files:
                pbar.update(
                    1
                )  # Update progress bar only if the folder had matching files

            

            # Clean unwanted files
            clean_unwanted_files(output_case_folder, args.format)


    print(
        f"Conversion to {args.format} completed. Check 'conversion_errors.log' for issues."
    )


if __name__ == "__main__":
    main()
