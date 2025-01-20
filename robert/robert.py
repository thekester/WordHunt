import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import logging
import sys
import time

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RobertScraper:
    def __init__(self):
        self.url = "https://dictionnaire.lerobert.com/mot-du-jour"
        self.source_name = "robert"
        self.data_dir = "data"
        os.makedirs(self.data_dir, exist_ok=True)
        # Création d'une session persistante
        self.session = requests.Session()
        # Définition des en-têtes pour simuler un navigateur
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/115.0.0.0 Safari/537.36'
        })

    def fetch_page(self, retries=3, delay=5):
        """Récupère le contenu de la page avec gestion des erreurs et réessais."""
        for attempt in range(1, retries + 1):
            try:
                response = self.session.get(self.url, timeout=10)
                response.raise_for_status()
                return response.content
            except requests.exceptions.RequestException as e:
                logger.error(f"Tentative {attempt}/{retries} - Erreur lors de la récupération de {self.url}: {e}")
                if attempt < retries:
                    logger.info(f"Nouvelle tentative dans {delay} secondes...")
                    time.sleep(delay)
                else:
                    logger.critical("Nombre maximum de tentatives atteint. Arrêt du script.")
                    sys.exit(1)

    def parse_content(self, html_content):
        """Analyse le contenu HTML pour extraire le mot, ses définitions et la date."""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extraire le mot du jour
        word_element = soup.find('h1')
        word_of_the_day = word_element.text.strip() if word_element else "Inconnu"

        # Extraire les définitions
        definitions = []
        definitions_section = soup.find('section', class_='def')
        if definitions_section:
            # Exemples d'extraction; ajustez selon la structure réelle du HTML
            definition_items = definitions_section.find_all('div', class_='b')
            for item in definition_items:
                word = item.find('b').text.strip() if item.find('b') else ""
                if word:
                    definitions.append(word)

        # Extraire la date (si présente)
        date_element = soup.find('div', class_='date')
        if date_element:
            date_text = date_element.text.strip()
        else:
            # Format alternatif selon la langue du site ; ajustez si nécessaire
            try:
                # Si la date est au format localisé en français, ajustez le format
                date_text = datetime.strptime(date_element.text.strip(), "%d %B %Y").strftime("%B %d, %Y")
            except Exception:
                date_text = datetime.now().strftime("%B %d, %Y")

        return word_of_the_day, definitions, date_text

    def save_data(self, word, definitions, date_text):
        """Sauvegarde les données récupérées dans un fichier JSON."""
        data = {
            "word_of_the_day": word,
            "date": date_text,
            "source_url": self.url,
            "definitions": definitions
        }

        # Conversion de la date pour le nom de fichier
        try:
            date_obj = datetime.strptime(date_text, "%B %d, %Y")
            formatted_date = date_obj.strftime("%Y-%m-%d")
        except ValueError:
            formatted_date = datetime.now().strftime("%Y-%m-%d")

        filename = f"{self.data_dir}/{self.source_name}_word_of_the_day_{formatted_date}.json"

        if os.path.exists(filename):
            logger.info(f"Le fichier {filename} existe déjà. Pas de mise à jour nécessaire.")
        else:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            logger.info(f"Données sauvegardées dans {filename}")

    def scrape(self):
        html_content = self.fetch_page()
        word, definitions, date_text = self.parse_content(html_content)
        self.save_data(word, definitions, date_text)

if __name__ == "__main__":
    scraper = RobertScraper()
    scraper.scrape()
