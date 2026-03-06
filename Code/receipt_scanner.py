import re
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def is_digital_pdf(filepath):
    """Prueft ob ein PDF digital erstellten Text enthaelt (nicht gescannt)."""
    try:
        import pdfplumber
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages[:2]:
                text = page.extract_text() or ''
                if len(text.strip()) > 30:
                    return True
        return False
    except Exception as e:
        logger.warning(f"PDF-Typ-Erkennung fehlgeschlagen: {e}")
        return False


def extract_text_digital(filepath):
    """Extrahiert Text aus digital erstelltem PDF mittels pdfplumber."""
    import pdfplumber
    texts = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''
            texts.append(text)
    return '\n'.join(texts)


def extract_text_ocr(filepath):
    """Extrahiert Text aus gescanntem PDF mittels Tesseract OCR."""
    from pdf2image import convert_from_path
    import pytesseract

    images = convert_from_path(filepath, dpi=300)
    texts = []
    for img in images:
        text = pytesseract.image_to_string(img, lang='deu')
        texts.append(text)
    return '\n'.join(texts)


# Regex-Patterns fuer gaengige deutsche Kassenbon-Formate

# Format 1: "PRODUKT NAME    1,99 A" (2+ Leerzeichen, optionaler Steuer-Buchstabe)
PATTERN_SIMPLE = re.compile(
    r'^(.+?)\s{2,}(\d+[,.]\d{2})\s*([A-D])?\s*\*?\s*$'
)

# Format 2: "2 x PRODUKT    3,98 A"  oder  "2x PRODUKT    3,98 A"
PATTERN_MULTI = re.compile(
    r'^(\d+)\s*[xX×]\s+(.+?)\s{2,}(\d+[,.]\d{2})\s*([A-D])?\s*\*?\s*$'
)

# Format 3: "2 PRODUKT  0,99  1,98 A"
PATTERN_QTY_UNIT_TOTAL = re.compile(
    r'^(\d+)\s+(.+?)\s{2,}(\d+[,.]\d{2})\s+(\d+[,.]\d{2})\s*([A-D])?\s*\*?\s*$'
)

# Format 4 (REWE-Style): "PRODUKT NAME 1,99 B" (1+ Leerzeichen, Steuer-Buchstabe zwingend)
PATTERN_TAX_LETTER = re.compile(
    r'^(.+?)\s+(\d+[,.]\d{2})\s+([A-D])\s*\*?\s*$'
)

# Mengen-Unterzeile: "2 Stk x 1,19" (modifiziert das vorherige Produkt)
PATTERN_SUBLINE_QTY = re.compile(
    r'^\s*(\d+)\s+(?:Stk|Stck|Stueck|St\.?)\s*[xX×]\s*(\d+[,.]\d{2})\s*$', re.I
)

# Datum-Patterns
DATE_PATTERNS = [
    re.compile(r'(?:Datum|Date)\s*[:.]?\s*(\d{2})[./](\d{2})[./](\d{4})', re.I),
    re.compile(r'(\d{2})[./](\d{2})[./](\d{4})'),  # DD.MM.YYYY
    re.compile(r'(\d{2})[./](\d{2})[./](\d{2})'),    # DD.MM.YY
]

# Gesamtsumme-Patterns (Reihenfolge = Prioritaet)
TOTAL_PATTERNS = [
    # Prioritaet 1: SUMME-Zeile (zuverlaessigste Quelle)
    re.compile(r'(?:SUMME|TOTAL|ZU ZAHLEN)\s*(?:EUR|€)?\s*[:=]?\s*(\d+[,.]\d{2})', re.I),
    # Prioritaet 2: Geg./Gegeben (Bezahlbetrag)
    re.compile(r'(?:Geg\.|Gegeben|\bBAR\b|\bEC\b|\bKARTE\b|\bVISA\b|MASTERCARD|GIROCARD)\s.*?(\d+[,.]\d{2})', re.I),
    # Prioritaet 3: GESAMTBETRAG — letzter Preis auf der Zeile (Brutto)
    re.compile(r'(?:GESAMT|GESAMTBETRAG|BETRAG)\s+.*(\d+[,.]\d{2})\s*$', re.I),
]

# Marktname-Patterns
STORE_PATTERNS = [
    re.compile(r'(REWE|EDEKA|ALDI|LIDL|PENNY|NETTO|KAUFLAND|DM|ROSSMANN|NORMA|REAL|HIT|GLOBUS|NAHKAUF|TEGUT|FAMILA|COMBI|MARKTKAUF)', re.I),
]

# Zeilen die keine Produkte sind
SKIP_PATTERNS = [
    re.compile(r'^\s*$'),
    re.compile(r'^[-=_*]{3,}'),
    re.compile(r'(SUMME|TOTAL|GESAMT|MWST|UST|STEUER|STEUERN|NETTO|BRUTTO|ZWISCHENSUMME)', re.I),
    re.compile(r'(BAR\b|EC\-?KARTE|KREDITKARTE|VISA|MASTERCARD|GIROCARD|KARTENZAHLUNG|RUECKGELD|GEGEBEN|GEG\.)', re.I),
    re.compile(r'(VIELEN DANK|DANKE|BELEG|QUITTUNG|KASSENBON|KASSENZETTEL|KUNDENBELEG)', re.I),
    re.compile(r'(FILIALE|MARKT\s*:|KASSE\s*:|BEDIENER|BONNR|BON\-?NR|BELEG\-?NR|TR\.?\s*NR)', re.I),
    re.compile(r'(ADRESSE|STR\.|STRASSE|PLZ|TELEFON|TEL[\.\)]|FAX|WWW\.|HTTP)', re.I),
    re.compile(r'(STEUERNUMMER|ST\.?\s*NR|UST\.?\s*ID|UID\s*NR|IDENT)', re.I),
    re.compile(r'^\s*\d{1,2}[./]\d{1,2}[./]\d{2,4}\s+\d{1,2}:\d{2}', re.I),
    re.compile(r'^\s*(EUR|€)\s*$', re.I),
    re.compile(r'(PFAND|LEERGUT|EINWEG|MEHRWEG)\s*[-]?\s*\d', re.I),
    re.compile(r'(TSE-|TERMINAL|TRACE|GENEHMIGUNGS|VU-NR|POS-INFO|SERIEN)', re.I),
    re.compile(r'(BONUS|COUPON|GUTHABEN|GESAMMELT|SAMMLE|VORTEILE|AKTIVIEREN)', re.I),
    re.compile(r'(BELASTUNG|BANKARBEITSTAG|ZAHLUNG\s+ERFOLGT)', re.I),
    re.compile(r'(BEZAHLUNG|PT\s+PAY|REWE\s+PAY|APPLE\s+PAY|GOOGLE\s+PAY)', re.I),
    re.compile(r'^[A-D]=\s*\d+', re.I),  # Steuer-Aufschluesselung: "A= 19,0% ..."
    re.compile(r'^\s*NR\.?\s*[#\d]', re.I),  # Kartennummer: "Nr. ###...1114"
    re.compile(r'(KEINE\s+RABATTE|GEKENNZEICHNETE)', re.I),
    re.compile(r'(FRAGE\b|ANTWORTEN\s+FINDEST)', re.I),
    re.compile(r'^\s*Datum\s*:', re.I),
    re.compile(r'^\s*Uhrzeit\s*:', re.I),
    re.compile(r'^\s*Betrag\s', re.I),
    re.compile(r'(AS-ZEIT|REWE\s*:)', re.I),
]


def _parse_price(price_str):
    """Konvertiert deutschen Preisstring (1,99) in float."""
    return float(price_str.replace(',', '.'))


def _should_skip_line(line):
    """Prueft ob eine Zeile uebersprungen werden soll (keine Produktzeile)."""
    for pattern in SKIP_PATTERNS:
        if pattern.search(line):
            return True
    return False


def parse_receipt_text(text):
    """Parst Kassenbon-Text und extrahiert Markt, Datum, Produkte und Summe."""
    lines = text.split('\n')
    items = []
    store_name = None
    receipt_date = None
    total_amount = None

    # Marktname suchen (in den ersten 10 Zeilen)
    for line in lines[:10]:
        for pattern in STORE_PATTERNS:
            m = pattern.search(line)
            if m:
                store_name = m.group(1).upper()
                break
        if store_name:
            break

    # Datum suchen
    for line in lines:
        for pattern in DATE_PATTERNS:
            m = pattern.search(line)
            if m:
                day, month, year = m.group(1), m.group(2), m.group(3)
                if len(year) == 2:
                    year = '20' + year
                try:
                    receipt_date = f"{year}-{month}-{day}"
                    datetime.strptime(receipt_date, '%Y-%m-%d')
                except ValueError:
                    receipt_date = None
                    continue
                break
        if receipt_date:
            break

    # Gesamtsumme suchen (stoppt beim ersten Treffer)
    found_total = False
    for line in lines:
        if found_total:
            break
        for pattern in TOTAL_PATTERNS:
            m = pattern.search(line)
            if m:
                total_amount = _parse_price(m.group(1))
                found_total = True
                break

    # Produkte extrahieren
    for line in lines:
        line = line.strip()
        if not line or _should_skip_line(line):
            continue

        item = None

        # Mengen-Unterzeile: "2 Stk x 1,19" → vorheriges Produkt aktualisieren
        m = PATTERN_SUBLINE_QTY.match(line)
        if m and items:
            qty = int(m.group(1))
            unit_price = _parse_price(m.group(2))
            items[-1]['quantity'] = qty
            items[-1]['unit_price'] = unit_price
            continue

        # Format 3: "2 PRODUKT  0,99  1,98 A"
        m = PATTERN_QTY_UNIT_TOTAL.match(line)
        if m:
            item = {
                'raw_name': m.group(2).strip(),
                'quantity': int(m.group(1)),
                'unit_price': _parse_price(m.group(3)),
                'total_price': _parse_price(m.group(4)),
                'tax_category': m.group(5) or None,
            }

        # Format 2: "2 x PRODUKT    3,98 A"
        if not item:
            m = PATTERN_MULTI.match(line)
            if m:
                qty = int(m.group(1))
                total = _parse_price(m.group(3))
                item = {
                    'raw_name': m.group(2).strip(),
                    'quantity': qty,
                    'unit_price': round(total / qty, 2) if qty > 0 else total,
                    'total_price': total,
                    'tax_category': m.group(4) or None,
                }

        # Format 1: "PRODUKT NAME    1,99 A" (2+ Leerzeichen)
        if not item:
            m = PATTERN_SIMPLE.match(line)
            if m:
                name = m.group(1).strip()
                if len(name) >= 2:
                    price = _parse_price(m.group(2))
                    item = {
                        'raw_name': name,
                        'quantity': 1,
                        'unit_price': price,
                        'total_price': price,
                        'tax_category': m.group(3) or None,
                    }

        # Format 4 (REWE-Style): "PRODUKT NAME 1,99 B" (1+ Leerzeichen, Steuer-Buchstabe)
        if not item:
            m = PATTERN_TAX_LETTER.match(line)
            if m:
                name = m.group(1).strip()
                if len(name) >= 2:
                    price = _parse_price(m.group(2))
                    item = {
                        'raw_name': name,
                        'quantity': 1,
                        'unit_price': price,
                        'total_price': price,
                        'tax_category': m.group(3) or None,
                    }

        if item:
            items.append(item)

    return {
        'store_name': store_name,
        'receipt_date': receipt_date,
        'total_amount': total_amount,
        'items': items,
    }


def match_products(items, grocy_products, mappings_dict, threshold=70):
    """Matcht Bon-Produkte mit Grocy-Produkten.

    1. Gelernte Zuordnungen (exakter Name-Match)
    2. Fuzzy-Match mit rapidfuzz (token_sort_ratio)
    """
    from rapidfuzz import fuzz

    grocy_names = [(p['id'], p['name']) for p in grocy_products]

    for item in items:
        raw = item['raw_name'].upper().strip()

        # 1. Gelernte Zuordnung (exakt)
        mapping = mappings_dict.get(raw)
        if mapping:
            item['matched_product_id'] = mapping['grocy_product_id']
            item['matched_product_name'] = mapping['grocy_product_name']
            item['match_score'] = 100
            item['match_source'] = 'learned'
            continue

        # 2. Fuzzy-Match
        best_score = 0
        best_id = None
        best_name = None
        for pid, pname in grocy_names:
            score = fuzz.token_sort_ratio(raw, pname.upper())
            if score > best_score:
                best_score = score
                best_id = pid
                best_name = pname

        if best_score >= threshold:
            item['matched_product_id'] = best_id
            item['matched_product_name'] = best_name
            item['match_score'] = round(best_score, 1)
            item['match_source'] = 'fuzzy'
        else:
            item['matched_product_id'] = None
            item['matched_product_name'] = None
            item['match_score'] = round(best_score, 1) if best_score > 0 else 0
            item['match_source'] = 'none'

    return items


def process_receipt(filepath, grocy_products, mappings_dict, threshold=70):
    """Komplette Pipeline: Erkennung → Extraktion → Parsing → Matching."""
    filename = os.path.basename(filepath)

    # Typ erkennen und Text extrahieren
    try:
        if is_digital_pdf(filepath):
            extraction_method = 'digital'
            raw_text = extract_text_digital(filepath)
        else:
            extraction_method = 'ocr'
            raw_text = extract_text_ocr(filepath)
    except Exception as e:
        logger.error(f"Textextraktion fehlgeschlagen fuer {filename}: {e}")
        return {
            'filename': filename,
            'filepath': filepath,
            'status': 'error',
            'extraction_method': None,
            'error_message': f"Textextraktion fehlgeschlagen: {e}",
            'raw_text': None,
            'parsed': None,
            'items': [],
        }

    if not raw_text or len(raw_text.strip()) < 10:
        return {
            'filename': filename,
            'filepath': filepath,
            'status': 'error',
            'extraction_method': extraction_method,
            'error_message': 'Kein Text extrahiert',
            'raw_text': raw_text,
            'parsed': None,
            'items': [],
        }

    # Parsen
    parsed = parse_receipt_text(raw_text)

    # Matchen
    items = match_products(
        parsed['items'], grocy_products, mappings_dict, threshold=threshold
    )

    return {
        'filename': filename,
        'filepath': filepath,
        'status': 'pending_review',
        'extraction_method': extraction_method,
        'error_message': None,
        'raw_text': raw_text,
        'parsed': parsed,
        'items': items,
    }


def scan_receipt_folder(folder_path, grocy_products, mappings_dict, threshold=70):
    """Scannt einen Ordner nach neuen PDF-Dateien und verarbeitet sie."""
    from database import receipt_filepath_exists, save_receipt, save_receipt_items

    if not os.path.isdir(folder_path):
        logger.warning(f"Kassenbon-Ordner existiert nicht: {folder_path}")
        return []

    results = []
    for fname in os.listdir(folder_path):
        if not fname.lower().endswith('.pdf'):
            continue

        filepath = os.path.join(folder_path, fname)

        if receipt_filepath_exists(filepath):
            continue

        logger.info(f"Verarbeite Kassenbon: {fname}")
        try:
            result = process_receipt(filepath, grocy_products, mappings_dict, threshold)

            receipt_id = save_receipt(
                filename=result['filename'],
                filepath=result['filepath'],
                status=result['status'],
                extraction_method=result['extraction_method'],
                store_name=result['parsed']['store_name'] if result['parsed'] else None,
                receipt_date=result['parsed']['receipt_date'] if result['parsed'] else None,
                total_amount=result['parsed']['total_amount'] if result['parsed'] else None,
                raw_text=result['raw_text'],
                error_message=result['error_message'],
            )

            if result['items']:
                save_receipt_items(receipt_id, result['items'])

            result['receipt_id'] = receipt_id
            results.append(result)
        except Exception as e:
            logger.error(f"Fehler bei Verarbeitung von {fname}: {e}")

    return results
