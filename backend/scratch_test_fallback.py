import sys
sys.path.append(r"c:\whatsapp_AI Sales Employee\backend")
from app.ai.intent_engine import detect_language
from tests.test_multilingual_accuracy import MULTILINGUAL_TEST_CASES
from unittest.mock import patch

correct = 0
total = 0

with patch("app.ai.intent_engine.generate_content", side_effect=Exception("Offline")):
    for text, expected_lang, expected_script in MULTILINGUAL_TEST_CASES:
        res = detect_language(text)
        total += 1
        if res["language"] == expected_lang and res["script"] == expected_script:
            correct += 1
        else:
            print(f"FAILED: '{text}' - Expected: {expected_lang}/{expected_script}, Got: {res['language']}/{res['script']}")

print(f"Accuracy: {correct/total * 100:.2f}%")
