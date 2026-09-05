import pytest
import time
from unittest.mock import MagicMock, patch
from fastapi import Request, HTTPException
from app.rate_limiter import RedisRateLimiter, InMemoryRateLimiter
from app.config import settings

def test_rate_limiter_in_memory_enforcement():
    limiter = InMemoryRateLimiter(requests_limit=3, window_seconds=2, name="test_inmem")
    
    req = MagicMock(spec=Request)
    req.headers = {}
    req.client = MagicMock()
    req.client.host = "192.168.1.100"

    original_testing = settings.TESTING
    try:
        settings.TESTING = True
        limiter(req)
        limiter(req)
        limiter(req)

        with pytest.raises(HTTPException) as exc_info:
            limiter(req)
        assert exc_info.value.status_code == 429
        assert "Too many requests" in exc_info.value.detail
    finally:
        settings.TESTING = original_testing

def test_rate_limiter_reverse_proxy_ip_resolution():
    limiter = RedisRateLimiter(name="test_proxy", requests_limit=10, window_seconds=60)
    
    req1 = MagicMock(spec=Request)
    req1.headers = {"x-forwarded-for": "203.0.113.195, 70.41.3.18, 150.172.238.178"}
    req1.client = MagicMock()
    req1.client.host = "10.0.0.1"

    original_testing = settings.TESTING
    try:
        settings.TESTING = True
        limiter(req1)
        assert "203.0.113.195" in limiter.requests
        assert len(limiter.requests["203.0.113.195"]) == 1

        req2 = MagicMock(spec=Request)
        req2.headers = {"x-real-ip": "198.51.100.42"}
        req2.client = MagicMock()
        req2.client.host = "10.0.0.1"
        limiter(req2)
        assert "198.51.100.42" in limiter.requests
        assert len(limiter.requests["198.51.100.42"]) == 1
    finally:
        settings.TESTING = original_testing

def test_redis_sliding_window_limiter():
    limiter = RedisRateLimiter(name="test_redis", requests_limit=2, window_seconds=60)
    
    req = MagicMock(spec=Request)
    req.headers = {}
    req.client = MagicMock()
    req.client.host = "127.0.0.1"

    original_testing = settings.TESTING
    try:
        settings.TESTING = False
        
        mock_redis = MagicMock()
        mock_pipeline = MagicMock()
        mock_redis.pipeline.return_value = mock_pipeline
        
        mock_pipeline.execute.side_effect = [
            (0, 0),
            (None, None)
        ]

        with patch("redis.from_url", return_value=mock_redis):
            limiter(req)
            assert mock_pipeline.zremrangebyscore.called
            assert mock_pipeline.zcard.called
            assert mock_pipeline.zadd.called
            assert mock_pipeline.expire.called

        mock_pipeline.execute.side_effect = [
            (0, 2),
        ]

        with patch("redis.from_url", return_value=mock_redis):
            with pytest.raises(HTTPException) as exc_info:
                limiter(req)
            assert exc_info.value.status_code == 429
    finally:
        settings.TESTING = original_testing

def test_redis_failure_falls_back_to_in_memory():
    limiter = RedisRateLimiter(name="test_fallback", requests_limit=2, window_seconds=60)
    
    req = MagicMock(spec=Request)
    req.headers = {}
    req.client = MagicMock()
    req.client.host = "192.168.1.50"

    original_testing = settings.TESTING
    try:
        settings.TESTING = False
        
        with patch("redis.from_url", side_effect=Exception("Redis connection refused")):
            limiter(req)
            limiter(req)
            
            with pytest.raises(HTTPException) as exc_info:
                limiter(req)
            assert exc_info.value.status_code == 429
            assert "192.168.1.50" in limiter.requests
    finally:
        settings.TESTING = original_testing
