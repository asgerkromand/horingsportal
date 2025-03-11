import os
import re
from email import message_from_file
from bs4 import BeautifulSoup
from pathlib import Path

class MHTConverter:
    def __init__(self, input_path):
        self.input_path = Path(input_path)
        self.html_content = None

    def load(self):
        """Load and parse the MHT file."""
        # Open and parse the MHT file
        with open(self.input_path, "rb") as mht_file:
            mht_msg = message_from_file(mht_file)

        # Extract the HTML part of the MHT (MIME format)
        for part in mht_msg.walk():
            if part.get_content_type() == "text/html":
                self.html_content = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                break

        if not self.html_content:
            raise ValueError("No HTML content found in the MHT file")
        
        return self

    def convert_to(self, output_path):
        """Convert MHT to HTML and save the result."""
        if not self.html_content:
            raise ValueError("MHT content not loaded. Please load the file first.")

        # Clean HTML using BeautifulSoup
        soup = BeautifulSoup(self.html_content, "html.parser")

        # You can add any cleaning logic here (like removing scripts, styles, etc.)
        for script in soup(["script", "style"]):
            script.decompose()  # Remove unwanted elements

        # Save the cleaned HTML content
        with open(output_path, "w", encoding="utf-8") as output_file:
            output_file.write(str(soup.prettify()))

        return Path(output_path)

    def convert(self):
        """Perform the full conversion process (load and save)."""
        output_html_path = self.input_path.with_suffix(".html")
        return self.convert_to(output_html_path)

# Example usage
converter = MHTConverter("/Users/asgerkromand/Library/CloudStorage/OneDrive-UniversityofCopenhagen/2. SODAS/5 horingsportal/test_files/example_files_for_conversion/mht/15026/Hoeringssvar_dansk_rederiforening.mht")
converter.load().convert_to("converted.html")