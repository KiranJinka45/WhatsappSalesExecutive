from google import genai
from google.genai import types
from typing import List, Optional, Dict, Any
import json
import logging
from .config import settings

logger = logging.getLogger(__name__)

def get_client() -> Optional[genai.Client]:
    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY is not set.")
        return None
    try:
        return genai.Client(api_key=settings.GEMINI_API_KEY)
    except Exception as e:
        logger.error(f"Error creating Gemini client: {e}")
        return None

def get_embedding(text: str) -> Optional[List[float]]:
    client = get_client()
    if not client:
        # Fallback or mock embedding if key is missing (for local testing without keys)
        return [0.0] * 768
    try:
        response = client.models.embed_content(
            model="text-embedding-004",
            contents=text
        )
        if response.embeddings:
            return response.embeddings[0].values
    except Exception as e:
        logger.error(f"Failed to fetch embedding: {e}")
    return [0.0] * 768

def classify_intent(message_content: str, history: List[Dict[str, str]] = None) -> str:
    client = get_client()
    if not client:
        return "human_negotiation" # Default safe option if LLM offline

    history_str = ""
    if history:
        for msg in history[-5:]: # Look at last 5 messages for context
            history_str += f"{msg['sender']}: {msg['content']}\n"
    
    prompt = f"""You are an NLU classifier for a clothing retail brand's WhatsApp assistant.
Your job is to classify the user's latest message into exactly ONE of the following 8 intents:

1. product_discovery: Searching for clothes, browsing by categories, colors, pricing, fabrics (e.g., "show sarees", "kurtis under 1000", "any blue silk sarees?").
2. product_info: Asking for specific details about an item, like fabric, washing instructions, length, embroidery type (e.g., "what is the fabric of the first saree?", "is it pure silk?").
3. similar_recommendation: Asking for alternatives or similar designs of a previously discussed item (e.g., "do you have this in blue?", "show me similar patterns").
4. media_request: Asking for videos, real photos, or unboxing clips of the products (e.g., "send full video of this", "can I get real photo of the border?").
5. logistics: Questions about COD availability, shipping fees, delivery times, or tracking (e.g., "COD available?", "how many days to deliver to Hyderabad?", "what is the shipping charge?").
6. availability: Checking if a specific size, color, or item is in stock (e.g., "is XL size available in this?", "is this in stock?").
7. store_info: Asking about physical store location, operating hours, contact info (e.g., "do you have a physical shop?", "where are you located?").
8. human_negotiation: Asking for discounts, wholesale bulk rates, custom styling advice, complaining, or asking to speak with a human agent (e.g., "best price?", "wholesale option?", "want to talk to owner", "let me chat with staff").

Here is the conversation history:
{history_str}

Latest customer message:
"{message_content}"

Respond with ONLY the exact intent name from: product_discovery, product_info, similar_recommendation, media_request, logistics, availability, store_info, human_negotiation. Do not include any other text or punctuation.
"""
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        intent = response.text.strip().lower()
        valid_intents = [
            "product_discovery", "product_info", "similar_recommendation", 
            "media_request", "logistics", "availability", "store_info", "human_negotiation"
        ]
        # Clean up output in case LLM added quotes/markdown
        for valid in valid_intents:
            if valid in intent:
                return valid
        return "human_negotiation"
    except Exception as e:
        logger.error(f"Failed to classify intent: {e}")
        return "human_negotiation"

def generate_reply(
    customer_msg: str, 
    history: List[Dict[str, str]], 
    catalog_context: List[Dict[str, Any]], 
    policies_context: Dict[str, Any]
) -> str:
    """
    Generates a reply grounded strictly in catalog and policy contexts.
    """
    client = get_client()
    if not client:
        return "Thank you for messaging us. One of our sales team representatives will assist you shortly."

    # Format catalog context
    catalog_str = "No matching items found in the catalog."
    if catalog_context:
        items = []
        for item in catalog_context:
            items.append(
                f"- SKU: {item.get('sku')}\n"
                f"  Name: {item.get('name')}\n"
                f"  Price: INR {item.get('price')}\n"
                f"  Color: {item.get('color')}\n"
                f"  Fabric: {item.get('fabric', 'N/A')}\n"
                f"  Sizes Available: {', '.join(item.get('sizes', []))}\n"
                f"  Stock Count: {item.get('stock_count', 0)}\n"
                f"  Description: {item.get('description', 'N/A')}\n"
                f"  Images: {', '.join(item.get('image_urls', []))}\n"
                f"  Videos: {', '.join(item.get('video_urls', []))}\n"
            )
        catalog_str = "\n".join(items)

    # Format policies context
    policies_str = json.dumps(policies_context, indent=2)

    # Format history
    history_str = ""
    for msg in history[-10:]:
        history_str += f"{msg['sender']}: {msg['content']}\n"

    system_instruction = """You are "Closely", an expert AI sales employee for our clothing brand.
You talk to customers on WhatsApp. Your tone is warm, polite, and helpful, typical of a premier clothing boutique.
You must adhere STRICTLY to these guardrails:
1. GROUNDING RULE: You are ONLY allowed to state product facts (price, fabric, size availability, color, stock status) that are directly listed in the "CATALOG CONTEXT" below. 
2. NO HALLUCINATION: If a customer asks about a color, fabric, size, or price not in the CATALOG CONTEXT, do NOT guess. State clearly: "We don't currently have that exact option listed, but let me check if our staff can arrange it for you!" and invite human takeover.
3. PRICING: State prices exactly as given in INR. Never offer discounts or write custom codes unless explicitly instructed in POLICIES CONTEXT.
4. MULTILINGUAL SUPPORT: Respond in the exact language/script mix the customer uses (e.g., Hinglish, Telugu-English, or plain Hindi/English). Do not force them to switch.
5. MEDIA REQUESTS: If image or video URLs are present in the CATALOG CONTEXT, mention them to the customer or display them nicely.

POLICIES CONTEXT (shipping, returns, general FAQ):
{policies_context}

CATALOG CONTEXT (current matching items from database):
{catalog_context}
"""

    prompt = f"""Below is the conversation history and the latest message. Generate a reply.

Conversation history:
{history_str}
Customer: {customer_msg}
AI:"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction.format(
                    policies_context=policies_str,
                    catalog_context=catalog_str
                ),
                temperature=0.2 # Low temperature to prevent hallucinations
            )
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Failed to generate AI response: {e}")
        return "I'm having trouble retrieving details right now. Let me connect you with one of our store managers."
