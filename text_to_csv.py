import re
from decimal import Decimal
from typing import Optional

def parse_statement_line(line: str) -> Optional[dict]:
    # Basic patterns
    date_pattern = r'(\d{2}/\d{2})'
    amount_pattern = r'([\d.,]+)'
    card_pattern = r'final (\d{4})'
    
    # Try to match a transaction line
    transaction = re.match(f'{date_pattern}\\s+(.+?)\\s+{amount_pattern}$', line)
    if transaction:
        date, description, amount = transaction.groups()
        amount = Decimal(amount.replace('.', '').replace(',', '.'))
        
        # Try to find card number
        card_match = re.search(card_pattern, description)
        card_last4 = card_match.group(1) if card_match else '0000'
        
        return {
            'post_date': date,
            'desc_raw': description,
            'amount_brl': amount,
            'card_last4': card_last4,
            'category': 'MISC',  # Default category
        }
    
    return None  # Return None if line doesn't match expected format

