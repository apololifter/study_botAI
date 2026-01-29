import io
import re
import requests
from pypdf import PdfReader
from bs4 import BeautifulSoup
from src.utils import logger

class ContentProcessor:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def extract_text_from_pdf(self, file_bytes: bytes) -> str:
        """Extracts text from a PDF file in memory."""
        try:
            pdf_file = io.BytesIO(file_bytes)
            reader = PdfReader(pdf_file)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            logger.error(f"Error extracting PDF text: {e}")
            return ""

    def extract_text_from_url(self, url: str) -> str:
        """Fetches and extracts text from a URL (handling PDF detection)."""
        try:
            response = requests.get(url, headers=self.headers, timeout=20)
            response.raise_for_status()
            
            content_type = response.headers.get('Content-Type', '').lower()
            
            # Si es un PDF, procesarlo como tal
            if 'application/pdf' in content_type or url.endswith('.pdf'):
                logger.info("URL detected as PDF. Processing binary content...")
                return self.extract_text_from_pdf(response.content)

            # Si es web normal, usar BeautifulSoup
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove scripts and styles
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            
            text = soup.get_text()
            
            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            return text
        except Exception as e:
            logger.error(f"Error fetching URL {url}: {e}")
            return ""

    def find_url_in_text(self, text: str) -> str:
        """Finds the first URL in a string."""
        url_regex = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s]*'
        match = re.search(url_regex, text)
        return match.group(0) if match else ""
