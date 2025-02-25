import subprocess
import argparse
import logging
from pathlib import Path
from email import policy
from email.parser import BytesParser
from fpdf import FPDF
from pdf2image import convert_from_path

def convert_email_file(input_file, output_dir, output_format="pdf"):
    """
    Converts an email file (.msg or .oft) to .pdf and optionally to an image format (png/jpg).
    """
    input_file = Path(input_file)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if input_file.suffix.lower() not in ['.msg', '.oft']:
        logging.error(f"Unsupported file format: {input_file.suffix}")
        return
    
    # Convert .msg to .eml
    eml_file = output_dir / f"{input_file.stem}.eml"
    try:
        subprocess.run(["msgconvert", "--outfile", str(eml_file), str(input_file)], check=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"Error converting {input_file} to .eml: {e}")
        return

    # Parse .eml and extract relevant information
    try:
        with open(eml_file, "rb") as f:
            msg = BytesParser(policy=policy.default).parse(f)
        
        subject = msg["subject"] or "(No Subject)"
        sender = msg["from"] or "(Unknown Sender)"
        recipients = msg["to"] or "(No Recipients)"
        date = msg["date"] or "(No Date)"
        body = msg.get_body(preferencelist=("plain"))
        body_text = body.get_content() if body else "(No Body Content)"
    except Exception as e:
        logging.error(f"Error parsing {eml_file}: {e}")
        return

    # Create PDF with email content
    pdf_file = output_dir / f"{input_file.stem}.pdf"
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    pdf.multi_cell(0, 10, f"Subject: {subject}")
    pdf.multi_cell(0, 10, f"From: {sender}")
    pdf.multi_cell(0, 10, f"To: {recipients}")
    pdf.multi_cell(0, 10, f"Date: {date}")
    pdf.ln(5)
    pdf.multi_cell(0, 10, "Body:")
    pdf.multi_cell(0, 10, body_text)
    
    pdf.output(str(pdf_file))
    
    # Convert PDF to image if required
    if output_format in ["png", "jpg"]:
        try:
            images = convert_from_path(str(pdf_file))
            for i, img in enumerate(images):
                img_output = output_dir / f"{input_file.stem}_{i}.{output_format}"
                img.save(img_output, output_format.upper())
        except Exception as e:
            logging.error(f"Error converting {pdf_file} to image: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert MSG/OFT to PDF/Image")
    parser.add_argument("--input", required=True, help="Path to the input .msg or .oft file")
    parser.add_argument("--output_dir", required=True, help="Path to the output directory")
    parser.add_argument("--format", choices=["pdf", "png", "jpg"], default="pdf", help="Output format (default: pdf)")

    args = parser.parse_args()
    convert_email_file(args.input, args.output_dir, args.format)