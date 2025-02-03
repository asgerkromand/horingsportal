import datetime
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Literal, Optional
from zipfile import ZipFile

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup as bs
from tqdm import tqdm

# Working with word docs
# Through windows API and Word
# import win32com.client

def soffice_converter(input_file, output_file):
    """Libre office word to PDF"""
    subprocess.call(
        [
            "soffice",
            # '--headless',
            "--convert-to",
            "pdf",
            "--outdir",
            output_file,
            input_file,
        ]
    )


def get_year_array(n_years: Optional[int]) -> list[int]:
    """Get a list of years to iterate over.
    n_years: the number of years to iterate over. If None, then iterate over all years.
    """
    today = datetime.datetime.now()
    max_year = today.year + int(today.month / 6) - 2003 + 1
    year_array = list(reversed(range(1, max_year)))
    # For some weird reason, the years are stored as list indexes, and the index 18 is currently missing...
    year_array.pop(year_array.index(18))
    if n_years:
        return year_array[:n_years]
    else:
        return year_array


class HPScraper:
    def __init__(self):
        """
        Starts a session and
        creates an empty list to store webpages.
        """
        self.session = requests.Session()
        self.subpages = []

    def get_subpages(
        self, total=np.inf, page_size=500, years: Optional[int] = None, query: str = ""
    ):
        """
        Collect all hearing-subpages from hoeringsportalen.dk.

        total: the total number of subpages to collect.
        page_size: the number of hearings to collect per request.
        years: the number of years to iterate over. If None, then iterate over all years. From current year and back.
        query: the search query to use. If empty, then all hearings will be collected.
        """

        hearing_count = 0

        request_headers = {
            "Host": "hoeringsportalen.dk",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:80.0) Gecko/20100101 Firefox/80.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "da,en;q=0.7,en-US;q=0.3",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://hoeringsportalen.dk/About",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
        }

        while True:
            payload = {
                "filters": {
                    "SearchString": query,
                    "SelectedHearingYears": get_year_array(years),
                },  # "SelectedHearingTypes":["2","1"]
                "skip": hearing_count,
                "take": page_size,
                "sortParameter": "PublicationDate",
                "sortAscending": "false",
            }

            response = self.session.post(
                "https://hoeringsportalen.dk/hearing/gethearings",
                json=payload,
                headers=request_headers,
            )

            hearings = json.loads(response.text)["Hearings"]

            if len(hearings) == 0 or len(self.subpages) >= total:
                print(f"Finished collecting {len(self.subpages)} subpages")
                break
            else:
                self.subpages += hearings

            hearing_count += 500

            print(f"Collected {hearing_count} hearing subpages", end="\r")

            time.sleep(0.5)

    def save_subpages(self, file_name):
        """
        Save the subpages as a json file.
        """
        with open(file_name, "w") as f:
            f.write(json.dumps(self.subpages))

    def load_subpages(self, file_name):
        """
        Load the subpages from a json file.
        """
        with open(file_name, "r") as f:
            self.subpages = json.load(f)

    def populate(self, mainpath, zip_files=True):
        """
        Download .zip-files & metadata (.json format) from the subpages, and store them in folders named after the hearing-id from the subpages file.
        Skips already collected folders.
        Params:
            mainpath: the folder in which the folders and content from the subpages will be created.
            zip_files: whether to download the zip files or not. If False just download metadata.

        """
        Path(mainpath).mkdir(exist_ok=True)

        if not zip_files:
            done = []
            desc = "Updating meta-data"
        else:
            # Get the hearing-id of the folders already created
            done = os.listdir(mainpath)
            done = [int(x) for x in done]
            desc = "Populating folders"

        # Loop over the rest of the hearing-ids
        for _id in tqdm(
            [x["Id"] for x in self.subpages if x["Id"] not in done],
            smoothing=0,
            desc=desc,
        ):
            # The path for the new folder to save the content.
            path = f"{mainpath}/{_id}"

            # Try to create a new folder
            try:
                os.mkdir(path)
            except FileExistsError:
                pass

            # Get the content from the url of the hearing
            url = f"https://hoeringsportalen.dk/Hearing/Details/{_id}"
            r = self.session.get(url)

            # Meta info:
            fieldset = bs(r.content, features="lxml").find("fieldset")
            details = fieldset.find("h3", {"class": "Høringsdetaljer"})
            containers = fieldset.find_all("div", {"class": "fieldContainer"})
            meta_info = {k.label.text.strip(): k.span.text.strip() for k in containers}
            meta_info["details"] = details if details else ""

            with open(f"{path}/{_id}_meta.json", "w") as f:
                json.dump(meta_info, f)

            time.sleep(0.5)

            if zip_files:
                # Zip file:
                r = self.session.get(
                    f"https://hoeringsportalen.dk/Hearing/DownloadDocumentsAsZipFile?hearingId={_id}&includeHidden=False"
                )

                with open(f"{path}/{_id}.zip", "wb") as f:
                    f.write(r.content)

                time.sleep(0.5)

    def get_valid_filename(self, s):
        """
        Return the given string converted to a string that can be used for a clean
        filename. Remove leading and trailing spaces; convert other spaces to
        underscores; and remove anything that is not an alphanumeric, dash,
        underscore, or dot.
        >>> get_valid_filename("john's portrait in 2004.jpg")
        'johns_portrait_in_2004.jpg'
        """
        if len(s) > 100:
            s = s[:100] + "." + s.split(".")[-1]

        s = str(s).strip().replace(" ", "_")

        return re.sub(r"(?u)[^-\w.]", "�", s)

    def unzip(self, mainpath):
        filepath = mainpath
        dirs = os.listdir(filepath)

        for folder in tqdm(dirs, smoothing=0.1, desc="Unzipping data"):
            if len(os.listdir(filepath / folder)) > 2:
                continue
            else:
                try:
                    with ZipFile(filepath / folder / f"{folder}.zip", "r") as zf:
                        for file in zf.namelist():
                            org_file = file
                            file = self.get_valid_filename(file)
                            with open(
                                filepath / folder / file, "wb"
                            ) as f:  # open the output path for writing
                                f.write(zf.read(org_file))
                except Exception as e:
                    print(folder, e)

    def word_to_PDF(self, file, engine: Literal["win32", "soffice"] = "soffice"):
        """
        Converts word files to pdf
        https://docs.microsoft.com/en-us/previous-versions/office/developer/office-2007/bb216319(v=office.12)?redirectedfrom=MSDN
        """
        in_file = os.path.abspath(file)
        out_file = os.path.abspath(
            re.sub(".docx?m?", ".pdf", file, flags=re.IGNORECASE)
        )
        if engine == "win32":
            wdFormatPDF = 17

            word = win32com.client.DispatchEx("Word.Application")
            word.visible = False
            wb = word.Documents.OpenNoRepairDialog(in_file, False, False)
            doc = word.ActiveDocument
            doc.SaveAs(out_file, FileFormat=wdFormatPDF)
            doc.Close()
            word.Quit()
        elif engine == "soffice":
            soffice_converter(in_file, "/".join(in_file.split("/")[:-1]))

    def file_conversion(self, mainpath):
        """Converts høringslister from .doc, .docx and .docm files into PDF files.

        Returns [list]: a list of høringslister with another extension.
        """
        # A list of all folders
        folders = os.listdir(mainpath)

        # An empty list to work with the additional files
        extra_files = []

        for folder in tqdm(folders, desc="Converting files", smoothing=0):
            # All the files in the folder
            folder_path = mainpath / folder
            files = os.listdir(folder_path)

            for file in files:
                # The name and extension of the file
                file_name, file_extension = os.path.splitext(file)

                #                 if file_extension == '.docm':
                #                     # Rename the file from .docm to .doc
                #                     os.rename(folder_path + '/' + file, folder_path + '/' + file.replace('.docm', '.doc'))
                #                     file = file.replace('.docm', '.doc')
                #                     file_extension = '.doc'

                if "liste" in file_name:
                    if file_extension in [".doc", ".docx", ".docm", "docxm"]:
                        self.word_to_PDF(str(folder_path / file))
                    else:
                        extra_files.append(file)

    def meta_extract(self, mainpath, savefile):
        """
        Extract meta data from the folders and save them to a .csv file
        """
        dirs = os.listdir(mainpath)

        file_list = [f"{mainpath}/{folder}/{folder}_meta.json" for folder in dirs]

        dfs = []  # an empty list to store the data frames
        for file in tqdm(file_list, desc="Merging metadata", smoothing=0):
            data = pd.read_json(file, lines=True)  # read data frame from json file
            data["Høringsnr"] = re.findall(r"\d+", file)[0]
            dfs.append(data)  # append the data frame to the list

        temp = pd.concat(
            dfs, ignore_index=True
        )  # concatenate all the data frames in the list.
        temp.to_csv(savefile)


def parse_args():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument(
        "--all",
        action="store_true",
        default=False,
        help="Run all the commands in chronological order",
    )
    parser.add_argument(
        "--get-subpages",
        action="store_true",
        default=False,
        help="Collect data on the hearings through iterating over the search subpages",
    )
    parser.add_argument(
        "--n-years",
        type=int,
        default=None,
        help="Number of hearing years to iterate over. Goes from current year and back.",
    )
    parser.add_argument("--save-subpages", action="store_true", default=False)
    parser.add_argument("--load-subpages", action="store_true", default=False)
    parser.add_argument(
        "--populate",
        action="store_true",
        default=False,
        help="Collect data (metadata and attachments) from the subpages",
    )
    parser.add_argument(
        "--extract-meta",
        action="store_true",
        default=False,
        help="Extract metadata and save to metadata.csv",
    )
    parser.add_argument(
        "--unzip",
        action="store_true",
        default=False,
        help="Unzip all the collected attachments",
    )
    parser.add_argument(
        "--convert-to-pdf",
        action="store_true",
        default=False,
        help="Convert all lists to pdf file (from eg. .doc or .txt). The extractor only works on PDF files.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    hp_scraper = HPScraper()
    if args.all or args.get_subpages:
        hp_scraper.get_subpages(years=args.n_years)
    if args.all or args.save_subpages:
        hp_scraper.save_subpages(args.data_dir / "subpages.json")
        print("Saved file to:", args.data_dir / "subpages.json")
    if args.load_subpages or args.populate:
        hp_scraper.load_subpages(args.data_dir / "subpages.json")
    if args.all or args.populate:
        hp_scraper.populate(args.data_dir / "hearings")
    if args.all or args.extract_meta:
        hp_scraper.meta_extract(
            args.data_dir / "hearings", args.data_dir / "metadata.csv"
        )
        print("Saved file to:", args.data_dir / "metadata.csv")
    if args.all or args.unzip:
        hp_scraper.unzip(args.data_dir / "hearings")
    if args.all or args.convert_to_pdf:
        hp_scraper.file_conversion(args.data_dir / "hearings")
