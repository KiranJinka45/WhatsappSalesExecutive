import pytest
import unittest.mock
from unittest.mock import patch, MagicMock
from app.ai.client import generate_content, last_llm_meta

def test_groq_timeout_falls_back_to_gemini():
    """
    Test that when Groq times out, the system falls back to Gemini successfully.
    """
    # 1. Mock Groq client to raise an exception
    mock_groq = MagicMock()
    mock_groq.chat.completions.create.side_effect = Exception("Groq connection timeout")

    # 2. Mock Gemini client to succeed
    mock_gemini = MagicMock()
    mock_gemini_resp = MagicMock()
    mock_gemini_resp.text = "Mocked Gemini Response"
    mock_gemini_resp.usage_metadata.prompt_token_count = 100
    mock_gemini_resp.usage_metadata.candidates_token_count = 50
    mock_gemini.models.generate_content.return_value = mock_gemini_resp

    with patch("app.ai.client.get_groq_client", return_value=mock_groq), \
         patch("app.ai.client.get_gemini_client", return_value=mock_gemini), \
         patch("app.ai.client.get_openai_client", return_value=None), \
         patch("app.ai.client.get_openrouter_client", return_value=None), \
         patch("app.ai.client.get_nvidia_client", return_value=None):
        
        from app.config import settings
        response = generate_content("Hello brand!", strategy="fast")
        
        # Assertions
        assert response.text == "Mocked Gemini Response"
        assert response.provider == "gemini"
        assert response.model == settings.GEMINI_MODEL
        assert response.input_tokens == 100
        assert response.output_tokens == 50
        
        # Verify ContextVar is set correctly
        meta = last_llm_meta.get()
        assert meta["provider"] == "gemini"
        assert meta["model"] == settings.GEMINI_MODEL
        assert meta["input_tokens"] == 100
        assert meta["output_tokens"] == 50
        assert meta["estimated_cost"] > 0.0

def test_groq_timeout_and_gemini_429_falls_back_to_openai():
    """
    Test that when Groq times out and Gemini returns 429, it falls back to OpenAI.
    """
    # 1. Mock Groq client to raise exception
    mock_groq = MagicMock()
    mock_groq.chat.completions.create.side_effect = Exception("Groq connection timeout")

    # 2. Mock Gemini client to raise a 429 rate limit exception
    mock_gemini = MagicMock()
    mock_gemini.models.generate_content.side_effect = Exception("Gemini API Error 429: Resource Exhausted")

    # 3. Mock OpenAI client to succeed
    mock_openai = MagicMock()
    mock_openai_resp = MagicMock()
    mock_openai_resp.choices = [MagicMock()]
    mock_openai_resp.choices[0].message.content = "Mocked OpenAI Response"
    mock_openai_resp.usage.prompt_tokens = 80
    mock_openai_resp.usage.completion_tokens = 40
    mock_openai.chat.completions.create.return_value = mock_openai_resp

    with patch("app.ai.client.get_groq_client", return_value=mock_groq), \
         patch("app.ai.client.get_gemini_client", return_value=mock_gemini), \
         patch("app.ai.client.get_openai_client", return_value=mock_openai), \
         patch("app.ai.client.get_openrouter_client", return_value=None), \
         patch("app.ai.client.get_nvidia_client", return_value=None):
        
        response = generate_content("Need to buy sarees", strategy="fast")
        
        # Assertions
        assert response.text == "Mocked OpenAI Response"
        assert response.provider == "openai"
        assert response.model == "gpt-4o-mini"
        assert response.input_tokens == 80
        assert response.output_tokens == 40
        
        # Verify ContextVar is set correctly
        meta = last_llm_meta.get()
        assert meta["provider"] == "openai"
        assert meta["model"] == "gpt-4o-mini"
        assert meta["input_tokens"] == 80
        assert meta["output_tokens"] == 40
        assert meta["estimated_cost"] > 0.0

def test_all_providers_fail_resolves_to_fallback():
    """
    Test that when all LLM providers fail, the system handles it gracefully and returns default metadata.
    """
    mock_groq = MagicMock()
    mock_groq.chat.completions.create.side_effect = Exception("Groq Error")
    mock_gemini = MagicMock()
    mock_gemini.models.generate_content.side_effect = Exception("Gemini Error")
    mock_openai = MagicMock()
    mock_openai.chat.completions.create.side_effect = Exception("OpenAI Error")

    with patch("app.ai.client.get_groq_client", return_value=mock_groq), \
         patch("app.ai.client.get_gemini_client", return_value=mock_gemini), \
         patch("app.ai.client.get_openai_client", return_value=mock_openai), \
         patch("app.ai.client.get_openrouter_client", return_value=None), \
         patch("app.ai.client.get_nvidia_client", return_value=None):
        
        response = generate_content("How are you?", strategy="fast")
        
        # Assertions
        assert response.text == ""
        assert response.provider == "fallback"
        assert response.model == "mock"
        assert response.input_tokens == 0
        assert response.output_tokens == 0
        
        # Verify ContextVar is set correctly
        meta = last_llm_meta.get()
        assert meta["provider"] == "fallback"
        assert meta["model"] == "mock"
        assert meta["input_tokens"] == 0
        assert meta["output_tokens"] == 0
        assert meta["estimated_cost"] == 0.0

def test_all_providers_fail_orchestrator_escalates():
    """
    Test that when all LLM providers fail, the orchestrator / generate_reply degrades gracefully
    and suggests connecting with a store manager (human escalation).
    """
    from app.ai.orchestrator import generate_reply
    
    mock_groq = MagicMock()
    mock_groq.chat.completions.create.side_effect = Exception("Groq Error")
    mock_gemini = MagicMock()
    mock_gemini.models.generate_content.side_effect = Exception("Gemini Error")
    mock_openai = MagicMock()
    mock_openai.chat.completions.create.side_effect = Exception("OpenAI Error")

    with patch("app.ai.client.get_groq_client", return_value=mock_groq), \
         patch("app.ai.client.get_gemini_client", return_value=mock_gemini), \
         patch("app.ai.client.get_openai_client", return_value=mock_openai), \
         patch("app.ai.client.get_openrouter_client", return_value=None), \
         patch("app.ai.client.get_nvidia_client", return_value=None):
         
        # When all fail, generate_reply should fall back to mock fallback which handles inquiry gracefully
        reply = generate_reply("Can I speak to a manager?", history=[], catalog_context=[], policies_context={})
        assert len(reply) > 0 and ("help" in reply.lower() or "manager" in reply.lower() or "namaste" in reply.lower())

