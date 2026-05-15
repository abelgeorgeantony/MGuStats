#!/usr/bin/env python3
import os
from collections import defaultdict

def find_missing_prns(valid_file, invalid_file, output_file="raw_data/missing_prns.txt"):
    # Check if input files exist
    if not os.path.exists(valid_file) or not os.path.exists(invalid_file):
        print(f"Error: Make sure both '{valid_file}' and '{invalid_file}' exist in the current directory.")
        return

    # Load known PRNs into a set for fast lookups
    with open(valid_file, 'r') as f:
        valid_prns = {line.strip() for line in f if line.strip()}
    with open(invalid_file, 'r') as f:
        invalid_prns = {line.strip() for line in f if line.strip()}
        
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
                
    # Display summary
    total_missing = sum(len(lst) for lst in missing_prns.values())
    print(f"--- Scan Complete! Found {total_missing} missing PRNs. ---")
    
    # Save the missing PRNs to the output file
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

if __name__ == "__main__":
    find_missing_prns("raw_data/valid_prns.txt", "raw_data/invalid_prns.txt")