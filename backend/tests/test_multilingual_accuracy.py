import pytest
from unittest.mock import patch, MagicMock
from app.ai.intent_engine import detect_language, classify_intent
from app.ai.orchestrator import generate_reply

# List of 40+ test cases representing code-mixed and multilingual inputs
MULTILINGUAL_TEST_CASES = [
    # Telugu - Latin script (Romanized)
    ("price entha?", "te", "latin"),
    ("ee red saree cost entha?", "te", "latin"),
    ("kavali black kurti size M", "te", "latin"),
    ("saree bagundi stock undhi?", "te", "latin"),
    ("lehenga cost cheppandi", "te", "latin"),
    ("evaru manager line lo unna?", "te", "latin"),
    ("avunu naku exchange beku", "te", "latin"),
    ("stock undha leda?", "te", "latin"),
    # Telugu - Native script
    ("ధర ఎంత?", "te", "native"),
    ("నలుపు రంగు చీర కావాలి", "te", "native"),
    ("స్టాక్ ఉందా?", "te", "native"),
    
    # Hindi - Latin script (Romanized / Hinglish)
    ("kya price hai?", "hi", "latin"),
    ("is blue kurti ka price kitna hai?", "hi", "latin"),
    ("mujhe red lehenga chahiye", "hi", "latin"),
    ("bhai stock available hai kya?", "hi", "latin"),
    ("dam batao shirt ka", "hi", "latin"),
    ("kya price h iska?", "hi", "latin"),
    ("sunder collection h", "hi", "latin"),
    ("acha discount milega?", "hi", "latin"),
    # Hindi - Native script
    ("क्या कीमत है?", "hi", "native"),
    ("मुझे लाल साड़ी चाहिए", "hi", "native"),
    ("स्टॉक में है क्या?", "hi", "native"),

    # Kannada - Latin script (Romanized)
    ("eshtu price?", "kn", "latin"),
    ("ee white shirt price eshtu?", "kn", "latin"),
    ("nange blue kurti beku", "kn", "latin"),
    ("stock ideya illa?", "kn", "latin"),
    ("kannada dalli cheppandi", "kn", "latin"),
    ("houdu naku beku", "kn", "latin"),
    ("eshtu discount kodi", "kn", "latin"),
    # Kannada - Native script
    ("ಬೆಲೆ ಎಷ್ಟು?", "kn", "native"),
    ("ನನಗೆ ಬಿಳಿ ಶರ್ಟ್ ಬೇಕು", "kn", "native"),
    ("ಸ್ಟಾಕ್ ಇದೆಯೇ?", "kn", "native"),

    # Tamil - Latin script (Romanized)
    ("evvalavu price?", "ta", "latin"),
    ("ee black saree evvalavu price?", "ta", "latin"),
    ("enna size iruku?", "ta", "latin"),
    ("nalla fabric check pannunga", "ta", "latin"),
    ("venum naku red kurti", "ta", "latin"),
    ("discount iruka illai?", "ta", "latin"),
    # Tamil - Native script
    ("விலை என்ன?", "ta", "native"),
    ("எனக்கு சிவப்பு சேலை வேண்டும்", "ta", "native"),
    ("பங்கு இருக்கிறதா?", "ta", "native"),

    # English - Latin script
    ("What is the price of the red saree?", "en", "latin"),
    ("Do you have size XL in stock?", "en", "latin"),
    ("I want to request a refund", "en", "latin"),
    ("Is cash on delivery available?", "en", "latin"),
]


@patch("app.ai.intent_engine.generate_content", side_effect=Exception("Offline"))
def test_local_fallback_language_detection(mock_gen):
    """
    Test that local keyword/Unicode fallback rules detect language and script
    correctly when the LLM is not called or offline.
    """
    correct = 0
    total = len(MULTILINGUAL_TEST_CASES)
    
    for text, expected_lang, expected_script in MULTILINGUAL_TEST_CASES:
        res = detect_language(text)
        if res["language"] == expected_lang and res["script"] == expected_script:
            correct += 1
        else:
            print(f"FAILED local detection for: '{text}' - Expected: {expected_lang}/{expected_script}, Got: {res['language']}/{res['script']}")
            
    accuracy = (correct / total) * 100
    print(f"\nLocal fallback detection accuracy: {accuracy:.2f}% ({correct}/{total})")
    assert accuracy >= 90.0, f"Local fallback accuracy below 90% threshold: {accuracy:.2f}%"


@patch("app.ai.intent_engine.generate_content")
def test_llm_language_detection(mock_gen):
    """
    Verify that LLM language detection behaves correctly with mocked response payloads.
    """
    # Simulate LLM response returning JSON
    mock_response = MagicMock()
    mock_response.text = '{"language": "te", "script": "latin", "confidence": 0.98}'
    mock_gen.return_value = mock_response
    
    res = detect_language("price entha?")
    assert res["language"] == "te"
    assert res["script"] == "latin"
    assert res["confidence"] == 0.98
    
    # Test fallback to English on bad JSON
    mock_response.text = 'invalid json'
    res = detect_language("What is the price of the red saree?")
    assert res["language"] == "en"
    assert res["script"] == "latin"


def test_prompt_generation_respects_language_context():
    """
    Ensure the prompt constructed for generating replies contains instructions
    referencing the detected language and script.
    """
    with patch("app.ai.orchestrator.generate_content") as mock_gen, \
         patch("app.ai.orchestrator.validate_reply") as mock_val:
         
        mock_gen.return_value = MagicMock(text="Mocked output")
        mock_val.return_value = (True, "Mocked output", [])
        
        generate_reply(
            customer_msg="price entha?",
            history=[],
            catalog_context=[],
            policies_context={},
            detected_language="te",
            detected_script="latin"
        )
        
        # Verify the prompt passed to generate_content contained our new dynamic instruction
        args, kwargs = mock_gen.call_args
        prompt = args[0]
        assert 'language: "te"' in prompt
        assert 'script: "latin"' in prompt
        assert "LANGUAGE & SCRIPT RULE" in prompt
