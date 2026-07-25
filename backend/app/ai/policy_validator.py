from typing import List, Dict, Any, Tuple
import re
import logging

logger = logging.getLogger(__name__)

def validate_reply(
    proposed_reply: str,
    catalog_context: List[Dict[str, Any]],
    policies_context: Dict[str, Any]
) -> Tuple[bool, str, List[str]]:
    """
    Validates the AI's proposed reply against business rules.
    Returns: (is_valid, corrected_reply, violations_list)
    """
    violations = []
    
    # 1. Price Hallucination Check
    # Find all prices mentioned in the reply (e.g., INR 1500, Rs. 1500, ₹1500)
    prices_mentioned_raw = re.findall(r'(?:INR|Rs\.?|₹)\s*([\d,]+(?:\.\d{1,2})?)', proposed_reply, re.IGNORECASE)
    prices_mentioned = [p.replace(',', '') for p in prices_mentioned_raw]
    if prices_mentioned:
        catalog_prices = [str(int(float(item.get('price')))) for item in catalog_context] + [str(item.get('price')) for item in catalog_context]
        for price_str in prices_mentioned:
            # Strip decimal parts if they are .00 or .0 for cleaner integer comparisons
            clean_price = price_str.split('.')[0]
            if clean_price not in catalog_prices and price_str not in catalog_prices:
                # Basic check: could be a total sum, but we flag it if it doesn't match an item
                # For now, just log it as a warning if it doesn't match any individual item
                # A more sophisticated check would parse order totals.
                if len(catalog_context) == 1:
                    violations.append(f"Price {price_str} does not match catalog item price.")
    
    # 2. Stock Check
    # If catalog items are explicitly out of stock but the reply implies they are available
    out_of_stock_items = [item for item in catalog_context if item.get('stock_count', 0) == 0]
    if out_of_stock_items:
        for item in out_of_stock_items:
            # If the reply mentions the item name but doesn't mention "out of stock" or "unavailable"
            if item.get('name', '').lower() in proposed_reply.lower():
                if "out of stock" not in proposed_reply.lower() and "unavailable" not in proposed_reply.lower():
                    violations.append(f"Offered item '{item.get('name')}' which is out of stock.")
    
    if violations:
        disclaimer = "\n\n(Note: Some details above might be incorrect. Let me connect you with our staff to confirm.)"
        return False, proposed_reply + disclaimer, violations
        
    return True, proposed_reply, []
