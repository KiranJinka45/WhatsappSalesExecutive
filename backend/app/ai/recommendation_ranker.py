from typing import List, Dict, Any
import logging
from ..config import settings

logger = logging.getLogger(__name__)

def rank_recommendations(
    filtered_catalog: List[Dict[str, Any]],
    weights: Dict[str, float] = None
) -> List[Dict[str, Any]]:
    """
    Recommendation Ranker.
    Scores products based on multiple signals to drive business outcomes.
    """
    if not filtered_catalog:
        return []

    if weights is None:
        weights = {
            "relevance": settings.RANKER_RELEVANCE_WEIGHT,
            "inventory": settings.RANKER_INVENTORY_WEIGHT,
            "priority": settings.RANKER_PRIORITY_WEIGHT
        }

    ranked_items = []
    
    # We assume filtered_catalog comes in order of semantic relevance (highest first)
    for i, item in enumerate(filtered_catalog):
        # Relevance score: 1.0 for first item, decreasing linearly
        relevance_score = max(0, 1.0 - (i * 0.1))
        
        # Inventory score: cap at 50 for max score, normalize to 0-1
        stock = item.get('stock_count', 0)
        inventory_score = min(1.0, stock / 50.0)
        
        # Priority score: High margin or merchant priority. 
        # For MVP, we will extract 'priority' from item metadata if it exists, else 0.5
        priority_score = item.get('merchant_priority', 0.5)
        
        total_score = (
            (relevance_score * weights["relevance"]) +
            (inventory_score * weights["inventory"]) +
            (priority_score * weights["priority"])
        )
        
        item['ranking_score'] = total_score
        ranked_items.append(item)
        
    # Sort descending by total_score
    ranked_items.sort(key=lambda x: x['ranking_score'], reverse=True)
    
    return ranked_items
