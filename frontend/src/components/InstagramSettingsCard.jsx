import React, { useState, useEffect } from 'react';
import { apiFetch } from '../api';

export default function InstagramSettingsCard() {
  const [pageId, setPageId] = useState('');
  const [accessToken, setAccessToken] = useState('');
  const [igAccountId, setIgAccountId] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [copied, setCopied] = useState(null);
  const [saveSuccess, setSaveSuccess] = useState('');
  const [saveError, setSaveError] = useState('');

  const webhookUrl = "https://closely-backend.onrender.com/api/webhooks/instagram";
  const verifyToken = "closely_verify_token";

  useEffect(() => {
    fetchInstagramHealth();
  }, []);

  const fetchInstagramHealth = async () => {
    try {
      const res = await apiFetch('/api/brand/instagram/health');
      if (res.ok) {
        const data = await res.json();
        setIsConnected(!!data.is_connected);
        if (data.instagram_page_id) setPageId(data.instagram_page_id);
        if (data.instagram_business_account_id) setIgAccountId(data.instagram_business_account_id);
      }
    } catch (err) {
      console.error("Error fetching Instagram health:", err);
    }
  };

  const copy = async (value, key) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(key);
      setTimeout(() => setCopied(null), 1500);
    } catch {
      // Ignore fallback
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveSuccess('');
    setSaveError('');
    setTestResult(null);
    try {
      const res = await apiFetch('/api/brand/instagram/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          page_id: pageId.trim(),
          access_token: accessToken.trim(),
          instagram_business_account_id: igAccountId.trim() || undefined
        })
      });
      const data = await res.json();
      if (res.ok) {
        setSaveSuccess(data.message || "Instagram integration connected successfully!");
        setIsConnected(true);
        if (data.instagram_business_account_id) setIgAccountId(data.instagram_business_account_id);
        setAccessToken('');
      } else {
        setSaveError(data.detail || "Failed to save Instagram settings.");
      }
    } catch (err) {
      setSaveError(err.message || "Network error occurred.");
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await apiFetch('/api/brand/instagram/test-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          page_id: pageId.trim() || undefined,
          access_token: accessToken.trim() || undefined
        })
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        setTestResult({ ok: true, username: data.username });
      } else {
        setTestResult({ ok: false, error: data.error || data.detail || "Connection test failed" });
      }
    } catch (err) {
      setTestResult({ ok: false, error: err.message || "Failed to connect" });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div style={cardStyles.container}>
      {/* Header */}
      <div style={cardStyles.header}>
        <div style={cardStyles.titleRow}>
          <div style={cardStyles.iconBadge}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="2" y="2" width="20" height="20" rx="5" ry="5"></rect>
              <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"></path>
              <line x1="17.5" y1="6.5" x2="17.51" y2="6.5"></line>
            </svg>
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={cardStyles.title}>Instagram Direct Messages</span>
              <span style={cardStyles.badge}>Meta Graph API</span>
            </div>
            <div style={cardStyles.subtitle}>
              Automate customer DMs, product cards, and sales with your AI Employee
            </div>
          </div>
        </div>
        <span style={isConnected ? cardStyles.statusConnected : cardStyles.statusDisconnected}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: isConnected ? '#00ffc4' : '#888' }} />
          {isConnected ? 'Connected' : 'Not Connected'}
        </span>
      </div>

      <div style={cardStyles.body}>
        {saveSuccess && (
          <div style={cardStyles.alertSuccess}>
            ✅ {saveSuccess}
          </div>
        )}

        {saveError && (
          <div style={cardStyles.alertError}>
            ⚠️ {saveError}
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
          <div>
            <label style={cardStyles.label}>Facebook Page ID</label>
            <input
              type="text"
              className="form-input"
              value={pageId}
              onChange={(e) => setPageId(e.target.value)}
              placeholder="e.g. 102938475610293"
            />
            <div style={cardStyles.hint}>
              The Facebook Page connected to your Instagram Business account.
            </div>
          </div>

          <div>
            <label style={cardStyles.label}>Page Access Token</label>
            <input
              type="password"
              className="form-input"
              value={accessToken}
              onChange={(e) => setAccessToken(e.target.value)}
              placeholder={isConnected ? "••••••••••••••••••••••••••••••••" : "Paste Page Access Token"}
            />
            <div style={cardStyles.hint}>
              Encrypted at rest with Fernet AES-128-CBC.
            </div>
          </div>
        </div>

        {/* Webhook Details */}
        <div style={cardStyles.webhookBox}>
          <div style={cardStyles.webhookTitle}>
            Meta Webhook Configuration (Instagram)
          </div>

          <div style={cardStyles.copyRow}>
            <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              <span style={{ color: '#888' }}>Callback URL:</span> {webhookUrl}
            </div>
            <button
              type="button"
              onClick={() => copy(webhookUrl, 'url')}
              style={cardStyles.copyBtn}
            >
              {copied === 'url' ? '✅ Copied' : '📋 Copy'}
            </button>
          </div>

          <div style={cardStyles.copyRow}>
            <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              <span style={{ color: '#888' }}>Verify Token:</span> {verifyToken}
            </div>
            <button
              type="button"
              onClick={() => copy(verifyToken, 'token')}
              style={cardStyles.copyBtn}
            >
              {copied === 'token' ? '✅ Copied' : '📋 Copy'}
            </button>
          </div>

          <a
            href="https://developers.facebook.com/docs/messenger-platform/instagram/get-started"
            target="_blank"
            rel="noreferrer"
            style={cardStyles.guideLink}
          >
            Meta Instagram Messaging Setup Guide ↗
          </a>
        </div>

        {/* Test Result */}
        {testResult && (
          <div style={testResult.ok ? cardStyles.testSuccess : cardStyles.testError}>
            <div style={{ fontWeight: '700', marginBottom: '0.2rem' }}>
              {testResult.ok ? '✅ Connection Successful' : '❌ Connection Test Failed'}
            </div>
            <div style={{ fontSize: '0.8rem' }}>
              {testResult.ok
                ? `Authenticated with Meta Graph API as @${testResult.username}`
                : testResult.error}
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div style={{ display: 'flex', gap: '0.8rem', alignItems: 'center', marginTop: '0.5rem' }}>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleSave}
            disabled={saving || !pageId || (!accessToken && !isConnected)}
            style={{ fontSize: '0.85rem', padding: '0.5rem 1rem' }}
          >
            {saving ? 'Saving...' : '💾 Save Instagram Settings'}
          </button>
          
          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleTest}
            disabled={testing || (!isConnected && !accessToken)}
            style={{ fontSize: '0.85rem', padding: '0.5rem 1rem' }}
          >
            {testing ? 'Testing...' : '🧪 Test Meta Graph Connection'}
          </button>
        </div>
      </div>
    </div>
  );
}

const cardStyles = {
  container: {
    marginTop: '1.5rem',
    marginBottom: '1.5rem',
    borderRadius: '12px',
    border: '1px solid rgba(255, 255, 255, 0.1)',
    background: 'rgba(255, 255, 255, 0.03)',
    overflow: 'hidden',
  },
  header: {
    padding: '1rem 1.25rem',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
    background: 'rgba(255, 255, 255, 0.02)',
  },
  titleRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.8rem',
  },
  iconBadge: {
    width: 36,
    height: 36,
    borderRadius: 8,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'linear-gradient(45deg, #f09433 0%,#e6683c 25%,#dc2743 50%,#cc2366 75%,#bc1888 100%)',
  },
  title: {
    fontSize: '0.95rem',
    fontWeight: '700',
    color: '#fff',
  },
  subtitle: {
    fontSize: '0.75rem',
    color: 'var(--text-secondary)',
    marginTop: '0.1rem',
  },
  badge: {
    fontSize: '0.65rem',
    fontWeight: '600',
    padding: '0.15rem 0.4rem',
    borderRadius: '4px',
    background: 'rgba(188, 24, 136, 0.15)',
    color: '#f09433',
    border: '1px solid rgba(188, 24, 136, 0.3)',
  },
  statusConnected: {
    fontSize: '0.75rem',
    fontWeight: '600',
    padding: '0.3rem 0.6rem',
    borderRadius: '20px',
    background: 'rgba(0, 255, 196, 0.1)',
    color: '#00ffc4',
    border: '1px solid rgba(0, 255, 196, 0.3)',
    display: 'flex',
    alignItems: 'center',
    gap: '0.4rem',
  },
  statusDisconnected: {
    fontSize: '0.75rem',
    fontWeight: '600',
    padding: '0.3rem 0.6rem',
    borderRadius: '20px',
    background: 'rgba(255, 255, 255, 0.05)',
    color: '#888',
    border: '1px solid rgba(255, 255, 255, 0.1)',
    display: 'flex',
    alignItems: 'center',
    gap: '0.4rem',
  },
  body: {
    padding: '1.25rem',
    display: 'flex',
    flexDirection: 'column',
    gap: '1rem',
  },
  label: {
    fontSize: '0.8rem',
    fontWeight: '600',
    color: 'var(--text-secondary)',
    marginBottom: '0.3rem',
    display: 'block',
  },
  hint: {
    fontSize: '0.7rem',
    color: '#777',
    marginTop: '0.25rem',
  },
  webhookBox: {
    borderRadius: '8px',
    background: 'rgba(0, 0, 0, 0.25)',
    border: '1px solid rgba(255, 255, 255, 0.06)',
    padding: '0.8rem 1rem',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.5rem',
  },
  webhookTitle: {
    fontSize: '0.75rem',
    fontWeight: '700',
    color: '#ccc',
    textTransform: 'uppercase',
    letterSpacing: '0.04em',
  },
  copyRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    background: 'rgba(255, 255, 255, 0.04)',
    padding: '0.4rem 0.6rem',
    borderRadius: '6px',
    fontSize: '0.75rem',
    fontFamily: 'monospace',
    color: '#eee',
    gap: '0.5rem',
  },
  copyBtn: {
    background: 'transparent',
    border: '1px solid rgba(255, 255, 255, 0.15)',
    color: '#ddd',
    borderRadius: '4px',
    padding: '0.2rem 0.4rem',
    fontSize: '0.7rem',
    cursor: 'pointer',
    flexShrink: 0,
  },
  guideLink: {
    fontSize: '0.75rem',
    color: '#00ffc4',
    textDecoration: 'none',
    display: 'inline-block',
    marginTop: '0.2rem',
  },
  alertSuccess: {
    padding: '0.6rem 0.8rem',
    borderRadius: '6px',
    background: 'rgba(0, 255, 196, 0.1)',
    color: '#00ffc4',
    border: '1px solid rgba(0, 255, 196, 0.3)',
    fontSize: '0.8rem',
  },
  alertError: {
    padding: '0.6rem 0.8rem',
    borderRadius: '6px',
    background: 'rgba(255, 77, 79, 0.1)',
    color: '#ff7875',
    border: '1px solid rgba(255, 77, 79, 0.3)',
    fontSize: '0.8rem',
  },
  testSuccess: {
    padding: '0.7rem 0.9rem',
    borderRadius: '6px',
    background: 'rgba(0, 255, 196, 0.08)',
    border: '1px solid rgba(0, 255, 196, 0.3)',
    color: '#00ffc4',
  },
  testError: {
    padding: '0.7rem 0.9rem',
    borderRadius: '6px',
    background: 'rgba(255, 77, 79, 0.08)',
    border: '1px solid rgba(255, 77, 79, 0.3)',
    color: '#ff7875',
  },
};
