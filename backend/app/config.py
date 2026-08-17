import os
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Optional

# Dynamic Env Loading based on APP_ENV
app_env = os.getenv("APP_ENV", "development").lower()
env_file_path = f".env.{app_env}" if os.path.exists(f".env.{app_env}") else ".env"

class Settings(BaseSettings):
    APP_ENV: str = "development"
    TESTING: bool = False
    SHADOW_MODE: bool = True
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/closely_db"
    # LLM Provider Keys
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    OPENROUTER_API_KEY: Optional[str] = None
    NVIDIA_API_KEY: Optional[str] = None
    
    # LLM Provider Models
    GEMINI_MODEL: str = "gemini-2.0-flash"
    GROQ_MODEL: str = "llama-3.1-8b-instant"
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENROUTER_MODEL: str = "google/gemini-2.0-flash-001"
    NVIDIA_MODEL: str = "meta/llama-3.1-70b-instruct"

    # Supabase Configuration
    SUPABASE_URL: Optional[str] = None
    SUPABASE_ANON_KEY: Optional[str] = None
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None

    # Additional Integrations
    STRIPE_SECRET_KEY: Optional[str] = None
    STITCH_API_KEY: Optional[str] = None
    FIGMA_ACCESS_TOKEN: Optional[str] = None
    CORS_ORIGINS: Optional[str] = None
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    REDIS_URL: str = "redis://localhost:6379/0"
    WHATSAPP_API_BASE_URL: str = "https://graph.facebook.com"
    META_API_VERSION: str = "v20.0"
    
    # WhatsApp / Meta Webhook Config
    WHATSAPP_PHONE_NUMBER_ID: Optional[str] = None
    WHATSAPP_ACCESS_TOKEN: Optional[str] = None
    WHATSAPP_APP_SECRET: Optional[str] = None
    WHATSAPP_VERIFY_TOKEN: str = "closely_verify_token"
    
    # WasenderAPI Integration Config (for instant QR-code scan testing)
    WASENDER_API_TOKEN: Optional[str] = None
    WASENDER_API_BASE_URL: str = "https://wasenderapi.com/api"
    WASENDER_SESSION_ID: Optional[str] = None
    
    # S3 / Media storage config
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_STORAGE_BUCKET_NAME: Optional[str] = None
    AWS_S3_ENDPOINT_URL: Optional[str] = None

    # Recommendation Ranker Config
    RANKER_RELEVANCE_WEIGHT: float = 0.60
    RANKER_INVENTORY_WEIGHT: float = 0.20
    RANKER_PRIORITY_WEIGHT: float = 0.20

    # Production Monitoring & Alerting
    SENTRY_DSN: Optional[str] = None

    model_config = ConfigDict(
        env_file=env_file_path,
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

def validate_config(s):
    # Fail-fast security validation: Ensure JWT_SECRET is set, secure and not an insecure default placeholder
    if not s.JWT_SECRET or s.JWT_SECRET.strip() in (
        "",
        "PROD_SECURE_JWT_SECRET_KEY_CHANGE_ME_IMMEDIATELY",
        "supersecretjwtkeyforcloselymvp2026!!!",
        "change_me_in_production"
    ) or len(s.JWT_SECRET.strip()) < 32:
        raise ValueError("CRITICAL SECURITY ERROR: JWT_SECRET environment variable is unset, too short (<32 chars), or set to an insecure default placeholder value.")

    # Fail-fast validation for LLM configurations
    if not s.TESTING:
        active_providers = []
        # Check Gemini
        if s.GEMINI_API_KEY and s.GEMINI_API_KEY.strip() not in ("", "placeholder", "YOUR_GEMINI_API_KEY"):
            active_providers.append("gemini")
        # Check Groq
        if s.GROQ_API_KEY and s.GROQ_API_KEY.strip() not in ("", "placeholder", "YOUR_GROQ_API_KEY"):
            active_providers.append("groq")
            # Validate model name format / deprecation
            if s.GROQ_MODEL in ("llama3-8b-8192", "llama3-70b-8192"):
                raise ValueError(f"CRITICAL CONFIGURATION ERROR: GROQ_MODEL is set to decommissioned model '{s.GROQ_MODEL}'. Please update to a valid current model.")
        # Check OpenAI
        if s.OPENAI_API_KEY and s.OPENAI_API_KEY.strip() not in ("", "placeholder", "YOUR_OPENAI_API_KEY"):
            active_providers.append("openai")
        # Check OpenRouter
        if s.OPENROUTER_API_KEY and s.OPENROUTER_API_KEY.strip() not in ("", "placeholder", "YOUR_OPENROUTER_API_KEY"):
            active_providers.append("openrouter")
        # Check NVIDIA
        if s.NVIDIA_API_KEY and s.NVIDIA_API_KEY.strip() not in ("", "placeholder", "YOUR_NVIDIA_API_KEY"):
            active_providers.append("nvidia")

        if not active_providers:
            raise ValueError("CRITICAL CONFIGURATION ERROR: No valid LLM provider API key is configured. At least one of GEMINI_API_KEY, GROQ_API_KEY, OPENAI_API_KEY, OPENROUTER_API_KEY, or NVIDIA_API_KEY must be configured with a valid API key.")

validate_config(settings)



