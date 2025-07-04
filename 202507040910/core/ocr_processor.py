"""
OCR-Verarbeitung für PDFs
"""
import os
import re
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import tempfile
import logging
import time

# Logger für dieses Modul
logger = logging.getLogger(__name__)


class OCRProcessor:
    """Führt OCR auf PDF-Dateien aus und extrahiert Text"""

    def __init__(self):
        # Versuche Tesseract zu finden
        self._setup_tesseract()

    def _setup_tesseract(self):
        """Konfiguriert Tesseract OCR"""
        # Standard-Pfade für Tesseract auf Windows
        tesseract_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            r"C:\Users\%USERNAME%\AppData\Local\Tesseract-OCR\tesseract.exe"
        ]

        for path in tesseract_paths:
            expanded_path = os.path.expandvars(path)
            if os.path.exists(expanded_path):
                pytesseract.pytesseract.tesseract_cmd = expanded_path
                logger.debug(f"Tesseract gefunden: {expanded_path}")
                return

        # Wenn nicht gefunden, hoffen wir dass es im PATH ist
        logger.warning("Tesseract nicht in Standard-Pfaden gefunden. Stelle sicher, dass es installiert ist.")

    def _preprocess_image_for_ocr(self, image: Image.Image) -> Image.Image:
        """Bereitet ein Bild für eine bessere OCR-Erkennung vor."""
        # Konvertiere zu Graustufen für bessere Kontraste
        return image.convert('L')

    def extract_text_from_pdf(self, pdf_path: str, language: str = 'deu') -> str:
        """
        Extrahiert Text aus einer PDF-Datei mittels OCR mit Vorverarbeitung
        """
        try:
            # WICHTIG: Normalisiere den Pfad für Windows
            pdf_path = os.path.normpath(pdf_path)
            
            # Prüfe ob Datei existiert
            if not os.path.exists(pdf_path):
                logger.error(f"PDF-Datei nicht gefunden: {pdf_path}")
                return ""
            
            # Warte kurz, falls Datei noch geschrieben wird
            max_retries = 3
            for i in range(max_retries):
                try:
                    # Versuche die Datei zu öffnen um sicherzustellen, dass sie nicht gesperrt ist
                    with open(pdf_path, 'rb') as f:
                        # Lese nur den Header um zu prüfen ob es eine gültige PDF ist
                        header = f.read(4)
                        if header != b'%PDF':
                            logger.error(f"Keine gültige PDF-Datei: {pdf_path}")
                            return ""
                    break
                except Exception as e:
                    if i < max_retries - 1:
                        logger.warning(f"Datei noch gesperrt, warte... ({i+1}/{max_retries})")
                        time.sleep(1)
                    else:
                        logger.error(f"Datei konnte nicht geöffnet werden: {e}")
                        return ""
            
            logger.debug(f"Starte OCR für: {pdf_path}")

            # Konvertiere PDF zu Bildern
            with tempfile.TemporaryDirectory() as temp_dir:
                poppler_path = os.path.join(os.path.dirname(__file__), '..', 'poppler', 'bin')
                poppler_path = os.path.normpath(poppler_path)
                
                # Prüfe ob Poppler existiert
                if not os.path.exists(poppler_path):
                    logger.error(f"Poppler nicht gefunden in: {poppler_path}")
                    return ""
                
                images = convert_from_path(pdf_path, dpi=300, poppler_path=poppler_path)

                all_text = []
                for i, image in enumerate(images):
                    logger.debug(f"OCR auf Seite {i+1}/{len(images)}")
                    # Wende Bildvorverarbeitung an
                    preprocessed_image = self._preprocess_image_for_ocr(image)
                    # OCR auf jeder Seite
                    text = pytesseract.image_to_string(preprocessed_image, lang=language)
                    all_text.append(f"--- Seite {i+1} ---\n{text}")

                result_text = "\n\n".join(all_text)
                logger.info(f"OCR abgeschlossen für {os.path.basename(pdf_path)}: {len(result_text)} Zeichen extrahiert")
                return result_text

        except Exception as e:
            logger.error(f"Fehler bei OCR für {pdf_path}: {e}", exc_info=True)
            return ""

    def extract_text_from_zone(self, pdf_path: str, page_num: int,
                              zone: Tuple[int, int, int, int],
                              language: str = 'deu') -> str:
        """
        Extrahiert Text aus einer bestimmten Zone einer PDF-Seite mit Bildvorverarbeitung.
        """
        try:
            # WICHTIG: Normalisiere den Pfad für Windows
            pdf_path = os.path.normpath(pdf_path)
            
            # Prüfe ob Datei existiert
            if not os.path.exists(pdf_path):
                logger.error(f"PDF-Datei nicht gefunden für Zone-OCR: {pdf_path}")
                return ""
            
            logger.debug(f"OCR-Zone-Extraktion: {pdf_path}, Seite {page_num}, Zone {zone}")

            # Konvertiere spezifische Seite
            poppler_path = os.path.join(os.path.dirname(__file__), '..', 'poppler', 'bin')
            poppler_path = os.path.normpath(poppler_path)
            
            images = convert_from_path(pdf_path, dpi=300,
                                     first_page=page_num, last_page=page_num, poppler_path=poppler_path)

            if not images:
                logger.warning(f"Keine Bilder aus PDF-Seite {page_num} konvertiert")
                return ""

            image = images[0]

            # Schneide Zone aus
            x, y, w, h = zone
            cropped = image.crop((x, y, x + w, y + h))

            # Wende Bildvorverarbeitung an
            preprocessed_cropped = self._preprocess_image_for_ocr(cropped)

            # OCR auf vorverarbeiteter Zone mit optimierter Konfiguration
            custom_config = r'--oem 3 --psm 6'
            text = pytesseract.image_to_string(preprocessed_cropped, lang=language, config=custom_config)
            result = text.strip()

            logger.debug(f"Zone-OCR Ergebnis: '{result[:50]}...' ({len(result)} Zeichen)")
            return result

        except Exception as e:
            logger.error(f"Fehler bei Zone OCR für {os.path.basename(pdf_path)}, Seite {page_num}: {e}", exc_info=True)
            return ""