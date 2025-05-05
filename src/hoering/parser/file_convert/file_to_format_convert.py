import os
import subprocess
from pathlib import Path
from pdf2image import convert_from_path
from PIL import Image
import shutil
import argparse
from tqdm import tqdm  # For progress bar
import zipfile
import time
from itertools import islice
from charset_normalizer import from_path
import collections
import json
import concurrent.futures
import random
from typing import Optional
from datetime import datetime
import threading
import logging

from hoering.parser.file_convert.resources.msg_oft_conversion import convert_msg_input
from hoering.parser.file_convert.resources.remove_files_rules import match_and_remove_files
from models.vl_openai import ImageClassifier

#Todo Todo Todo:
#   Fix pbars, so that they make sense.

class FileConverter:
    def __init__(self, input_dir, output_dir, output_format, patterns, make_copy=False, copy_sample_size: Optional[int] = None):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_format = output_format
        self.patterns = patterns.split(",") if patterns else []
        self.file_extension_summary = {}
        self.keep_thinking = True

        # Create output folder
        self.output_format_dir = self.create_output_folder()

        # Set up logging
        self.setup_logging()

        # Validate directories
        self.validate_directories()

        # Optionally make a copy of the input directory
        if make_copy:
            self.input_dir = self.make_copy_input_dir(self.input_dir, sample_size=copy_sample_size)
            print(f"Copy of input directory created at {self.input_dir}")

    def setup_logging(self):
        """Setup the logging configuration (file-only, silent in terminal)."""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        self.log_dir = self.output_format_dir / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

        log_file = self.log_dir / f"conversion_errors_{time.strftime('%Y%m%d_%H%M%S')}.log"
        file_handler = logging.FileHandler(log_file)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(formatter)

        # Remove any existing handlers from this logger
        if self.logger.hasHandlers():
            self.logger.handlers.clear()

        # Attach only the file handler (no console handler)
        self.logger.addHandler(file_handler)

        # Also silence the root logger (optional, for libraries)
        logging.getLogger().setLevel(logging.CRITICAL + 1)

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

            path_to_script = Path(__file__).parent / "resources" / "count_files.sh"
            bash_command = [str(path_to_script.resolve()), str(self.input_dir), pattern_string]
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
            file_count_dict = self.count_files_by_extension(self.patterns)
            total_files_to_parse = sum(file_count_dict.values())
            print(f"Total 'svar'-files to process: {total_files_to_parse}")

            outputted_files = []
            input_filepaths = []

            with tqdm(total=total_files_to_parse, desc="Processing Files", unit="file", dynamic_ncols=True, mininterval=0.5) as pbar:
                for root, _, files in islice(os.walk(self.input_dir), 100):
                    folder_name = Path(root).name
                    output_case_folder = self.output_format_dir / folder_name

                    for file in files:
                        file_output, input_filepath_to_be_removed = self.process_file(file, Path(root), output_case_folder, pbar)
                        if isinstance(file_output, list) and isinstance(input_filepath_to_be_removed, Path):
                            outputted_files.extend(file_output)
                            input_filepaths.append(input_filepath_to_be_removed)
                        else:
                            continue
            
            return outputted_files, input_filepaths
    
    def process_file(self, file, input_root, output_case_folder, pbar):
        """Process each file."""
        new_file_name = self.manual_fix_filename(input_root, Path(file))
        new_file_name = Path(new_file_name)

        file_outputs = []
        if any(pattern.lower() in file.lower() for pattern in self.patterns):
            output_case_folder.mkdir(parents=True, exist_ok=True)
            converted_output = self.convert_to_format(new_file_name, input_root, output_case_folder)
            if isinstance(converted_output, list):
                converted_output = [file.name for file in converted_output]
                file_outputs.extend(converted_output)
            elif isinstance(converted_output, Path):
                file_outputs.append(converted_output.name)

            if self.output_format != "pdf":
                path_to_pdf = Path(output_case_folder) / f"{new_file_name.stem}.pdf"
                if path_to_pdf.exists():
                    image_files = self.convert_pdf_to_png(path_to_pdf, self.output_format, output_case_folder)
                    file_outputs.extend(image_files)
                else:
                    self.logger.error(f"PDF file not found for converting to {self.output_format}: {path_to_pdf}")
            
            if len(file_outputs) > 0:
                no_of_files_converted = len(file_outputs)
                pbar.update(no_of_files_converted)

            # Remove the original file after conversion
            input_filepath_to_be_removed = Path(input_root) / new_file_name
            self.remove_parsed_answer_file(input_filepath_to_be_removed)
        else:
            input_filepath_to_be_removed = None

        return file_outputs, input_filepath_to_be_removed
    
    def remove_parsed_answer_file(self, filepath: Path):
        """Remove the parsed answer file."""
        try:
            if filepath.exists():
                os.remove(filepath)
                self.logger.info(f"Removed parsed file: {filepath}")
            else:
                self.logger.error(f"File not found for removal: {filepath}")
        except Exception as e:
            self.logger.error(f"Error removing file {filepath}: {e}")


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

    def convert_pdf_to_png(self, pdf_path, image_format, output_case_folder):
        """Convert a PDF file to PNG"""
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

    def remove_standard_files(self):
        """Check if the file name contains standard file patterns."""
        no_files_deleted = match_and_remove_files(self.input_dir, self.log_dir)

        return no_files_deleted

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
            random.seed(170497)  # For reproducibility
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
                
    def parse_responses_from_patterns(self):
        """Parse høringssvar files known to be valid."""
        total_files_left = self.count_files_by_extension()
        total_pattern_files_to_convert = self.count_files_by_extension(self.patterns)
        self.logger.info(
            f"Starting conversion process for files in {self.input_dir}. Output will be saved to {self.output_format_dir}"
            f"Output format: {self.output_format}"
            f"Patterns used: {self.patterns}"
            f"Total files left in the directory: {total_files_left}"
            f"Total files matching patterns to convert: {total_pattern_files_to_convert}"
            )

        # Process the directory
        parsed_files, input_filepaths = self.process_directory()
        self.logger.info(f"Finished processing files in {self.input_dir}. Output saved to {self.output_format_dir}")

        return total_pattern_files_to_convert
    
    def parse_response_from_vl_classfier(self):
        """Parse høringssvar files using Qwen classification."""
        # Count how many files are left in the directory
        total_files_left = self.count_files_by_extension()
        total_files_left_to_parse = sum(total_files_left.values())
        print(f'Processing the remaining files using Qwen classifier. Total files left: {total_files_left_to_parse}')

        # Process the directory
        output_file_names, original_file_names = self.transform_unknowns_into_pdfs()
        self.logger.info(f"Converted {output_file_names} unknown files to PDF.")
        self.remove_remaining_files(original_file_names)

        return output_file_names, original_file_names

    def transform_unknowns_into_pdfs(self):
        """Convert unknown file types to PDF."""
        file_outputs = []
        original_file_names = []

        for root, _, files in islice(os.walk(self.input_dir), 100):
            for file in files:
                file_path = Path(root) / file  # Full path of the file
        
                if file_path.suffix.lower() != ".pdf":
                    new_file_name = self.manual_fix_filename(Path(root), file_path)
                    new_file_name = Path(new_file_name)
                    self.logger.info(f"Converting {file_path} to PDF as {new_file_name.stem}.pdf")

                    converted_output = self.convert_to_format(new_file_name, Path(root), Path(root))
                    original_file_names.append(Path(Path(root) / new_file_name))

                    if isinstance(converted_output, list):
                        converted_output = [str(file.name) for file in converted_output]
                        file_outputs.extend(converted_output)
                    elif isinstance(converted_output, Path):
                        file_outputs.append(str(converted_output.name))
                else:
                    # If the file is already a PDF, register as converted
                    self.logger.info(f"File {file_path} is already a PDF. No conversion needed.")
                    file_outputs.append(file)  # Add the original file name to the outputs

        return file_outputs, original_file_names

    def x1(self, file, input_root, output_case_folder, pbar):
       """Process each file."""
       new_file_name = self.manual_fix_filename(input_root, Path(file))
       new_file_name = Path(new_file_name)
       file_outputs = []
       if any(pattern.lower() in file.lower() for pattern in self.patterns):
           output_case_folder.mkdir(parents=True, exist_ok=True)
           converted_output = self.convert_to_format(new_file_name, input_root, output_case_folder)
           if isinstance(converted_output, list):
               converted_output = [file.name for file in converted_output]
               file_outputs.extend(converted_output)
           elif isinstance(converted_output, Path):
               file_outputs.append(converted_output.name)
           if self.output_format != "pdf":
               path_to_pdf = Path(output_case_folder) / f"{new_file_name.stem}.pdf"
               if path_to_pdf.exists():
                   image_files = self.convert_pdf_to_png(path_to_pdf, self.output_format, output_case_folder)
                   file_outputs.extend(image_files)
               else:
                   self.logger.error(f"PDF file not found for converting to {self.output_format}: {path_to_pdf}")
           if len(file_outputs) > 0:
               no_of_files_converted = len(file_outputs)
               pbar.update(no_of_files_converted)
           # Remove the original file after conversion
           input_filepath_to_be_removed = Path(input_root) / new_file_name
           self.remove_parsed_answer_file(input_filepath_to_be_removed)

       else:
           input_filepath_to_be_removed = None

       return file_outputs, input_filepath_to_be_removed
    
    def remove_remaining_files(self, input_filepaths):
        """Remove files that are left"""
        removed_files = []
        for input_filepath in input_filepaths:
            try:
                if input_filepath.exists():
                    os.remove(input_filepath)
                    removed_files.append(input_filepath)
                else:
                    self.logger.error(f"File not found for removal: {input_filepath}")
            except Exception as e:
                self.logger.error(f"Error removing file {input_filepath}: {e}")
        self.logger.info(f"Removed {len(removed_files)} original that has been converted into pdf: {removed_files}")

    def start_thinking_thread(self):
        thread = threading.Thread(target=self.think_about_moni_loop, daemon=True)
        thread.start()

    def think_about_moni_loop(self):
        while self.keep_thinking:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Thinking about Monii...")
            time.sleep(300 - datetime.now().second)  # Sync with the start of the next minute
    
    def stop_thinking_thread(self):
        """Sets keep_thinking to False to stop the thinking thread gracefully"""
        self.keep_thinking = False
                    
    def run(self):
        """Start the conversion process."""

        self.start_thinking_thread()
        
        # Creating tacking list:
        self.files_deleted = None
        self.files_known_as_answer = None
        self.files_predicted_as_answer = None

        # Count total number of files (not including folders)
        total_file_count = self.count_files_by_extension()
        # Save the file count to a json file
        with open(self.log_dir / "file_count.json", "w") as f:
            json.dump(total_file_count, f, indent=4)

        # Step 1 - Remove files from input_dir that are not høringssvar based on known file-patterns.
        no_files_deleted = self.remove_standard_files()
        self.files_deleted = no_files_deleted
        
        # Step 2 - Parse høringssvar files known to be valid
        no_pattern_files_converted = self.parse_responses_from_patterns()
        self.files_known_as_answer = no_pattern_files_converted

        # Step 3 - Convert remaining files to pdf
        self.parse_response_from_vl_classfier()

        self.stop_thinking_thread()
        print("Monii will be back soon.")
               

def main():
    parser = argparse.ArgumentParser(description="Convert files to pdf, png, or jpg.")
    parser.add_argument("--input_dir", "-i", required=True, help="Path to the input data directory")
    parser.add_argument("--output_dir", "-o", required=True, help="Path to the output directory")
    parser.add_argument("--make_copy_of_input", "-make_copy", action='store_true', help="Make a copy of the input directory")
    parser.add_argument("--copy_sample_size", "-sample_size", type=int, help="Number of subdirectories to sample when copying", default=None)
    parser.add_argument("--format", "-f", choices=["pdf", "png", "jpg"], help="Output format: pdf, png, or jpg", default="pdf")
    parser.add_argument("--patterns", "-p", help="Comma-separated list of filename patterns to match (e.g., 'svar')", default="")

    args = parser.parse_args()
    input_dir  = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    converter = FileConverter(input_dir, output_dir, args.format, args.patterns, make_copy=args.make_copy_of_input, copy_sample_size=args.copy_sample_size)
    converter.run()

if __name__ == "__main__":
    main()
