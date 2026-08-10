from typing import List, Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)

def normalize_size(size_str: str) -> str:
    if not size_str:
        return ""
    s = size_str.strip().lower()
    # Map numeric size to standard label (Indian bust/chest measurements to S/M/L)
    num_map = {
        "36": "s",
        "38": "m",
        "40": "l",
        "42": "xl",
        "44": "xxl"
    }
    if s in num_map:
        return num_map[s]
    # Standardize textual names
    name_map = {
        "small": "s",
        "medium": "m",
        "large": "l",
        "extra large": "xl",
        "double extra large": "xxl"
    }
    if s in name_map:
        return name_map[s]
    return s


def validate_retrieval(
    intent: str,
    entities: Dict[str, Any],
    catalog_context: List[Dict[str, Any]]
) -> Tuple[bool, List[Dict[str, Any]], str]:
    """
    Retrieval Quality Layer.
    Ensures that the semantic search results actually match the strict entities extracted (e.g. price limits, size, availability).
    Returns: (is_valid, filtered_catalog, escalation_reason)
    """
    # Non-catalog conversational intents (greetings, general queries, store hours, logistics, policies) do not require catalog items
    if intent in ["greeting", "general_query", "general", "store_info", "logistics", "shipping_exception", "policy", "faq", "other"]:
        return True, catalog_context or [], ""

    if not catalog_context:
        return False, [], "No catalog items found."

    filtered_context = []
    
    for item in catalog_context:
        # 1. Budget filtering
        price = item.get('price', 0)
        budget_max = entities.get('budget_max')
        if budget_max and price > budget_max:
            continue
            
        budget_min = entities.get('budget_min')
        if budget_min and price < budget_min:
            continue
            
        # 2. Availability filtering
        if intent == "availability" and item.get('stock_count', 0) == 0:
            continue

        # 3. Sizing filtering (Finding C2 Resolution)
        requested_size = entities.get('size')
        if requested_size:
            product_sizes = item.get('sizes')
            if product_sizes:
                # Support string sizes separated by commas or lists of strings
                if isinstance(product_sizes, str):
                    product_sizes = [s.strip() for s in product_sizes.split(",") if s.strip()]
                
                product_sizes_lower = [s.lower() for s in product_sizes]
                # If product is Free Size (like a saree), it fits any size request
                if "free size" in product_sizes_lower or "free" in product_sizes_lower:
                    pass
                else:
                    norm_req = normalize_size(requested_size)
                    norm_prod_sizes = [normalize_size(s) for s in product_sizes]
                    if norm_req not in norm_prod_sizes:
                        continue
            else:
                # If product has no sizes specified but a size was strictly requested, skip it
                continue
            
        filtered_context.append(item)
        
    if not filtered_context:
        return False, [], "Found items, but none matched the strict entity criteria (budget/availability/size)."
        
    return True, filtered_context, ""
