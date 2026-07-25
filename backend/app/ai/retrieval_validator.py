from typing import List, Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)

def validate_retrieval(
    intent: str,
    entities: Dict[str, Any],
    catalog_context: List[Dict[str, Any]]
) -> Tuple[bool, List[Dict[str, Any]], str]:
    """
    Retrieval Quality Layer.
    Ensures that the semantic search results actually match the strict entities extracted (e.g. price limits, availability).
    Returns: (is_valid, filtered_catalog, escalation_reason)
    """
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
            
        filtered_context.append(item)
        
    if not filtered_context:
        return False, [], "Found items, but none matched the strict entity criteria (budget/availability)."
        
    return True, filtered_context, ""
