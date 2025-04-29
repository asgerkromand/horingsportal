import re
import os
import csv
import random
from typing import List, Dict
from collections import defaultdict
from pathlib import Path
import pandas as pd

def match_rules(filename: str):
    """Return list of rule matches for a given filename (excluding extension)."""
    matches = []
    filename_lower = filename.lower()  # Case-insensitive comparison

    # Rule 1: 'bekendtgoerelse' appears but not 'svar' anywhere in the filename
    if 'bekendtgoerelse' in filename_lower and 'svar' not in filename_lower:
        matches.append({'rule': 1, 'description': 'Contains "bekendtgoerelse" without "svar"'})

    # Rule 2: 'hoering' appears but not 'svar' anywhere in the filename
    if 'hoering' in filename_lower and 'svar' not in filename_lower:
        matches.append({'rule': 2, 'description': 'Contains "hoering" without "svar"'})

    # Rule 3: 'liste' appears but not prefixed by 'hoering' and not 'svar' anywhere
    if 'liste' in filename_lower and 'hoering' not in filename_lower and 'svar' not in filename_lower:
        matches.append({'rule': 3, 'description': 'Contains "liste" but not prefixed by "hoering" and without "svar"'})

    # Rule 4: 'hoeringsnotat' appears
    if 'hoeringsnotat' in filename_lower:
        matches.append({'rule': 4, 'description': 'Contains "hoeringsnotat"'})

    # Rule 5: 'hoeringsbrev' appears
    if 'hoeringsbrev' in filename_lower:
        matches.append({'rule': 5, 'description': 'Contains "hoeringsbrev"'})

    # Rule 6: 'forslag', 'lov', and 'til' together but not 'svar'
    if 'forslag' in filename_lower and 'lov' in filename_lower and 'til' in filename_lower and 'svar' not in filename_lower:
        matches.append({'rule': 6, 'description': 'Contains "forslag", "lov", and "til" but not "svar"'})

    # Rule 7: 'hoeringsliste' appears
    if 'hoeringsliste' in filename_lower:
        matches.append({'rule': 7, 'description': 'Contains "hoeringsliste"'})

    # Rule 8: 'resume' or 'resumé' appears
    if 'resume' in filename_lower or 'resumé' in filename_lower:
        matches.append({'rule': 8, 'description': 'Contains "resume" or "resumé"'})

    # Rule 9: 'bekendtegoerelse' appears but not 'svar'
    if 'bekendtegoerelse' in filename_lower and 'svar' not in filename_lower:
        matches.append({'rule': 9, 'description': 'Contains "bekendtgoerelse" without "svar"'})

    # Rule 10: 'ændring' appears but not 'svar'
    if 'ændring' in filename_lower and 'svar' not in filename_lower:
        matches.append({'rule': 10, 'description': 'Contains "ændring" without "svar"'})

    # Rule 11: 'faktaside' appears
    if 'faktaside' in filename_lower:
        matches.append({'rule': 11, 'description': 'Contains "faktaside"'})

    # Rule 12: 'udkast', 'til', and 'lov' together but not 'svar'
    if 'udkast' in filename_lower and 'til' in filename_lower and 'lov' in filename_lower and 'svar' not in filename_lower:
        matches.append({'rule': 12, 'description': 'Contains "udkast", "til", and "lov" but not "svar"'})

    # Rule 13: 'lovudkast' appears but not 'svar'
    if 'lovudkast' in filename_lower and 'svar' not in filename_lower:
        matches.append({'rule': 13, 'description': 'Contains "lovudkast" without "svar"'})

    # Rule 14: 'lovforslag' appears but not 'svar'
    if 'lovforslag' in filename_lower and 'svar' not in filename_lower:
        matches.append({'rule': 14, 'description': 'Contains "lovforslag" without "svar"'})

    # Rule 15: 'udkast' and 'bekendtgørelse' together but not 'svar'
    if 'udkast' in filename_lower and 'bekendtgørelse' in filename_lower and 'svar' not in filename_lower:
        matches.append({'rule': 15, 'description': 'Contains "udkast" and "bekendtgørelse" without "svar"'})

    # Rule 16: 'lovforslag' without 'hoering'
    if 'lovforslag' in filename_lower and 'hoering' not in filename_lower:
        matches.append({'rule': 16, 'description': 'Contains "lovforslag" without "hoering"'})

    # Rule 17: 'annex' appears
    if 'annex' in filename_lower:
        matches.append({'rule': 17, 'description': 'Contains "annex"'})

    # Rule 18: 'bilag' appears but not 'svar'
    if 'bilag' in filename_lower and 'svar' not in filename_lower:
        matches.append({'rule': 18, 'description': 'Contains "bilag" without "svar"'})

    # Rule 19: 'udkast' and 'bek.' together but not 'svar'
    if 'udkast' in filename_lower and 'bek.' in filename_lower and 'svar' not in filename_lower:
        matches.append({'rule': 19, 'description': 'Contains "udkast" and "bek." without "svar"'})

    # Rule 20: 'orienteringsliste' or 'orienteringsbrev' appears
    if 'orienteringsliste' in filename_lower or 'orienteringsbrev' in filename_lower:
        matches.append({'rule': 20, 'description': 'Contains "orienteringsliste" or "orienteringsbrev"'})

    # Rule 21: 'brev', 'liste', or 'udk' as the exact filename
    if filename_lower in ['brev', 'liste', 'udk']:
        matches.append({'rule': 21, 'description': 'Filename is exactly "brev", "liste", or "udk"'})

    # Rule 22: 'vejledning' appears but not 'svar'
    if 'vejledning' in filename_lower and 'svar' not in filename_lower:
        matches.append({'rule': 22, 'description': 'Contains "vejledning" without "svar"'})

    # Rule 23: 'act' appears as a whole word (not as part of another word)
    if re.search(r'\bact\b', filename_lower) and 'svar' not in filename_lower:
        matches.append({'rule': 23, 'description': 'Contains whole word "act" without "svar"'})

    # Rule 24: 'bkg' appears as a whole word (not as part of another word)
    if re.search(r'\bbkg\b', filename_lower) and 'svar' not in filename_lower:
        matches.append({'rule': 24, 'description': 'Contains whole word "bkg" without "svar"'})

    # Rule 25: 'foelgebrev' appears
    if 'foelgebrev' in filename_lower:
        matches.append({'rule': 25, 'description': 'Contains "foelgebrev"'})

    # Rule 26: 'rapport' appears but not 'svar'
    if 'rapport' in filename_lower and 'svar' not in filename_lower:
        matches.append({'rule': 26, 'description': 'Contains "rapport" without "svar"'})

    return matches

def get_matching_files(input_dir: Path) -> List[Dict[str, str]]:
    """Recursively get files and match them against the rules."""
    log_entries = []
    rule_to_filenames = defaultdict(list)

    for filepath in input_dir.rglob("*"):  # rglob finds files recursively
        if filepath.is_file():  # Skip directories, only process files
            base_name = os.path.splitext(filepath.name)[0]  # Remove extension
            matches = match_rules(base_name)
            
            for match in matches:
                log_entries.append({
                    'filename': filepath,
                    'rule': match['rule'],
                    'description': match['description']
                })
                rule_to_filenames[(match['rule'], match['description'])].append(filepath)
    
    return log_entries, rule_to_filenames

def save_log_to_csv(log_entries: List[Dict[str, str]], output_dir: Path):
    """Save matched files log to CSV."""
    if log_entries:
        os.makedirs(output_dir, exist_ok=True)
        log_file = output_dir / f"removal_log.csv"
        
        with open(log_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['filename', 'rule', 'description'])
            writer.writeheader()
            writer.writerows(log_entries)

def save_summary_to_csv(rule_to_filenames: defaultdict, output_dir: Path):
    """Save summary table to CSV."""
    summary_entries = []
    for (rule_num, desc), files in sorted(rule_to_filenames.items()):
        example_files = random.sample(files, min(5, len(files)))
        summary_entries.append({
            'rule': rule_num,
            'description': desc,
            'count': len(files),
            'example_files': "\n".join([str(f) for f in example_files])
        })

    if summary_entries:
        os.makedirs(output_dir, exist_ok=True)
        summary_file = output_dir / f"summary_log.csv"
        with open(summary_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['rule', 'description', 'count', 'example_files'])
            writer.writeheader()
            writer.writerows(summary_entries)

def delete_matched_files(rule_to_filenames: defaultdict):
    """Deletes all files matched by rules and returns the count."""
    # Flatten the rule_to_filenames dictionary to get all files
    files_to_delete = [filepath for files in rule_to_filenames.values() for filepath in files]
    deleted_count = 0
    for file_path in files_to_delete:
        try:
            if file_path.exists():
                file_path.unlink()
                deleted_count += 1
        except Exception as e:
            print(f"Error deleting {file_path}: {e}")
    return deleted_count

def delete_known_named_files(input_dir: Path):
    """Delete *_meta.json and .zip files based on folder names. Returns count of deleted files."""
    deleted_count = 0
    for folder in input_dir.iterdir():
        if folder.is_dir():
            folder_name = folder.name
            meta_file = folder / f"{folder_name}_meta.json"
            zip_file = folder / f"{folder_name}.zip"

            for file_path in [meta_file, zip_file]:
                try:
                    if file_path.exists():
                        file_path.unlink()
                        deleted_count += 1
                except Exception as e:
                    print(f"Error deleting {file_path}: {e}")
    return deleted_count

def remove_matched_and_known_files(input_dir: Path, rule_to_filenames: defaultdict):
    """Delete matched and known named files."""
    # Count how many files are to be deleted
    no_matched_files_to_delete = delete_matched_files(rule_to_filenames)
    no_known_files_to_delete = delete_known_named_files(input_dir)
    total_files_deleted = no_matched_files_to_delete + no_known_files_to_delete
    print(f"Deleted {no_matched_files_to_delete} matched files and {no_known_files_to_delete} known named files. In total: {total_files_deleted}.")

    return total_files_deleted

def process_log_to_csv(output_dir: Path, log_entries: List[Dict[str, str]], rule_to_filenames: defaultdict):
    """Process log entries and save to CSV."""
    save_log_to_csv(log_entries, output_dir)
    save_summary_to_csv(rule_to_filenames, output_dir)


def match_and_remove_files(input_dir: Path, output_dir: Path):
    """Main function to process files, log to CSV, and output the summary."""
    log_entries, rule_to_filenames = get_matching_files(input_dir)

    process_log_to_csv(output_dir, log_entries, rule_to_filenames)
    total_files_deleted = remove_matched_and_known_files(input_dir, rule_to_filenames)  # Remove files based on 

    return total_files_deleted
