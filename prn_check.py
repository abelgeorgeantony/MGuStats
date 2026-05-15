#!/usr/bin/env python3
import os
from collections import defaultdict, Counter

def find_missing_prns(valid_file, invalid_file, output_file="raw_data/missing_prns.txt"):
    # Check if input files exist
    if not os.path.exists(valid_file) or not os.path.exists(invalid_file):
        print(f"Error: Make sure both '{valid_file}' and '{invalid_file}' exist.")
        return

    # Load raw PRNs into lists
    with open(valid_file, 'r') as f:
        valid_raw = [line.strip() for line in f if line.strip()]
    with open(invalid_file, 'r') as f:
        invalid_raw = [line.strip() for line in f if line.strip()]

    # ---------------------------------------------------------
    # 1. STRUCTURAL VALIDATION CHECK
    # ---------------------------------------------------------
    print("\n--- Running Structural Validation ---")
    
    valid_list = []
    invalid_list = []
    malformed_valid = []
    malformed_invalid = []

    # Check valid file
    for i, prn in enumerate(valid_raw):
        if len(prn) == 12 and prn.isdigit():
            valid_list.append(prn)
        else:
            malformed_valid.append((i + 1, prn)) # Save line number and bad string

    # Check invalid file
    for i, prn in enumerate(invalid_raw):
        if len(prn) == 12 and prn.isdigit():
            invalid_list.append(prn)
        else:
            malformed_invalid.append((i + 1, prn))

    # Report malformed data
    found_structural_issues = False
    
    if malformed_valid:
        found_structural_issues = True
        print(f"[!] Found {len(malformed_valid)} malformed entries in {valid_file}:")
        for line_num, bad_prn in malformed_valid[:5]:
            print(f"  - Line {line_num}: '{bad_prn}'")
        if len(malformed_valid) > 5:
            print(f"  ... and {len(malformed_valid) - 5} more.")

    if malformed_invalid:
        found_structural_issues = True
        print(f"[!] Found {len(malformed_invalid)} malformed entries in {invalid_file}:")
        for line_num, bad_prn in malformed_invalid[:5]:
            print(f"  - Line {line_num}: '{bad_prn}'")
        if len(malformed_invalid) > 5:
            print(f"  ... and {len(malformed_invalid) - 5} more.")

    if not found_structural_issues:
        print("[✓] All PRNs are structurally valid (exactly 12 digits).")
    else:
        print("[!] Note: Malformed entries have been temporarily excluded from further checks to prevent crashes.")

    # ---------------------------------------------------------
    # 2. MISSING PRN LOGIC
    # ---------------------------------------------------------
    # Convert validated lists to sets for the missing PRN logic and fast lookups
    valid_prns = set(valid_list)
    invalid_prns = set(invalid_list)
    all_known_prns = valid_prns.union(invalid_prns)
    
    # Track min and max limits for each year
    year_limits = defaultdict(lambda: {"min": float('inf'), "max": float('-inf')})
    
    # Determine limits based solely on valid_prns.txt
    for prn in valid_prns:
        year = prn[:2] 
        prn_int = int(prn)
        
        if prn_int < year_limits[year]["min"]:
            year_limits[year]["min"] = prn_int
        if prn_int > year_limits[year]["max"]:
            year_limits[year]["max"] = prn_int
            
    # Find missing PRNs within those limits
    missing_prns = defaultdict(list)
    
    for year, limits in year_limits.items():
        for prn_int in range(limits["min"], limits["max"] + 1):
            prn_str = str(prn_int)
            if prn_str not in all_known_prns:
                missing_prns[year].append(prn_str)
                
    # Display missing PRN summary
    total_missing = sum(len(lst) for lst in missing_prns.values())
    print(f"\n--- Missing PRN Scan Complete! Found {total_missing} gaps. ---")
    
    # Save the missing PRNs to the output file
    # Make sure output directory exists
    os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)
    
    with open(output_file, 'w') as f:
        for year in sorted(missing_prns.keys()):
            for prn in missing_prns[year]:
                f.write(f"{prn}\n")
                
    print(f"Successfully saved all missing numbers to: {output_file}")
    
    # Print a brief preview to the terminal
    for year, m_list in sorted(missing_prns.items()):
        print(f"\nYear 20{year} Limit: {year_limits[year]['min']} to {year_limits[year]['max']}")
        print(f"Total missing for 20{year}: {len(m_list)}")
        
        if len(m_list) > 0:
            print("Preview:")
            for prn in m_list[:5]: # Show only the first 5 in the terminal
                print(f"  - {prn}")
            if len(m_list) > 5:
                print(f"  ... and {len(m_list) - 5} more.")

    # ---------------------------------------------------------
    # 3. DUPLICATE CHECKING LOGIC
    # ---------------------------------------------------------
    print("\n--- Running Duplicate Check ---")
    
    # Count occurrences in each validated list
    valid_counts = Counter(valid_list)
    invalid_counts = Counter(invalid_list)
    
    # Find items that appear more than once
    valid_dupes = {prn: count for prn, count in valid_counts.items() if count > 1}
    invalid_dupes = {prn: count for prn, count in invalid_counts.items() if count > 1}
    
    # Find items that exist in both files
    cross_dupes = valid_prns.intersection(invalid_prns)
    
    found_dupe_issues = False
    
    if valid_dupes:
        found_dupe_issues = True
        print(f"\n[!] Found {len(valid_dupes)} PRNs duplicated within {valid_file}:")
        for prn, count in list(valid_dupes.items())[:5]:
            print(f"  - {prn} (appears {count} times)")
        if len(valid_dupes) > 5:
            print(f"  ... and {len(valid_dupes) - 5} more.")
            
    if invalid_dupes:
        found_dupe_issues = True
        print(f"\n[!] Found {len(invalid_dupes)} PRNs duplicated within {invalid_file}:")
        for prn, count in list(invalid_dupes.items())[:5]:
            print(f"  - {prn} (appears {count} times)")
        if len(invalid_dupes) > 5:
            print(f"  ... and {len(invalid_dupes) - 5} more.")
            
    if cross_dupes:
        found_dupe_issues = True
        print(f"\n[!] Found {len(cross_dupes)} PRNs that appear in BOTH files:")
        for prn in list(cross_dupes)[:5]:
            print(f"  - {prn}")
        if len(cross_dupes) > 5:
            print(f"  ... and {len(cross_dupes) - 5} more.")
            
    if not found_dupe_issues:
        print("[✓] All clear! No duplicates found in individual files or across both files.\n")

if __name__ == "__main__":
    find_missing_prns("raw_data/valid_prns.txt", "raw_data/invalid_prns.txt")