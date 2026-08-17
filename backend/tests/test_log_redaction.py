import pytest
from app.security import mask_sensitive_data

def test_mask_sensitive_data_phone_numbers():
    phone = "+919876543210"
    masked = mask_sensitive_data(phone)
    assert masked == "+91****210"
    assert "9876543" not in masked

def test_mask_sensitive_data_bearer_tokens():
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ"
    masked = mask_sensitive_data(token)
    assert "eyJ" in masked
    assert "****" in masked
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in masked

def test_mask_sensitive_data_short_strings():
    short_val = "12345"
    masked = mask_sensitive_data(short_val)
    assert masked == "***REDACTED***"

def test_mask_sensitive_data_empty():
    assert mask_sensitive_data(None) == ""
    assert mask_sensitive_data("") == ""
