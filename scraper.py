import asyncio
import aiohttp
from bs4 import BeautifulSoup
import os
import json
import logging
from aiohttp import ClientTimeout

# Configure terminal logging
logging.basicConfig(
    level=logging.INFO,
    format="\033[32m%(asctime)s\033[0m - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S"
)

# ==========================================
# CONFIGURATION ZONE
# ==========================================
# You must grab the actual form action URL from the MGU network tab
TARGET_URL = "https://YOUR_MGU_RESULT_ENDPOINT.ac.in/results" 

# Semester exams to test for the probe. Load from your mapped JSON.
METADATA_FILE = "metadata.json"

# Limits & Throttling
CONCURRENCY_LIMIT = 15     # Keep between 10-20 to avoid WAF blocks
MAX_RETRIES = 3            # How many times to retry a timed-out request
TIMEOUT_SECONDS = 15       # Drop dead connections after 15s

# Bounding Box (Adjust these based on your probe results)
TARGET_YEAR = "23"
STREAM_MARKER = "0021"
COUNTER_START = 1
COUNTER_END = 120000       # Adjust to the actual ceiling of your year
# ==========================================

async def fetch_and_save(session, semaphore, prn, exam_id):
    """
    Fires the POST request, trims the HTML, and saves the tables.
    Uses a semaphore to strictly limit concurrent connections.
    """
    payload = {
        "prn": prn,
        "exam_id": str(exam_id)
        # Add any other hidden form fields (like __VIEWSTATE) here if MGU requires them
    }

    async with semaphore:
        for attempt in range(MAX_RETRIES):
            try:
                async with session.post(TARGET_URL, data=payload) as response:
                    
                    if response.status in [502, 503, 504]:
                        logging.warning(f"Gateway Error for PRN {prn}. Retrying ({attempt+1}/{MAX_RETRIES})...")
                        await asyncio.sleep(2 ** attempt) # Exponential backoff
                        continue
                        
                    response.raise_for_status()
                    html_content = await response.text()
                    
                    # Process the HTML
                    if process_html(html_content, prn, exam_id):
                        return True # Successfully saved
                    else:
                        return False # Invalid PRN/Empty Table (The "Holes")

            except asyncio.TimeoutError:
                logging.error(f"Timeout on PRN {prn}. Retrying ({attempt+1}/{MAX_RETRIES})...")
                await asyncio.sleep(2)
            except Exception as e:
                logging.error(f"Failed PRN {prn} on Exam {exam_id}: {str(e)}")
                break # Break on non-network errors
                
    return False

def process_html(html_content, prn, exam_id):
    """
    Strips away legacy layout code and saves only the data tables.
    """
    # Using lxml parser for maximum speed
    soup = BeautifulSoup(html_content, 'lxml')
    
    # Extract tables. Exclude layout tables if they have specific attributes
    tables = soup.find_all('table')
    
    if not tables:
        return False
        
    trimmed_html = f"<html><body>\n\n"
    for table in tables:
        trimmed_html += str(table) + "\n<br>\n"
    trimmed_html += "</body></html>"
    
    # Ensure directory exists
    admission_year = f"20{prn[:2]}"
    save_dir = f"./raw_data/{admission_year}/{prn}"
    os.makedirs(save_dir, exist_ok=True)
    
    file_path = f"{save_dir}/{exam_id}.html"
    
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(trimmed_html)
        
    logging.info(f"Saved: {prn} -> Exam {exam_id}")
    return True

async def main():
    # Load Exam IDs (Extracting just the semester 1 IDs for the initial pass)
    try:
        with open(METADATA_FILE, "r") as f:
            metadata = json.load(f)
            # Assuming we test Semester 1 regular exams to verify the PRN first
            # Adjust this list to target specific exams
            exam_ids_to_test = [exam["value"] for exam in metadata.get("semester_1", [])]
    except FileNotFoundError:
        logging.error(f"Could not find {METADATA_FILE}. Exiting.")
        return

    # Setup connection pooling and timeouts
    timeout = ClientTimeout(total=TIMEOUT_SECONDS)
    connector = aiohttp.TCPConnector(limit=CONCURRENCY_LIMIT)
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = []
        
        # Build the queue of tasks
        logging.info(f"Generating PRN target queue from {COUNTER_START} to {COUNTER_END}...")
        for i in range(COUNTER_START, COUNTER_END + 1):
            # Format the 6-digit counter (e.g., 1 -> 000001)
            global_counter = f"{i:06d}"
            prn = f"{TARGET_YEAR}{STREAM_MARKER}{global_counter}"
            
            # Queue up a task for each Exam ID against this PRN
            for exam_id in exam_ids_to_test:
                tasks.append(fetch_and_save(session, semaphore, prn, exam_id))

        logging.info(f"Executing {len(tasks)} requests asynchronously. Press Ctrl+C to abort.")
        
        # Gather executes all tasks concurrently (managed by the semaphore)
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    # Ensure raw_data directory exists
    os.makedirs("./raw_data", exist_ok=True)
    
    try:
        # Use the appropriate event loop policy for Debian/Linux
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("\nGracefully shutting down engine...")