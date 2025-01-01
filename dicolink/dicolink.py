import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import logging
import sys

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Target URL
url = "https://www.dicolink.com/motdujour"
source_name = "dicolink"  # Name of the source

try:
    # Fetch the HTML content of the page
    response = requests.get(url)
    response.raise_for_status()
except requests.exceptions.RequestException as e:
    logger.error(f"Error fetching {url}: {e}")
    sys.exit(1)

soup = BeautifulSoup(response.content, 'html.parser')

# Extract the word of the day
word_element = soup.find('h1')
word_of_the_day = word_element.text.strip() if word_element else "Unknown"

# Extract the definitions
definitions_section = soup.find('div', {'class': 'word-module module-definitions'})
definitions = []
if definitions_section:
    sources = definitions_section.find_all('h3', {'class': 'source'})
    definition_lists = definitions_section.find_all('ul')

    for source, definitions_list in zip(sources, definition_lists):
        source_text = source.text.strip()
        definition_items = [li.text.strip() for li in definitions_list.find_all('li')]

        # Exclude sources without definitions or with "pas de définition"
        if not any(def_item.lower() != "pas de définition" for def_item in definition_items):
            continue  # Skip this source

        # Filter out "pas de définition" if other definitions exist
        filtered_definitions = [def_item for def_item in definition_items if def_item.lower() != "pas de définition"]

        if filtered_definitions:
            definitions.append({
                "source": source_text,
                "definitions": filtered_definitions
            })

# Extract the date (if available)
# Assume the date is present in a tag with the class 'date' in the sidebar
date_element = soup.find('div', {'class': 'date'})
date_of_the_day = date_element.text.strip() if date_element else datetime.now().strftime("%B %d, %Y")

# Structure the data
data = {
    "word_of_the_day": word_of_the_day,
    "date": date_of_the_day,
    "source_url": url,
    "definitions": definitions
}

# Optional: Display the data
print(json.dumps(data, indent=4, ensure_ascii=False))

# Save the data to a JSON file
# Create a 'data' folder if it doesn't exist
os.makedirs('data', exist_ok=True)

try:
    # Convert the date to "YYYY-MM-DD" format
    date_obj = datetime.strptime(date_of_the_day, "%B %d, %Y")
    formatted_date = date_obj.strftime("%Y-%m-%d")
except ValueError:
    # If the date format doesn't match, use the current date
    formatted_date = datetime.now().strftime("%Y-%m-%d")

# Filename including the source name
filename = f"data/{source_name}_word_of_the_day_{formatted_date}.json"

# Check if the file already exists
if os.path.exists(filename):
    logger.info(f"The file {filename} already exists. No update necessary.")
else:
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    logger.info(f"Data saved in {filename}")
