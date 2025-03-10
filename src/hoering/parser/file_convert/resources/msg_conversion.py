import argparse
import logging
import subprocess
from pathlib import Path
from email.parser import BytesParser
from email import policy
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from pdf2image import convert_from_path
from typing import Optional, Dict, Union
from PyPDF2 import PdfReader, PdfWriter
from PIL import Image
import shutil

# Configure logging
logging.basicConfig(
    level=logging.WARNING, format="%(asctime)s - %(levelname)s - %(message)s"
)


class CustomPDF(FPDF):
    def __init__(self):
        super().__init__()
        # Set the path to the external fonts
        path_to_external_fonts = Path(__file__).parent / "external_fonts"

        # Add regular, bold, and oblique versions of the font
        self.add_font(
            "DejaVuSansCondensed",
            "",
            str(path_to_external_fonts / "DejaVuSansCondensed.ttf"),
        )
        self.add_font(
            "DejaVuSansCondensed",
            "B",
            str(path_to_external_fonts / "DejaVuSansCondensed-Bold.ttf"),
        )
        self.add_font(
            "DejaVuSansCondensed",
            "I",
            str(path_to_external_fonts / "DejaVuSansCondensed-Oblique.ttf"),
        )

    def header(self):
        self.set_font("DejaVuSansCondensed", "B", 12)
        self.cell(
            0, 10, "Email Document", 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C"
        )
        self.ln(3)

    def footer(self):
        self.set_y(-15)
        self.set_font("DejaVuSansCondensed", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", 0, new_x=XPos.RIGHT, new_y=YPos.TOP)


def convert_email_file(
    input_file: Path, output_dir: Path, patterns: list, output_format: str = "pdf"
) -> None:
    """Converts an email file (.msg or .oft) to a PDF and optionally to an image format (png/jpg)."""
    if input_file.suffix.lower() not in [".msg", ".oft"]:
        logging.error(f"Unsupported file format: {input_file.suffix}")
        return None

    eml_file = convert_msg_to_eml(input_file, output_dir)
    if not eml_file:
        return None

    email_data, attachments = parse_eml_file(eml_file, output_dir, patterns)
    if not email_data:
        return None

    pdf_file = create_pdf(email_data, attachments, output_dir, input_file.stem)

    if output_format in ["png", "jpg"]:
        convert_pdf_to_image(pdf_file, output_dir, input_file.stem, output_format)


def convert_msg_to_eml(input_file: Path, output_dir: Path) -> Optional[Path]:
    """Converts a .msg or .oft file to .eml format."""
    eml_file = output_dir / f"{input_file.stem}.eml"
    try:
        subprocess.run(
            ["msgconvert", "--outfile", str(eml_file), str(input_file)], check=True
        )
        logging.info(f"Converted {input_file} to {eml_file}")
        return eml_file
    except subprocess.CalledProcessError as e:
        logging.error(f"Error converting {input_file} to .eml: {e}")
        return None


def parse_eml_file(
    eml_file: Path, output_dir: Path, patterns: list
) -> Optional[Dict[str, Union[str, None]]]:
    """Parses an .eml file and extracts relevant email information, including attachments."""
    try:
        with open(eml_file, "rb") as f:
            msg = BytesParser(policy=policy.default).parse(f)

        # Extract email data
        email_data = {
            "subject": msg["subject"] or "(No Subject)",
            "sender": msg["from"] or "(Unknown Sender)",
            "recipients": msg["to"] or "(No Recipients)",
            "date": msg["date"] or "(No Date)",
            "body_text": (
                msg.get_body(preferencelist=("plain")).get_content()
                if msg.get_body(preferencelist=("plain"))
                else "(No Body Content)"
            ),
        }

        # Handle attachments only if filename contains specified patterns
        attachments = [
            save_attachment(part, output_dir)
            for part in msg.iter_attachments()
            if (filename := part.get_filename())
            and any(pattern in filename.lower() for pattern in patterns)
           ]

        return email_data, [
            attach for attach in attachments if attach
        ]  # Filter out None attachments

    except Exception as e:
        logging.error(f"Error parsing {eml_file}: {e}")
        return None, []


def save_attachment(part, output_dir: Path) -> Optional[Path]:
    """Saves an attachment to the specified output directory."""
    try:
        attachment_filename = part.get_filename()
        if not attachment_filename:
            logging.warning("Attachment has no filename.")
            return None

        attachment_path = output_dir / attachment_filename

        # Ensure unique filenames in case of duplicates
        if attachment_path.exists():
            base, extension = attachment_filename.rsplit(".", 1)
            attachment_path = output_dir / f"{base}_1.{extension}"

        with open(attachment_path, "wb") as attachment_file:
            attachment_file.write(part.get_payload(decode=True))

        logging.info(f"Saved attachment: {attachment_path}")
        return attachment_path
    except Exception as e:
        logging.error(f"Error saving attachment {attachment_filename}: {e}")
        return None


def create_pdf(
    email_data: Dict[str, str], attachments: list, output_dir: Path, file_stem: str
) -> Path:
    pdf_file = output_dir / f"{file_stem}.pdf"
    pdf = CustomPDF()
    pdf.set_auto_page_break(auto=True, margin=10)

    # Add a new page only if there is body text to display
    if email_data.get(
        "body_text"
    ).strip():  # Check if body_text is not empty or just whitespace
        pdf.add_page()

        # Set the font to DejaVuSansCondensed regular with smaller size
        pdf.set_font("DejaVuSansCondensed", "", 10)

        cell_width = pdf.w - 20  # Set cell width with margins

        for key in ["subject", "sender", "recipients", "date", "body_text"]:
            # Use the bold font for the header
            pdf.set_font("DejaVuSansCondensed", "B", 10)  # Change from 12 to 10
            pdf.cell(
                cell_width,
                10,
                f"{key.replace('_', ' ').capitalize()}:",
                0,
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
            )

            # Switch back to regular font for the body text
            pdf.set_font("DejaVuSansCondensed", "", 10)  # Change from 12 to 10
            content = email_data.get(key, "(No Content)").strip()  # Strip whitespace
            if content:  # Only add content if it's not empty
                pdf.multi_cell(cell_width, 6, content)  # Change from 8 to 6

            pdf.ln(1)  # Change from 2 to 1 or remove

    pdf.output(str(pdf_file))
    logging.info(f"PDF created: {pdf_file}")

    # Merge with attachments
    if attachments:
        merged_pdf_file = merge_pdfs(pdf_file, attachments, output_dir, file_stem)
        return merged_pdf_file

    return pdf_file


def merge_pdfs(
    main_pdf_path: Path, attachment_pdfs: list, output_dir: Path, file_stem: str
) -> Path:
    """Merge the main PDF with attachment PDFs."""
    merged_pdf_file = output_dir / f"{file_stem}_merged.pdf"
    pdf_writer = PdfWriter()

    # Add the main PDF
    with open(main_pdf_path, "rb") as main_pdf:
        pdf_reader = PdfReader(main_pdf)
        for page in pdf_reader.pages:
            pdf_writer.add_page(page)

    # Add each attachment PDF
    for attachment in attachment_pdfs:
        if attachment.suffix.lower() == ".pdf":
            with open(attachment, "rb") as attachment_pdf:
                pdf_reader = PdfReader(attachment_pdf)
                for page in pdf_reader.pages:
                    pdf_writer.add_page(page)

    # Write the merged PDF to file
    with open(merged_pdf_file, "wb") as output_pdf:
        pdf_writer.write(output_pdf)

    logging.info(f"Merged PDF created: {merged_pdf_file}")
    return merged_pdf_file


def process_attachment(
    attachment_path: Path, output_dir: Path, output_format: str
) -> Optional[Path]:
    """Process and convert an attachment to the specified format (PDF, PNG, or JPG)."""
    ext = attachment_path.suffix.lower()
    original_file_name = attachment_path.stem
    output_file = output_dir / f"{original_file_name}.{output_format}"

    if output_file.exists():
        logging.info(f"Skipping {attachment_path}, already converted.")
        return output_file

    try:
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
            convert_to_pdf(attachment_path, output_dir)
            if output_format in ["png", "jpg"]:
                convert_pdf_to_image(
                    output_file.with_suffix(".pdf"),
                    output_dir,
                    original_file_name,
                    output_format,
                )

        elif ext in [".msg", ".oft"]:
            converted_eml = convert_msg_to_eml(attachment_path, output_dir)
            if converted_eml:
                convert_to_pdf(converted_eml, output_dir)
                if output_format in ["png", "jpg"]:
                    convert_pdf_to_image(
                        output_file.with_suffix(".pdf"),
                        output_dir,
                        original_file_name,
                        output_format,
                    )

        elif ext in [".tif", ".tiff", ".jpg", ".jpeg", ".png"]:
            process_image_attachment(attachment_path, output_dir, output_format)

        elif ext == ".pdf":
            if output_format == "pdf":
                shutil.copy(attachment_path, output_file)
            else:
                convert_pdf_to_image(
                    attachment_path, output_dir, original_file_name, output_format
                )

        else:
            logging.warning(f"Skipping unknown format: {attachment_path}")

        return output_file

    except subprocess.CalledProcessError as e:
        logging.error(f"Error processing {attachment_path}: {e}")
    except Exception as e:
        logging.error(f"Unexpected error processing {attachment_path}: {e}")

    return None


def convert_to_pdf(input_file: Path, output_dir: Path) -> None:
    """Convert a file to PDF format using LibreOffice."""
    subprocess.run(
        [
            "soffice",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_dir),
            str(input_file),
        ],
        check=True,
    )

def process_image_attachment(
    attachment_path: Path, output_dir: Path, output_format: str
) -> None:
    """Handles the processing of image attachments (e.g., TIFF, JPG)."""
    images = (
        convert_from_path(str(attachment_path))
        if attachment_path.suffix.lower() in [".tif", ".tiff"]
        else [Image.open(attachment_path)]
    )
    if output_format == "pdf":
        images[0].save(
            output_dir / f"{attachment_path.stem}.pdf",
            save_all=True,
            append_images=images[1:],
        )
    else:
        for i, img in enumerate(images):
            img.save(
                output_dir / f"{attachment_path.stem}_{i}.{output_format}",
                output_format.upper(),
            )

def convert_pdf_to_image(
    pdf_file: Path, output_dir: Path, file_stem: str, output_format: str
) -> None:
    """Converts a PDF file to an image (PNG or JPG)."""
    try:
        # Ensure the file-domain is lowercase
        output_format = output_format.lower()
        images = convert_from_path(str(pdf_file))
        for i, img in enumerate(images):
            img_output = output_dir / f"{file_stem}_{i}.{output_format}"
            img.save(
                img_output, "JPEG" if output_format == "jpg" else output_format.upper()
            )
            logging.info(f"Image saved: {img_output}")
    except Exception as e:
        logging.error(f"Error converting {pdf_file} to image: {e}")


def convert_msg_input(
    input_path: Path, output_base_dir: Path, output_format: str, patterns: list
) -> None:
    """Processes the input path (file or folder) and manages output structure."""
    if input_path.is_dir():
        process_folder(input_path, output_base_dir, output_format, patterns)
    elif input_path.is_file():
        process_file(input_path, output_base_dir, output_format, patterns)
    else:
        logging.error("Invalid input path. Please provide a valid file or folder.")


def process_folder(
    input_folder: Path, output_base_dir: Path, output_format: str, patterns: list
) -> None:
    """Processes all .msg and .oft files inside a given folder."""
    files = list(input_folder.glob("*.msg")) + list(input_folder.glob("*.oft"))
    if not files:
        logging.error("No .msg or .oft files found in the directory.")
        return

    case_name = input_folder.name  # Use the folder name as the case name
    for file in files:
        # Create a subfolder for each processed file under the case name
        output_dir = output_base_dir / case_name / file.stem
        output_dir.mkdir(parents=True, exist_ok=True)

        convert_email_file(file, output_dir, patterns, output_format)


def process_file(
        input_file: Path, output_dir: Path, output_format: str, patterns: list
        ) -> None:
    """Processes a single .msg or .oft file."""
    if input_file.suffix.lower() not in [".msg", ".oft"]:
        logging.error("Unsupported file format. Please provide a .msg or .oft file.")
        return

    convert_email_file(input_file, output_dir, patterns, output_format)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert MSG/OFT to PDF/Image")
    parser.add_argument(
        "--input_dir", required=True, help="Path to the input file or folder"
    )
    parser.add_argument(
        "--output_dir", required=True, help="Path to the output directory"
    )
    parser.add_argument(
        "--format",
        choices=["pdf", "png", "jpg"],
        default="pdf",
        help="Output format (default: pdf)",
    )
    parser.add_argument(
        "--patterns",
        help="Comma-separated list of filename patterns to match (e.g., 'ringssvar,ringsvar')",
        default="ringssvar,ringsvar",
    )

    args = parser.parse_args()
    convert_msg_input(args.input_dir, args.output_dir, args.format, args.patterns.split(","))
