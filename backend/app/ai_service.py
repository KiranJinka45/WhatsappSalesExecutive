"""
Backwards-compatible import shim.
All AI logic has been refactored into app/ai/ package.
"""
from .ai import (
    get_client, get_embedding, classify_intent, detect_language, extract_entities, 
    validate_retrieval, rank_recommendations, generate_reply, decision_engine, 
    DECISION_ENGINE_VERSION, generate_content, get_image_embedding, transcribe_audio,
    execute_draft_generation_pipeline, route_and_extract_intent, execute_deterministic_catalog_query,
    IntentExtraction, ProductSearchCriteria, GroundedProductResult, DraftGenerationResult
)

