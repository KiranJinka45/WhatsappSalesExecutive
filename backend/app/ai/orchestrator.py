from typing import List, Dict, Any, Optional
import json
import logging
from .client import generate_content
from .policy_validator import validate_reply

logger = logging.getLogger(__name__)

def _mock_reply_fallback(customer_msg: str, catalog_context: List[Dict[str, Any]], policies_context: Dict[str, Any], is_first_message: bool = True) -> str:
    msg_lower = customer_msg.lower()
    greeting_prefix = "Namaste! 🙏 Welcome to Pushpalatha Silks! " if is_first_message else ""
    
    # 0. Greetings & Casual Pleasantries ("hi", "hello", "hi bro", "hey", "namaste")
    if any(g in msg_lower for g in ["hi", "hello", "hey", "namaste", "good morning", "good evening"]) and not any(w in msg_lower for w in ["saree", "kurti", "dress", "lehenga", "under", "price", "cost", "timing", "open", "location", "shipping", "return"]):
        return "Namaste! 🙏 Welcome to Pushpalatha Silks! How can I help you today?" if is_first_message else "How can I help you today?"

    # 1. Store info & timings request
    if any(w in msg_lower for w in ["open", "hours", "timing", "address", "location", "where is", "map"]):
        addr = policies_context.get("address") or "Main Road, Dharmavaram"
        return f"{greeting_prefix}We are open every day from 10 AM to 9 PM at {addr}."
        
    # 2. Logistics / Shipping / Delivery / COD / Returns
    elif any(w in msg_lower for w in ["cod", "cash on delivery", "cash", "shipping", "delivery", "charge", "days", "time", "return", "exchange", "refund", "policy"]):
        shipping = policies_context.get("shipping") or "We deliver across India in 3-5 days with COD available."
        return f"{greeting_prefix}{shipping}"
        
    # 3. Product Discovery / Inquiry
    elif catalog_context:
        item = catalog_context[0]
        img_url = item.get('image_urls')[0] if item.get('image_urls') and len(item.get('image_urls')) > 0 else ""
        img_suffix = f"\n\nView: {img_url}" if img_url else ""
        return f"{greeting_prefix}We have the {item.get('name')} for ₹{int(float(item.get('price', 0)))}.{img_suffix}"
    else:
        return f"{greeting_prefix}We have a gorgeous collection of silk sarees. What color or budget range are you looking for?"

def generate_reply(
    customer_msg: str, 
    history: Optional[List[Dict[str, str]]] = None, 
    catalog_context: Optional[List[Dict[str, Any]]] = None, 
    policies_context: Optional[Dict[str, Any]] = None,
    detected_language: Optional[str] = None,
    detected_script: Optional[str] = None,
    customer_name: str = "Customer",
    brand_name: str = "Pushpalatha Silks",
    **kwargs
) -> str:
    """
    Generates a reply grounded strictly in catalog and policy contexts.
    Enforces short, natural human WhatsApp messaging and greets ONLY on the first message.
    """
    if history is None:
        history = kwargs.get("history_context") or []
    if catalog_context is None:
        catalog_context = kwargs.get("catalog_ctx") or []
    if policies_context is None:
        policies_context = kwargs.get("policies_ctx") or {}

    # Check if this is the first AI message in the conversation thread
    previous_ai_msgs = [m for m in history if m.get("sender") == "ai"]
    is_first_message = len(previous_ai_msgs) == 0

    if is_first_message:
        greeting_instruction = f"GREETING RULE: This is the VERY FIRST message in the conversation. Warmly greet the customer by name if known (e.g. 'Namaste {customer_name}! 🙏 Welcome to {brand_name}!')."
    else:
        greeting_instruction = f"STRICT NO-RE-GREETING RULE: This is an ONGOING conversation (message count > 1). Do NOT greet the customer. Do NOT say 'Hi', 'Hello', 'Namaste', 'Hi {customer_name}', 'Naa {customer_name}', or repeat any greetings. Jump directly into answering their query."

    # Format catalog context
    catalog_str = f"For general inquiries or greetings, introduce {brand_name} boutique collection of silk sarees (Banarasi, Kanjeevaram, Pattu, Cotton)."
    if catalog_context:
        items = []
        for item in catalog_context[:3]:  # Limit to top 3 items to keep LLM context concise
            img_str = f" | Image: {item.get('image_urls')[0]}" if item.get('image_urls') and len(item.get('image_urls')) > 0 else ""
            items.append(
                f"- Name: {item.get('name')} | Price: ₹{item.get('price')} | Color: {item.get('color')} | Fabric: {item.get('fabric', 'N/A')}{img_str}"
            )
        catalog_str = "\n".join(items)

    # Format policies context
    policies_str = json.dumps(policies_context, indent=2)

    # Format history
    history_str = ""
    for msg in history[-6:]:
        history_str += f"{msg['sender']}: {msg['content']}\n"

    lang_instruction = ""
    if detected_language and detected_script:
        lang_instruction = f"""
7. LANGUAGE & SCRIPT RULE:
- The customer's message has been detected as language: "{detected_language}" and script: "{detected_script}".
- You MUST generate your response matching this exact language and script combination.
- SCRIPT CONSISTENCY: Do NOT mix native script and Latin/English script in the same reply. If the script is "latin", the entire response (including lists, product names, and descriptions) must use ONLY English letters (Latin alphabet). Never output native Unicode characters (such as Telugu/Devanagari script) in a "latin" script response.
- If the language is "te" (Telugu) and script is "latin", reply in natural, clear, and simple Romanized Telugu (e.g. "Namaste andi! Maa daggara cotton sarees levu. Kani silk sarees vunnayi, chusthara?").
- If the language is "hi" (Hindi) and script is "latin", reply in Romanized Hindi/Hinglish (e.g. "Namaste! Hamare paas cotton sarees abhi nahi hain, par silk sarees hain. Kya aap dekhna chahenge?").
- If the script is "native", reply strictly in native regional Unicode characters.
- If English, reply in plain English.
- CRITICAL PRODUCT NAME RULE: Always keep product names (like "Royal Banarasi Silk Saree" or "Peach Chiffon Saree") exactly in English as-is (in Latin script). Do not translate them into regional names (e.g. do not translate "Royal" to "Raju").
- CRITICAL TELUGU QUALITY RULE: When writing in Telugu, use simple, friendly, and natural phrasing. For example: use "saree" or "cheera" for saree, "dhara" or "price" for price, "color" or "rangu" for color, "vundi" or "vunnayi" for available. Keep sentences short and conversational.
"""

    system_instruction = f"""You are "Closely", an expert AI sales assistant for {brand_name} boutique on WhatsApp. on WhatsApp.

CRITICAL FORMAT & LENGTH RULES:
1. SHORT & SIMPLE: Keep your response short, concise, and directly relevant (maximum 1 to 3 short sentences). Never send long paragraphs or walls of text.
2. {greeting_instruction}
3. NO HALLUCINATION & ALTERNATIVES: Only recommend products, prices, colors, and fabrics listed in the CATALOG CONTEXT below. If the exact color or product requested by the customer is not found in the CATALOG CONTEXT, politely state that we don't have that exact match, and then suggest the most similar products that ARE in the CATALOG CONTEXT as alternatives, including their exact image URLs.
4. PRICING: State prices as ₹ in natural sentences. Never mention SKU numbers or internal database IDs.
5. NATURAL HUMAN CHATTING: Write like a real, friendly human store assistant texting on WhatsApp.
6. PRODUCT IMAGES: When recommending, showing, or mentioning products from the CATALOG CONTEXT, you MUST include the exact corresponding Image URL provided in the CATALOG CONTEXT next to the product name. For example:
- "Peach Chiffon Saree: ₹5499. View: https://example.com/peach.jpg"
Never ignore or omit the Image URL. Output it exactly as listed in the CATALOG CONTEXT.
{lang_instruction}

POLICIES CONTEXT:
{policies_str}

CATALOG CONTEXT:
{catalog_str}
"""

    sanitized_msg = customer_msg.replace("</customer_message>", "").replace("<customer_message>", "")

    prompt = f"""{system_instruction}

Conversation history:
{history_str}
Latest customer message:
<customer_message>
{sanitized_msg}
</customer_message>
AI:"""

    try:
        response = generate_content(prompt, strategy="smart")
        raw_reply = response.text.strip() if response.text else ""
        
        # If all LLM providers failed, trigger fallback and suggest manager connection
        if response.provider == "fallback":
            return "Namaste! We are currently experiencing technical difficulties. Let me connect you with a store manager to assist you directly."
            
        if not raw_reply:
            return _mock_reply_fallback(customer_msg, catalog_context, policies_context, is_first_message=is_first_message)
            
        # Run policy validation
        is_valid, final_reply, violations = validate_reply(raw_reply, catalog_context, policies_context)
        
        if not is_valid:
            logger.warning(f"AI reply policy violations: {violations}")
            
        return final_reply
        
    except Exception as e:
        logger.error(f"Failed to generate AI response: {e}")
        return "Let me check that for you right now."
