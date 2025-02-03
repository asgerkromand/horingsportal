# Høringsportalen


## Introduction

The files are generated through the following steps:
1. Collect initial information about hearings from [Høringsportalen](https://hoeringsportalen.dk/), can specify year range and query.
2. Populate folder for each hearing with a zip file of the files attached to the hearing, and a file containing meta data on the hearing.
3. Unzip files
4. Convert relevant files to PDF (easier for extraction)
5. Extract the actors from each hearing

The current files are based on hearings from 2018/2019 ->

## Files

The file structure for the data is as follows:

```
.
├── hearings
│   ├── 100001
│   ├── 100002
│   └── ...
├── scripts
│   ├── extract.py
│   └── scrape.py
├── all_hearings.json
├── all_hearings_entity_counts.csv
├── bill_hearings.json
├── bill_hearings_entity_counts.csv
├── metadata.csv
├── subpages.json
├── requirements.txt
└── README.md

2 directories, 10 files
```

- `hearings/`: Not included, but can be populated by running `scrape.py` script from `scripts/`.
- `scripts/`: Scripts used to collect and parse the data, for more info see the next sections of this file.
- `all_hearings.json`: json file containing a dictionary with hearing IDs as keys and a list of entities as values.
- `all_hearings_entity_counts.csv`: Counts of occurences of each entity across all hearings.
- `bill_hearings.json`: json file containing a dictionary with hearing IDs as keys and a list of entities as values.
- `bill_hearings_entity_counts.csv`: Counts of occurences of each entity across all bill hearings.
- `metadata.csv`: Metadata for each hearing in a csv structure.
- `subpages.json`: Information about each hearing collected from initial scrape of the hearing IDs.
- `requirements.txt`: Requirements for python packages used to run the scripts.

## Scripts
### Setup
Create a new python environment and install the required packages from the `requirements.txt` file.

For the PDF extraction to fully function, you are required to also install the following [ghostscript](https://ghostscript.com/releases/gsdnld.html).

The scripts have been configured to work through the following CLI:

### Data scraping

```console
python scripts/scrape.py --help
```

```console
python scripts/scrape.py --data-dir data --all
```

You can specify a range of years to collect backwards in time through the --n-years flag:

```console
python scripts/scrape.py --data-dir data --all --n-years=6
```

### Data extraction

```console
python scripts/extract.py --help
```

```console
python scripts/extract.py --data-dir data --all --type all
python scripts/extract.py --data-dir data --all --type bill
```
