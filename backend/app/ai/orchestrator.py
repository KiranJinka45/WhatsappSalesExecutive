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
        return f"{greeting_prefix}We have the {item.get('name')} for ₹{int(float(item.get('price', 0)))}. Would you like to see pictures?"
        
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
        greeting_instruction = f"GREETING RULE: This is the VERY FIRST message in the conversation. Warmly greet the customer by name if known (e.g. 'Namaste {customer_name}! 🙏 Welcome to Pushpalatha Silks!')."
    else:
        greeting_instruction = f"STRICT NO-RE-GREETING RULE: This is an ONGOING conversation (message count > 1). Do NOT greet the customer. Do NOT say 'Hi', 'Hello', 'Namaste', 'Hi {customer_name}', 'Naa {customer_name}', or repeat any greetings. Jump directly into answering their query."

    # Format catalog context
    catalog_str = "For general inquiries or greetings, introduce Pushpalatha Silks boutique collection of silk sarees (Banarasi, Kanjeevaram, Pattu, Cotton)."
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
- If the language is "te" (Telugu) and script is "latin", reply in Romanized Telugu (Telugu written in the Latin alphabet, e.g. "ee saree price Rs. 4500 andi...").
- If the language is "hi" (Hindi) and script is "latin", reply in Romanized Hindi/Hinglish (e.g. "is saree ki price Rs. 4500 hai...").
- If the language is "kn" (Kannada) and script is "latin", reply in Romanized Kannada.
- If the language is "ta" (Tamil) and script is "latin", reply in Romanized Tamil.
- If the script is "native", reply strictly in native regional Unicode characters.
- If English, reply in plain English.
"""

    system_instruction = f"""You are "Closely", an expert AI sales assistant for Pushpalatha Silks boutique on WhatsApp.

CRITICAL FORMAT & LENGTH RULES:
1. SHORT & SIMPLE: Keep your response short, concise, and directly relevant (maximum 1 to 3 short sentences). Never send long paragraphs or walls of text.
2. {greeting_instruction}
3. NO HALLUCINATION: Only state prices, colors, fabrics, and availability listed in CATALOG CONTEXT below. If not found, say cleanly: "We don't have that exact option right now, but I can check with our team for you!"
4. PRICING: State prices as ₹ in natural sentences. Never mention SKU numbers or internal database IDs.
5. NATURAL HUMAN CHATTING: Write like a real, friendly human store assistant texting on WhatsApp.
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
