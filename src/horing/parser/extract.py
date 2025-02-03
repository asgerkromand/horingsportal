import glob
import json
import logging
import os
import re
import time
from collections import Counter
from enum import StrEnum

import pandas as pd
from bs4 import BeautifulSoup as bs
from tqdm.autonotebook import tqdm

# Packages to handle PDF-reading

from ghostscript import GhostscriptError

## Working with PDFs as text
import fitz

## Extracting tables from PDFs
import camelot  # Best at detecting if there is a table or not on the page
import pdfplumber  # Best at extracting the actual contents of the table

# OCR on PDFs
import ocrmypdf


def create_logger():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s: %(message)s", datefmt="%Y-%m-%d - %H:%M:%S"
    )

    fh = logging.FileHandler(
        filename="extractor.log",
        mode="w",
    )
    fh.setFormatter(formatter)
    fh.setLevel(logging.INFO)

    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    ch.setLevel(logging.ERROR)

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


logger = create_logger()


def get_list_files(mainpath, pattern, hearing_ids=False, greedy=False):
    """Returns a list of files for hearings based on a pattern matching file names"""
    høringsfiler = {}

    if hearing_ids:
        folders = [
            folder for folder in os.listdir(mainpath) if int(folder) in hearing_ids
        ]
    else:
        folders = os.listdir(mainpath)

    if isinstance(pattern, str):
        desc = f"Extracting PDF-files containing '{pattern}'"
    elif isinstance(pattern, list):
        if greedy:
            desc = f"Extracting PDF-files for folders where any of the following keywoards are present: '{pattern}'"
        else:
            desc = f"Extracting PDF-files for folders where all of the following keywoards are present: '{pattern}'"
    else:
        raise TypeError("pattern must be either str or list")

    for folder in tqdm(folders, desc=print(desc), smoothing=0):
        folderfiles = glob.glob(f"{mainpath}/{folder}/*.pdf")

        if type(pattern) == str:
            høringsfiler[folder] = [file for file in folderfiles if pattern in file]

        if type(pattern) == list:
            files = []
            for p in pattern:
                files += [file for file in folderfiles if p in file]

            error = False
            if not greedy:
                pass
            else:
                for p in pattern:
                    if not len([file for file in files if p in file]):
                        error = True
            if not error:
                høringsfiler[folder] = files

    files = [høringsfiler[x] for x in høringsfiler if len(høringsfiler[x]) > 0]
    files = [x for y in files for x in y]
    files = [file.replace("\\", "/") for file in files]
    print(f"{len(files)} files found")
    return files


class NGOExtractor:
    def __init__(self):
        """
        Provide the list of files to extract NGOs from.

        Initialized with:
            - an empty dict `ngos_list´ to be populated,
        """
        # A dictionary of hearing and NGOs. Hearing-id as key and list of NGOs as value
        self.ngos_list = {}

    def mean_commas(self, ngos):
        """Counts the mean number of commas"""
        if ngos:
            count = [x.count(",") for x in ngos]
            return sum(count) / len(ngos)
        else:
            return 0

    def casing(self, NGO):
        """
        A function for fixing the casing of the NGO names
        """
        ngo = []
        for word in re.split("(\W)", NGO):
            if word.islower():
                ngo.append(word.title())
            else:
                ngo.append(word)
        ngo = "".join(ngo)
        return ngo

    #     def get_margin_style(self, page):

    #         # Create a soup instance from the html-representation of the PDF-text
    #         soup = bs(page.get_text('html'), features="lxml")

    #         # Delete symbols from the soup
    #         elements = soup.find_all('span')
    #         elements = [x for x in elements if 'symbol' in x['style'].lower()]

    #         for element in elements:
    #             if len(element.parent.text) < 4:
    #                     element.parent.decompose()
    #             else:
    #                 element.decompose()

    #         # Delete images from the soup
    #         elements = soup.find_all('img')
    #         for element in elements:
    #             element.decompose()

    #         # Extracting the most common HTML-style from the soup
    #         #most_common_style = Counter([(x['style']) for x in soup.find_all('span')]).most_common()[0][0]

    #         # Extract the most common left margin from the soup
    #         left_margin = int(Counter(re.findall('left:(\d*)pt', str(soup))).most_common()[0][0])

    #         return left_margin #most_common_style,

    def extract_page(self, page, most_common_style):
        """Extract a list of NGOs from a PDF-page object"""

        # Create a soup instance of the html-representation of the pdf
        soup = bs(page.get_text("html"), features="lxml")

        # An empty list to store the NGOs in
        ngos = []

        # If there's recognizeable text in the HTML:
        if soup.text.strip():
            # Delete symbols from the soup
            elements = soup.find_all("span")
            elements = [x for x in elements if "symbol" in x["style"].lower()]

            for element in elements:
                if element.parent and len(element.parent.text) < 4:
                    element.parent.decompose()
                else:
                    element.decompose()

            # Delete images from the soup
            elements = soup.find_all("img")
            for element in elements:
                element.decompose()

            # Extract the NGOs if they fit the most common left-margin and style
            # return [x.find('span', style=most_common_style).text.strip() for x in soup.find_all(style = re.compile(fr'{left_margin}')) if x.find('span', style=most_common_style)]
            # return [x.text.strip() for x in soup.find_all(style = re.compile(fr'{left_margin}')) if x.find('span', style=most_common_style)]

            elems = soup.find_all("p")

            # Extract the most common left margin
            c = Counter(re.findall("left:(-?[\d\.]*)pt", str(soup)))
            left_margin = float(c.most_common()[0][0])

            logger.debug(f"Most common left margin: {left_margin}")

            left_margin_elems = []

            for elem in elems:
                if (
                    left_margin - 1
                    <= (
                        elem_left_margin := float(
                            re.findall("left:(-?[\d\.]*)pt", str(elem))[0]
                        )
                    )
                    <= left_margin + 1
                ):
                    left_margin_elems.append(elem)
                logger.debug(f"Element left margin: {elem_left_margin}")

            logger.debug(
                f"Number of rows based on left margin: {len(left_margin_elems)}"
            )

            # Extract the top-margins based on the most common left margin
            top_margins = re.findall(
                "top:[\d\.]*pt",
                " ".join(elem["style"] for elem in left_margin_elems),
            )
            logger.debug(f"Number of rows based on top style: {len(top_margins)}")

            for margin in top_margins:
                ngos.append(
                    "".join(
                        [
                            x.text
                            for x in elems
                            if margin in x["style"]
                            and x.span["style"] == most_common_style
                            and not x.span.parent.name == "b"
                        ]
                    )
                )
        else:
            logger.warn("No recognizable text found in HTML")

        return ngos

    def get_most_common_style(self, first_page):
        """
        Get the most common used style for the first page
        """
        soup = bs(first_page.get_text("html"), features="lxml")

        # Extract the most common style:
        elements = soup.find_all("span", style=True)
        elements = [
            element
            for element in elements
            if "symbol" not in element["style"].lower()
            and len(element.text.strip()) > 1
            and "@" not in element.text
        ]
        if elements:
            most_common_style = Counter([x["style"] for x in elements]).most_common()[
                0
            ][0]

            return most_common_style
        else:
            return None

    def extract_document(self, doc):
        """Exctracting a list of NGOs from a PDF-file"""

        # An empty list for storing NGOs
        ngos = []

        # Extract the most common style based on the first page
        most_common_style = self.get_most_common_style(doc[0])
        if most_common_style:
            logger.debug(f"most common style: {most_common_style}")

            for page in doc:
                try:
                    ngos += self.extract_page(page, most_common_style)
                except IndexError:
                    time.sleep(0.5)
                    ngos += self.extract_page(page, most_common_style)
        else:
            logger.debug("could not find most common style")
        return ngos

    def table_extract(self, file):
        """Extract a list of NGOs from PDF-tables"""

        tables = []
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                tables += page.extract_tables()

        ngos = [str(ngo[0]).replace("\n", "") for y in tables for ngo in y]

        return ngos

    def ngo_cleaner(self, ngos):
        # Cleaning the list of NGOs

        ## Removing empty entries
        ngos = [x for x in ngos if len(x) > 1]

        ## Check for comma-seperated layout
        if self.mean_commas(ngos) >= 2:
            # Creating one long string
            raw = "".join(ngos).strip()

            # Splitting by commas
            raw = [x for x in re.split("([\w\)\s]),", raw)]

            # Connecting strings with their endings
            raw = [a + b for a, b in zip(raw[::2], raw[1::2])]

            # Stripping blank spaces
            raw = [x.strip() for x in raw]

            # Removing word-splitting hyphens
            raw = [re.sub("(\-)(?=[a-z])", "", x) for x in raw]

            # saving as ngos
            ngos = raw

        ## Removing e-mail adresses
        ngos = [
            " ".join(v)
            for v in [[y for y in ngo.split() if "@" not in y] for ngo in ngos]
        ]

        ## Delete site notations and title
        ngos = [
            ngo
            for ngo in ngos
            if "side" not in ngo.lower().split()
            and "høringsliste" not in ngo.lower()
            and ngo.lower().strip() != "andre"
        ]

        ## Remove list-symbol
        ngos = [ngo.replace("•", "") for ngo in ngos]
        ## adding space to with symbol
        ngos = [ngo.replace("/v", " /v") for ngo in ngos]
        ## removing double spaces
        ngos = [ngo.replace("  ", "") for ngo in ngos]

        ngos = [re.sub(" 1 ", " I ", ngo) for ngo in ngos]

        # Removing adresses and CVR numbers
        ngos = [ngo for ngo in ngos if len([l for l in ngo if l.isdigit()]) < 4]

        # Removing phone numbers
        ngos = [ngo for ngo in ngos if "tlf." not in ngo.lower()]

        ## Removing symbol from e-mail ending
        ngos = [ngo.strip(" -").strip(" –").strip(".").strip() for ngo in ngos]

        ## Removing pre-fix numbers
        ngos = [re.sub("^\d+\.", "", ngo).strip() for ngo in ngos]

        ## Removing entries ending with :
        ngos = [ngo for ngo in ngos if not ngo.endswith(":")]

        ngos = [ngo.strip(",").strip() for ngo in ngos]

        ## If a comma is present, keep only the part before the first
        # ngos = [ngo.split(',')[0].strip() for ngo in ngos]

        ## Deleting only page numbers
        ngos = [ngo for ngo in ngos if not ngo.isdigit()]

        ## Keeping only entries with at least 2 letters
        ngos = [ngo for ngo in ngos if len(ngo) > 1]

        ## Delete empty entries
        ngos = [ngo for ngo in ngos if ngo.strip() != ""]

        #         ## Removing the entries if more than a third of them are not in title-case (this is to remove documents which are either not hearinglists, or from which we don't obtain the list of NGO's)
        #         if len([ngo for ngo in ngos if ngo == ngo.title()]) <= len(ngos)/3:
        #             ngos = []

        # Stream lining the casing to title-case
        ngos = [self.casing(ngo) for ngo in ngos]

        # Removing duplicates
        # ngos = sorted(list(set(ngos)))

        return ngos

    def ocr(self, file, doc):
        print(f"Performing OCR: {file}")

        # Close the old PDF
        doc.close()

        # Perform OCR and overwrite the old PDF
        ocrmypdf.ocr(
            file,
            file.split(".")[0] + "_ocr." + file.split(".")[1],
            # deskew=True,
            skip_text=True,
            language="dan",
        )

        file = file.split(".")[0] + "_ocr." + file.split(".")[1]

        return file

    def extract(self, files):
        # Changing the file-type to list in order to function properly in the loop and storing them in self
        if isinstance(files, list):
            pass
        else:
            files = [files]

        for file in tqdm(
            files, smoothing=0, desc="Extracting NGOs from hearings lists"
        ):
            # Opening the PDF
            with fitz.open(file) as doc:
                hearing = file.split("/")[-2]

                # 1 - Check if the file has any regocnized text on the first page

                if len(doc[0].get_text()) < 10:
                    # If the PDF-file is empty skip. [Currently OCR does not yield a good enough result]

                    self.ngos_list[hearing] = []
                    logger.warn(f"{hearing} - No text found on first page for")

                    continue

                #                 try:
                #                     file = self.ocr(file, doc)
                #                 except ImportError:
                #                     print('ImportError')
                #                     hearing = file.split('/')[-2]
                #                     self.ngos_list[hearing] = []

                #                     continue

                # 2 - Method 1 - Table Extraction
                try:
                    table = camelot.read_pdf(file, line_scale=25, resolution=500)
                except GhostscriptError as e:
                    self.ngos_list[hearing] = []
                    logger.warn(f"{hearing} - GhostscriptError: {e}")
                    continue

                if table:
                    ngos = self.table_extract(file)
                    logger.info(f"{hearing} - Extracted list from table")

                # 3 - Method 2 - from text
                else:
                    ngos = self.extract_document(doc)
                    logger.info(f"{hearing} - Extracted list from text")

                ngos_cleaned = self.ngo_cleaner(ngos)
                logger.info(
                    f"Finished cleaning NGO list from document ({len(ngos)} --> {len(ngos_cleaned)})"
                )

                # Adding the list of NGO's to the hearing-id
                if hearing in self.ngos_list:
                    self.ngos_list[hearing] += ngos_cleaned

                else:
                    self.ngos_list[hearing] = ngos_cleaned

    def save_file(self, filename):
        with open(filename, "w") as f:
            json.dump(self.ngos_list, f)


class HearingType(StrEnum):
    bill = "bill"
    all = "all"


def parse_args():
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument(
        "--all",
        action="store_true",
        default=False,
        help="Run all the commands in chronological order",
    )
    parser.add_argument("--type", type=HearingType, default="all", help="Hearing type")
    parser.add_argument(
        "--extract",
        action="store_true",
        default=False,
        help="Extract entities and save them in a .json file",
    )
    parser.add_argument(
        "--count", action="store_true", default=False, help="Count entities"
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    metadata = pd.read_csv(args.data_dir / "metadata.csv", index_col=0)
    if args.type == HearingType.bill:
        hearing_ids = metadata[metadata["Høringstype"] == "Lovforslag"][
            "Høringsnr"
        ].to_list()
        filename = "bill_hearings"
    elif args.type == HearingType.all:
        hearing_ids = metadata["Høringsnr"].to_list()
        filename = "all_hearings"
    else:
        raise ValueError("Invalid hearing type")

    if args.all or args.extract:
        files = get_list_files(
            args.data_dir / "hearings", "liste", hearing_ids=hearing_ids
        )

        høringslistefiler = [file for file in files if "liste" in file]
        høringssvarfiler = [file for file in files if "svar" in file]

        ngo_extractor = NGOExtractor()
        ngo_extractor.extract(høringslistefiler)
        filepath = args.data_dir / f"{filename}.json"
        ngo_extractor.save_file(filepath)
        print(f"Saved file to {filepath}")

    if args.all or args.count:
        with open(args.data_dir / f"{filename}.json") as f:
            data = json.load(f)
        filepath = args.data_dir / f"{filename}_entity_counts.csv"
        c = Counter([x for y in data.values() for x in y])
        pd.DataFrame(
            [(k, v) for k, v in c.items()], columns=["entity", "count"]
        ).sort_values(by="count", ascending=False).to_csv(filepath, index=False)
        print(f"Saved file to {filepath}")
