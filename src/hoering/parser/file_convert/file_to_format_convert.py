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
import zipfile
import time
from itertools import islice
from charset_normalizer import from_path
import collections
import json
from hoering.parser.file_convert.resources.remove_files_rules import match_and_remove_files
import time
import concurrent.futures
import random
from typing import Optional
from datetime import datetime


# To do: 
#   Fix outtputted_files so that it can be used in the clean_unwanted_files function
#   Fix clean_unwanted_files


class FileConverter:
    def __init__(self, input_dir, output_dir, output_format, patterns, make_copy=False, copy_sample_size: Optional[int] = None):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_format = output_format
        self.patterns = patterns.split(",") if patterns else []
        self.file_extension_summary = {}

        # Set up logging
        self.setup_logging()

        # Validate directories
        self.validate_directories()

        # Optionally make a copy of the input directory
        if make_copy:
            self.input_dir = self.make_copy_input_dir(self.input_dir, sample_size=copy_sample_size)

        # Create output folder
        self.output_format_dir = self.create_output_folder()

    def setup_logging(self):
        """Setup the logging configuration."""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        log_dir = self.output_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        handler = logging.FileHandler(log_dir / f"conversion_errors_{time.strftime('%Y%m%d_%H%M%S')}.log")
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)

        self.logger.addHandler(handler)

    def validate_directories(self):
        """Check if input and output directories are valid."""
        if not self.input_dir.exists():
            self.logger.error(f"Input directory '{self.input_dir}' not found. Exiting.")
            raise SystemExit

        if self.input_dir == self.output_dir:
            self.logger.error("Output directory cannot be the same as the input directory. Exiting.")
            raise SystemExit

    def create_output_folder(self):
        """Create output folder for the selected format with a timestamp as a nested folder."""
        # Get current timestamp to make the subfolder unique
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create the main output folder (hearing_answer_to_{self.output_format}) if it doesn't exist
        main_output_dir = self.output_dir / f"hearing_answer_to_{self.output_format}"
        main_output_dir.mkdir(parents=True, exist_ok=True)

        # Create the nested folder with the timestamp inside the main output folder
        timestamped_folder = main_output_dir / timestamp
        timestamped_folder.mkdir(parents=True, exist_ok=True)
        
        return timestamped_folder

    def count_files_by_extension(self, pattern=None):
        """Counts files in a directory (including nested ones) and groups them by extension.
        Can filter based on filename substrings or count all files if pattern='all'."""

        try:
            if isinstance(pattern, list):
                pattern_string = "|".join(pattern)
            else: # Counts all files
                pattern_string = ""

            if not os.path.isdir(self.input_dir):
                self.logger.error(f"Invalid directory: {self.input_dir}")
                return {}

            bash_command = ["./resources/count_files.sh", str(self.input_dir), pattern_string]
            self.logger.info(f"Running bash command: {' '.join(bash_command)}")
            result = subprocess.run(bash_command, capture_output=True, text=True, check=True)

            if result.returncode != 0:
                self.logger.error(f"Error: {result.stderr}")
                return {}

            file_counts = collections.defaultdict(int)
            for line in result.stdout.strip().split("\n"):
                if line:  # Ensure non-empty line
                    ext, count = line.rsplit(":", 1)  # Expecting "ext: count" format
                    file_counts[ext.strip()] += int(count)

            total_count = sum(file_counts.values())
            print(f"Total files counted: {total_count} in {self.input_dir}")
            self.logger.info(f"Total files counted: {total_count} in {self.input_dir}")
            self.logger.info(f"Patterns used: {pattern if pattern else 'None'}")

            self.logger.info(f"File counts by extension: {dict(file_counts)}")
            return dict(file_counts)

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error running Bash script: {e}")
            return {}
        except ValueError as e:
            self.logger.error(f"Unexpected output from Bash script: {result.stdout}, Error: {e}")
            return {}
        
    def process_directory(self):
            """Process all files in the directory."""
            num_files_to_process = self.count_files_using_bash()
            print(num_files_to_process)

            with tqdm(total=num_files_to_process, desc="Processing Files", unit="file", dynamic_ncols=True, mininterval=0.5) as pbar:
                for root, _, files in islice(os.walk(self.input_dir), 100):
                    folder_name = Path(root).name
                    output_case_folder = self.output_format_dir / folder_name
                    output_case_folder.mkdir(parents=True, exist_ok=True)
                    outputted_files = []
                    print('\n',folder_name)

                    for file in files:
                        file_output = self.process_file(file, Path(root), output_case_folder, pbar)
                        if isinstance(file_output, list):
                            outputted_files.extend(file_output)
                        if isinstance(file_output, str):
                            outputted_files.append(file_output)

                    print(outputted_files)
                    self.clean_unwanted_files(outputted_files, output_case_folder)
                    self.remove_empty_folder(output_case_folder)
                    
    
    def process_file(self, file, input_root, output_case_folder, pbar):
        """Process each file."""
        new_file_name = self.manual_fix_filename(input_root, Path(file))
        new_file_name = Path(new_file_name)

        output_files = []
        if any(pattern.lower() in file.lower() for pattern in self.patterns):
            file_output = self.convert_to_format(new_file_name, input_root, output_case_folder)
            if isinstance(file_output, list):
                file_output = [file.name for file in file_output]
                output_files.extend(file_output)
            if isinstance(file_output, Path):
                output_files.append(file_output.name)

            if self.output_format != "pdf":
                path_to_pdf = Path(output_case_folder) / f"{new_file_name.stem}.pdf"
                if path_to_pdf.exists():
                    image_files = self.convert_pdf_to_images(path_to_pdf, self.output_format, output_case_folder)
                    output_files.extend(image_files)
                else:
                    self.logger.error(f"PDF file not found for converting to {self.output_format}: {path_to_pdf}")

            pbar.update(1)
        return output_files

    def convert_to_format(self, file_name: Path, input_root: Path, output_case_folder: Path):
        """Convert different file types to the specified format (pdf, png, or jpg)."""
        case_name = output_case_folder.name
        ext = file_name.suffix.lower()

        try:
            ext = file_name.suffix.lower()

            # Track the file before any conversion
            self.track_output_files(file_name)

            if ext in [".doc", ".docx", ".rtf", ".txt", ".htm", ".mht"]:
                if self.output_format == ".mht":
                    self.logger.warning(f"Skipping MHT conversion for {output_case_folder / file_name} in folder ID: {case_name}")
                    return
                else:
                    file = self.doc_to_pdf(file_name, input_root, output_case_folder)
                    return file

            elif ext in [".ppt"]:
                pass  # Not implemented

            elif ext in [".msg", ".oft"]:
                file_output = convert_msg_input(file_name, input_root, output_case_folder, self.output_format, self.patterns)
                return file_output

            elif ext in [".tif", ".jpg", ".jpeg", ".png"]:
                files = self.image_to_pdf(file_name, input_root, output_case_folder, self.output_format)
                return files

            elif ext in [".zip"]:
                files = self.zip_to_pdf(file_name, input_root, output_case_folder)
                return files

            elif ext in [".pdf"]:
                file_path = input_root / file_name
                shutil.copy(file_path, output_case_folder)
                return file_name


            elif ext in [".xls", ".xlsx"]:
                file = self.xls_to_pdf(file_name, input_root, output_case_folder)
                return file
                
            else:
                self.logger.warning(f"Skipping unknown format: {file_name} in folder ID: {case_name}")

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error converting {file_name} in folder ID: {case_name}: {e}")
        except FileNotFoundError:
            self.logger.error(f"File not found: {file_name} in folder ID: {case_name}")
        except Exception as e:
            self.logger.error(f"Unexpected error processing {file_name} in folder ID: {case_name}: {e}")

    def doc_to_pdf(self, file_name: Path, input_dir: Path, output_dir: Path):
        """Convert documents (.txt, .docx, .mht, etc.) to PDF."""
        # Special case: Convert .txt to UTF-8 before processing
        if file_name.suffix.lower() == ".txt":
            self.convert_txt_to_utf8(file_name, input_dir)
        return self.convert_doc_to_pdf(file_name, input_dir, output_dir)  # Convert to PDF

    def convert_txt_to_utf8(self, file_name: Path, input_dir: Path):
        """Ensure TXT file is properly UTF-8 encoded, rewriting if misencoded characters exist."""
        input_path = input_dir / file_name

        # Detect encoding first
        detected = from_path(input_path).best()
        if detected is None:
            self.logger.error(f"Encoding detection failed for {input_path}")
            return

        detected_encoding = detected.encoding

        try:
            with open(input_path, "r", encoding="utf-8") as f:
                content = f.read()
            if "�" in content:  # If there are misencoded characters, we need to fix them
                raise UnicodeDecodeError("utf-8", b"", 0, 1, "Found replacement characters")
        except UnicodeDecodeError:
            try:
                with open(input_path, "r", encoding=detected_encoding or "windows-1252") as f:
                    content = f.read()
            except Exception as e:
                self.logger.error(f"Failed to decode {input_path} using {detected_encoding}: {e}")
                return
            
        try:
            with open(input_path, "w", encoding="utf-8") as f:
                f.write(content)
            self.logger.info(f"Re-encoded {input_path} from {detected_encoding} to UTF-8")
        except Exception as e:
            self.logger.error(f"Failed to re-encode {input_path}: {e}")

    def convert_doc_to_pdf(self, file_name: Path, input_dir: Path, output_dir: Path):
        """Convert standard document formats (.txt, .doc, .docx, etc.) to PDF."""
        input_path = input_dir / file_name
        subprocess.run(
            [
                "soffice", "--headless", "--convert-to", "pdf",
                "--outdir", str(output_dir), str(input_path)
            ],
            check=True,
        )
        return f"{file_name.stem}.pdf"
    
    def image_to_pdf(self, file_name: Path, input_root: Path, output_case_folder: Path, output_format):
        """Convert an .tif, .jpg, .jpeg, .png to a PDF file."""
        images = [Image.open(input_root / file_name)]
        if output_format == "pdf":
            images[0].save(
                Path(output_case_folder) / f"{file_name}.pdf", "PDF", resolution=100.0, save_all=True
            )
        return f"{file_name.stem}.pdf"

    def xls_to_pdf(self, file_name, input_root, output_case_folder):
        """Convert a .xls, .xlsx to a PDF file."""
        input_path = input_root / file_name
        pdf_output = output_case_folder / f"{file_name.stem}.pdf"
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
        return f"{file_name}.pdf"

    def zip_to_pdf(self, file_name, input_root, output_case_folder):
        """Handle zip file extraction and conversion."""
        # Unzips the file and processes each file within the ZIP archive
        zip_path = input_root / file_name
        temp_extract_dir = output_case_folder / "temp_unzip"
        temp_extract_dir.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_extract_dir)

            output_files = []
            for root, _, files in os.walk(temp_extract_dir):
                for file in files:
                    if any(pattern.lower() in file.lower() for pattern in self.patterns):
                        file_output = self.convert_to_format(file, temp_extract_dir, output_case_folder)
                        output_files.append(file_output)

            shutil.rmtree(temp_extract_dir)  # Clean up
            return output_files
        except Exception as e:
            self.logger.error(f"Error processing zip file {zip_path}: {e}")

    def convert_pdf_to_images(self, pdf_path, image_format, output_case_folder):
        """Convert a PDF file to PNG or JPG images."""
        try:
            images = convert_from_path(pdf_path)
        except Exception as e:
            self.logger.error(f"Error converting PDF to images: {e}, file: {pdf_path}")
            return
        original_file_name = pdf_path.stem
        original_file_extension = pdf_path.suffix[1:]

        images_file_names = []
        for i, img in enumerate(images):
            img.save(
                Path(output_case_folder)
                / f"{original_file_name}_{original_file_extension}_{i}.{image_format}",
                image_format.upper(),
            )
            images_file_names.append(f"{original_file_name}_{original_file_extension}_{i}.{image_format}")
        return images_file_names

    def clean_unwanted_files(self, outputted_files, output_case_folder):
            """Clean unwanted files not matching the expected output files."""
            for root, _, files in os.walk(output_case_folder):
                for file in files:
                    if file not in outputted_files:
                        file_path = Path(root) / file
                        os.remove(file_path)
                        self.logger.info(f"Removed unwanted file: {file_path}")

    def track_output_files(self, file_path):
            """Track the output files and their original extensions."""
            original_extension = file_path.suffix.lower()

            if original_extension not in self.file_extension_summary:
                self.file_extension_summary[original_extension] = 0
            self.file_extension_summary[original_extension] += 1

    def remove_empty_folder(self, output_case_folder):
        """Remove empty folders after processing."""
        if not os.listdir(output_case_folder):
            os.rmdir(output_case_folder)
            self.logger.info(f"Removed empty folder: {output_case_folder}")

    def manual_fix_filename(self, file_input_dir: Path, file_name: Path) -> str:
        """Manually fix known corrupted characters in filenames."""
        file_stem, extension = file_name.stem, file_name.suffix.lower()
        fixed_file_stem = file_stem.replace("�", "oe").replace("H�ringssvar", "Hoeringssvar").lower()

        if fixed_file_stem != file_stem:
            old_file_name = file_name.name
            new_file_name = f'{fixed_file_stem}{extension}'
            old_file_path = file_input_dir / old_file_name
            new_file_path = file_input_dir / new_file_name
            if old_file_path.exists():
                os.rename(old_file_path, new_file_path)
            else:
                self.logger.error(f"File not found: {old_file_path}")
            return Path(new_file_name).name
    
        return Path(file_name).name

    def remove_standard_files(self, input_dir: Path):
        """Check if the file name contains standard file patterns."""
        file_remove_log_dir = self.output_dir / "remove_file_logs"
        match_and_remove_files(input_dir, file_remove_log_dir)

    def make_copy_input_dir(self, input_dir, sample_size: Optional[int] = None):
        """Create a copy of the input directory with live progress tracking using multithreading."""
        input_dir_copy = Path(self.input_dir).with_suffix(".copy")

        if input_dir_copy.exists():
            try:
                shutil.rmtree(input_dir_copy)
                self.logger.info(f"Existing copy directory {input_dir_copy} removed.")
            except Exception as e:
                self.logger.error(f"Failed to remove existing directory {input_dir_copy}: {e}")
                return None

        # Gather immediate subdirectories of the input directory
        subdirs = [d for d in Path(input_dir).iterdir() if d.is_dir()]
        if sample_size is not None and sample_size < len(subdirs):
            subdirs = random.sample(subdirs, sample_size)

        # Log the sampled directories
        self.logger.info(f"Sampled the following {len(subdirs)} subdirectories for copying:")
        for subdir in subdirs:
            self.logger.info(f"- {subdir}")

        total_files = sum(
            len(files)
            for subdir in subdirs
            for _, _, files in os.walk(subdir)
        )

        buffer_size = 1024 * 1024  # 1MB buffer size
        futures = []

        self.logger.info(f"Copying files from {input_dir} to {input_dir_copy}")

        with concurrent.futures.ThreadPoolExecutor() as executor, tqdm(
            total=total_files, desc="Copying files", unit="file", dynamic_ncols=True
        ) as pbar:

            for subdir in subdirs:
                for root, dirs, files in os.walk(subdir):
                    relative_root = Path(root).relative_to(input_dir)
                    new_root = input_dir_copy / relative_root
                    new_root.mkdir(parents=True, exist_ok=True)

                    for file in files:
                        src_file = Path(root) / file
                        dest_file = new_root / file
                        future = executor.submit(self.copy_file, src_file, dest_file, pbar, buffer_size)
                        futures.append(future)

            concurrent.futures.wait(futures)

        self.logger.info(f"Finished copying files to {input_dir_copy}")
        return input_dir_copy

    def copy_file(self, src_file, dest_file, pbar, buffer_size):
        """Helper function to copy a file with buffering and progress update."""
        MAX_RETRIES = 5
        RETRY_DELAYS = [3, 5, 10, 20, 30]  # Differentiated delays between retries (in seconds)
        retries = 0
        while retries < MAX_RETRIES:
            try:
                with open(src_file, 'rb') as src, open(dest_file, 'wb') as dest:
                    shutil.copyfileobj(src, dest, buffer_size)
                pbar.update(1)
                return
            except Exception as e:
                retries += 1
                self.logger.error(f"Error copying {src_file} to {dest_file}. Attempt {retries}/{MAX_RETRIES}. Error: {e}")
                if retries < MAX_RETRIES:
                    self.logger.info(f"Retrying in {RETRY_DELAYS[retries - 1]} seconds...")
                    time.sleep(RETRY_DELAYS[retries - 1])
                else:
                    self.logger.error(f"Failed to copy {src_file} after {MAX_RETRIES} attempts. Skipping.")
                    return
    
    def run(self):
        """Start the conversion process."""
        # Count total number of files (not including folders)
        total_file_count = self.count_files_by_extension(self.patterns)
        # Save the file count to a json file
        with open(self.output_dir / "file_count.json", "w") as f:
            json.dump(total_file_count, f, indent=4)
        
        # Step 1 - Remove files that are not høringssvar for sure
        self.remove_standard_files(self.input_dir)

        # Step 2 - Parse høringssvar files known to be valid
        self.logger.info(f"Starting conversion process for files in {self.input_dir}")
        self.logger.info(f"Output directory: {self.output_format_dir}")
        self.logger.info(f"Output format: {self.output_format}")
        self.logger.info(f"Patterns used: {self.patterns}")
        self.logger.info(f"Total files to process: {total_file_count}")
        remaining_file_count = self.count_files_by_extension(self.patterns)


        # Count how many files left in the directory

        #self.process_directory()

def main():
    parser = argparse.ArgumentParser(description="Convert files to pdf, png, or jpg.")
    parser.add_argument("--input_dir", "-i", required=True, help="Path to the input data directory")
    parser.add_argument("--output_dir", "-o", required=True, help="Path to the output directory")
    parser.add_argument("--make_copy_of_input", "-make_copy", action='store_true', help="Make a copy of the input directory")
    parser.add_argument("--copy_sample_size", type=int, help="Number of subdirectories to sample when copying", default=None)
    parser.add_argument("--format", "-f", choices=["pdf", "png", "jpg"], help="Output format: pdf, png, or jpg", default="pdf")
    parser.add_argument("--patterns", help="Comma-separated list of filename patterns to match (e.g., 'ringssvar,ringsvar,svar')", default="")

    args = parser.parse_args()
    input_dir  = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    converter = FileConverter(input_dir, output_dir, args.format, args.patterns, make_copy=args.make_copy_of_input, copy_sample_size=args.copy_sample_size)
    print(converter.input_dir)
    converter.run()

if __name__ == "__main__":
    main()
