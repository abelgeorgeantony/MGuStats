#!/usr/bin/env python3
import os
import subprocess
import time

def run_missing_scraper(input_file="raw_data/missing_prns.txt", scraper_script="scraper.py"):
    # Check if the input file exists
    if not os.path.exists(input_file):
        print(f"Error: Cannot find '{input_file}'.")
        return

    print("Starting scraper for missing PRNs...")

    with open(input_file, 'r') as file:
        for line in file:
            prn = line.strip()
            
            # Skip empty lines
            if not prn:
                continue
            
            # Extract the year (first 2 characters)
            year = prn[:2]
            
            # Extract the counter (characters from index 6 to 12)
            counter_padded = prn[6:12]
            
            try:
                # Convert to integer to strip leading zeros automatically
                counter = int(counter_padded)
            except ValueError:
                print(f"Warning: Skipping invalid PRN format -> {prn}")
                continue

            print(f"Fetching PRN: {prn} -> Running: python {scraper_script} --years {year} --counter-start {counter} --counter-end {counter}")
            
            # Build the command as a list for subprocess
            command = [
                "python", scraper_script,
                "--years", year,
                "--counter-start", str(counter),
                "--counter-end", str(counter)
            ]
            
            try:
                # Execute the scraper
                subprocess.run(command, check=True)
            except subprocess.CalledProcessError as e:
                print(f"Error: Scraper failed for PRN {prn}. Details: {e}")
            except FileNotFoundError:
                print(f"Error: Could not find '{scraper_script}'. Make sure it is in the same directory.")
                return

            # Add a 1-second delay to be gentle on the server
            time.sleep(1)

    print("Finished processing all missing PRNs.")

if __name__ == "__main__":
    run_missing_scraper()