import logging
from typing import List, Optional
from ..config import settings
from google import genai
import groq
import openai

logger = logging.getLogger(__name__)

# Lazy initialized clients
_gemini_client = None
_groq_client = None
_openai_client = None
_openrouter_client = None
_nvidia_client = None

def get_gemini_client() -> Optional[genai.Client]:
    global _gemini_client
    if _gemini_client is None and settings.GEMINI_API_KEY:
        try:
            _gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
        except Exception as e:
            logger.error(f"Error creating Gemini client: {e}")
    return _gemini_client

def get_client() -> Optional[genai.Client]:
    return get_gemini_client()

def get_groq_client():
    global _groq_client
    if _groq_client is None and settings.GROQ_API_KEY:
        try:
            _groq_client = groq.Groq(api_key=settings.GROQ_API_KEY)
        except Exception as e:
            logger.error(f"Error creating Groq client: {e}")
    return _groq_client

def get_openai_client():
    global _openai_client
    if _openai_client is None and settings.OPENAI_API_KEY:
        try:
            _openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        except Exception as e:
            logger.error(f"Error creating OpenAI client: {e}")
    return _openai_client

def get_openrouter_client():
    global _openrouter_client
    if _openrouter_client is None and settings.OPENROUTER_API_KEY:
        try:
            _openrouter_client = openai.OpenAI(
                api_key=settings.OPENROUTER_API_KEY,
                base_url="https://openrouter.ai/api/v1",
            )
        except Exception as e:
            logger.error(f"Error creating OpenRouter client: {e}")
    return _openrouter_client

def get_nvidia_client():
    global _nvidia_client
    if _nvidia_client is None and settings.NVIDIA_API_KEY:
        try:
            _nvidia_client = openai.OpenAI(
                api_key=settings.NVIDIA_API_KEY,
                base_url="https://integrate.api.nvidia.com/v1",
            )
        except Exception as e:
            logger.error(f"Error creating NVIDIA client: {e}")
    return _nvidia_client

import contextvars

# ContextVar to store the last LLM execution metadata
last_llm_meta = contextvars.ContextVar("last_llm_meta", default={})

def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return int(len(text.split()) * 1.3)

class AIResponse:
    def __init__(self, text: str, provider: str = "unknown", model: str = "unknown", input_tokens: int = 0, output_tokens: int = 0, estimated_cost: float = 0.0):
        self.text = text
        self.provider = provider
        self.model = model
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.estimated_cost = estimated_cost

def generate_content(prompt: str, strategy: str = "fast") -> AIResponse:
    """
    Multi-LLM Fallback Generator.
    strategy: 'fast' prefers Groq, 'smart' prefers Gemini/OpenAI.
              Custom strategies 'openrouter' and 'nvidia' prioritize those providers first.
    """
    # Set default metadata
    default_meta = {
        "provider": "fallback",
        "model": "mock",
        "input_tokens": 0,
        "output_tokens": 0,
        "estimated_cost": 0.0
    }
    last_llm_meta.set(default_meta)

    # Determine execution sequence based on strategy
    if strategy == "openrouter":
        providers_to_try = ["openrouter", "nvidia", "groq", "gemini", "openai"]
    elif strategy == "nvidia":
        providers_to_try = ["nvidia", "openrouter", "groq", "gemini", "openai"]
    elif strategy == "fast":
        providers_to_try = ["groq", "gemini", "openai", "openrouter", "nvidia"]
    elif strategy == "smart":
        providers_to_try = ["groq", "gemini", "openai", "openrouter", "nvidia"]
    else:
        providers_to_try = ["groq", "gemini", "openai", "openrouter", "nvidia"]

    for provider in providers_to_try:
        if provider == "groq":
            groq_client = get_groq_client()
            if groq_client:
                try:
                    chat_completion = groq_client.chat.completions.create(
                        messages=[{"role": "user", "content": prompt}],
                        model=settings.GROQ_MODEL,
                    )
                    text = chat_completion.choices[0].message.content
                    prompt_tokens = getattr(chat_completion.usage, "prompt_tokens", 0) or _estimate_tokens(prompt)
                    completion_tokens = getattr(chat_completion.usage, "completion_tokens", 0) or _estimate_tokens(text)
                    cost = (prompt_tokens / 1_000_000) * 0.05 + (completion_tokens / 1_000_000) * 0.08
                    meta = {
                        "provider": "groq",
                        "model": settings.GROQ_MODEL,
                        "input_tokens": prompt_tokens,
                        "output_tokens": completion_tokens,
                        "estimated_cost": cost
                    }
                    last_llm_meta.set(meta)
                    return AIResponse(text, **meta)
                except Exception as e:
                    logger.error(f"Groq failed: {e}. Falling back...")
        
        elif provider == "gemini":
            gemini_client = get_gemini_client()
            if gemini_client:
                try:
                    res = gemini_client.models.generate_content(
                        model=settings.GEMINI_MODEL,
                        contents=prompt
                    )
                    text = res.text
                    prompt_tokens = 0
                    completion_tokens = 0
                    if hasattr(res, "usage_metadata") and res.usage_metadata:
                        prompt_tokens = getattr(res.usage_metadata, "prompt_token_count", 0) or 0
                        completion_tokens = getattr(res.usage_metadata, "candidates_token_count", 0) or 0
                    if not prompt_tokens:
                        prompt_tokens = _estimate_tokens(prompt)
                    if not completion_tokens:
                        completion_tokens = _estimate_tokens(text)
                    cost = (prompt_tokens / 1_000_000) * 0.075 + (completion_tokens / 1_000_000) * 0.30
                    meta = {
                        "provider": "gemini",
                        "model": settings.GEMINI_MODEL,
                        "input_tokens": prompt_tokens,
                        "output_tokens": completion_tokens,
                        "estimated_cost": cost
                    }
                    last_llm_meta.set(meta)
                    return AIResponse(text, **meta)
                except Exception as e:
                    logger.error(f"Gemini failed: {e}. Falling back...")

        elif provider == "openai":
            openai_client = get_openai_client()
            if openai_client:
                try:
                    response = openai_client.chat.completions.create(
                        model=settings.OPENAI_MODEL,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    text = response.choices[0].message.content
                    prompt_tokens = getattr(response.usage, "prompt_tokens", 0) or _estimate_tokens(prompt)
                    completion_tokens = getattr(response.usage, "completion_tokens", 0) or _estimate_tokens(text)
                    cost = (prompt_tokens / 1_000_000) * 0.15 + (completion_tokens / 1_000_000) * 0.60
                    meta = {
                        "provider": "openai",
                        "model": settings.OPENAI_MODEL,
                        "input_tokens": prompt_tokens,
                        "output_tokens": completion_tokens,
                        "estimated_cost": cost
                    }
                    last_llm_meta.set(meta)
                    return AIResponse(text, **meta)
                except Exception as e:
                    logger.error(f"OpenAI failed: {e}. Falling back...")

        elif provider == "openrouter":
            openrouter_client = get_openrouter_client()
            if openrouter_client:
                try:
                    response = openrouter_client.chat.completions.create(
                        model=settings.OPENROUTER_MODEL,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    text = response.choices[0].message.content
                    prompt_tokens = getattr(response.usage, "prompt_tokens", 0) or _estimate_tokens(prompt)
                    completion_tokens = getattr(response.usage, "completion_tokens", 0) or _estimate_tokens(text)
                    # Cost estimated based on Anthropic Claude 3.5 Sonnet on OpenRouter
                    cost = (prompt_tokens / 1_000_000) * 3.00 + (completion_tokens / 1_000_000) * 15.00
                    meta = {
                        "provider": "openrouter",
                        "model": settings.OPENROUTER_MODEL,
                        "input_tokens": prompt_tokens,
                        "output_tokens": completion_tokens,
                        "estimated_cost": cost
                    }
                    last_llm_meta.set(meta)
                    return AIResponse(text, **meta)
                except Exception as e:
                    logger.error(f"OpenRouter failed: {e}. Falling back...")

        elif provider == "nvidia":
            nvidia_client = get_nvidia_client()
            if nvidia_client:
                try:
                    response = nvidia_client.chat.completions.create(
                        model=settings.NVIDIA_MODEL,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    text = response.choices[0].message.content
                    prompt_tokens = getattr(response.usage, "prompt_tokens", 0) or _estimate_tokens(prompt)
                    completion_tokens = getattr(response.usage, "completion_tokens", 0) or _estimate_tokens(text)
                    # Cost estimated based on LLaMA 3.1 70B on NVIDIA
                    cost = (prompt_tokens / 1_000_000) * 0.70 + (completion_tokens / 1_000_000) * 0.90
                    meta = {
                        "provider": "nvidia",
                        "model": settings.NVIDIA_MODEL,
                        "input_tokens": prompt_tokens,
                        "output_tokens": completion_tokens,
                        "estimated_cost": cost
                    }
                    last_llm_meta.set(meta)
                    return AIResponse(text, **meta)
                except Exception as e:
                    logger.error(f"NVIDIA failed: {e}. Falling back...")

    logger.error("All LLM providers failed to generate content.")
    return AIResponse("", **default_meta)

def get_embedding(text: str) -> Optional[List[float]]:
    # We can try OpenAI first for embeddings, or fallback to Gemini
    openai_client = get_openai_client()
    if openai_client:
        try:
            response = openai_client.embeddings.create(
                input=text,
                model="text-embedding-3-small"
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"OpenAI embedding failed: {e}. Falling back to Gemini...")
            
    client = get_gemini_client()
    if not client:
        return [0.0] * 768
    try:
        response = client.models.embed_content(
            model="gemini-embedding-001",
            contents=text
        )
        if response.embeddings:
            return response.embeddings[0].values
    except Exception as e:
        logger.error(f"Failed to fetch embedding: {e}")
    return [0.0] * 768

def get_image_embedding(image_bytes: bytes) -> Optional[List[float]]:
    """
    Generates a multimodal embedding for image bytes using gemini-embedding-2.
    """
    client = get_gemini_client()
    if not client:
        logger.error("Gemini client not initialized for image embedding.")
        return [0.0] * 3072
    try:
        from google.genai import types
        part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
        response = client.models.embed_content(
            model="gemini-embedding-2",
            contents=part
        )
        if response.embeddings:
            return response.embeddings[0].values
    except Exception as e:
        logger.error(f"Failed to fetch image embedding: {e}")
    return [0.0] * 3072

def transcribe_audio(audio_bytes: bytes, mime_type: str = "audio/ogg") -> str:
    """
    Transcribes audio bytes to text with triple-redundancy:
    1. Groq Whisper (fast and free/cheap)
    2. OpenAI Whisper
    3. Gemini 2.0 Flash (native multimodal fallback)
    """
    import tempfile
    import os

    # Determine extension
    ext = ".ogg"
    if "wav" in mime_type:
        ext = ".wav"
    elif "mp3" in mime_type:
        ext = ".mp3"
    elif "m4a" in mime_type:
        ext = ".m4a"

    # Write audio bytes to temporary file for Whisper APIs
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        # 1. Try Groq Whisper
        groq_client = get_groq_client()
        if groq_client:
            try:
                with open(tmp_path, "rb") as f:
                    res = groq_client.audio.transcriptions.create(
                        model="whisper-large-v3",
                        file=f
                    )
                if res.text:
                    logger.info("Audio transcription succeeded via Groq Whisper.")
                    return res.text.strip()
            except Exception as e:
                logger.warning(f"Groq Whisper transcription failed: {e}. Trying OpenAI...")

        # 2. Try OpenAI Whisper
        openai_client = get_openai_client()
        if openai_client:
            try:
                with open(tmp_path, "rb") as f:
                    res = openai_client.audio.transcriptions.create(
                        model="whisper-1",
                        file=f
                    )
                if res.text:
                    logger.info("Audio transcription succeeded via OpenAI Whisper.")
                    return res.text.strip()
            except Exception as e:
                logger.warning(f"OpenAI Whisper transcription failed: {e}. Trying Gemini multimodal fallback...")

        # 3. Try Gemini multimodal fallback
        gemini_client = get_gemini_client()
        if gemini_client:
            try:
                from google.genai import types
                part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
                res = gemini_client.models.generate_content(
                    model="models/gemini-2.0-flash",
                    contents=[
                        part,
                        "Please transcribe this voice message precisely into text. Output only the transcript, nothing else. If it is in Romanized Telugu or Hinglish, write exactly what they said in Romanized English script. If in native script, write in native script."
                    ]
                )
                if res.text:
                    logger.info("Audio transcription succeeded via Gemini multimodal.")
                    return res.text.strip()
            except Exception as e:
                logger.error(f"Gemini multimodal transcription failed: {e}")

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    raise ValueError("All speech-to-text engines failed to transcribe the audio.")

