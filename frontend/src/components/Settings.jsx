import React, { useState, useEffect } from 'react';
import { apiFetch } from '../api';

export default function Settings({ token }) {
  const [name, setName] = useState('');
  const [whatsappNumber, setWhatsappNumber] = useState('');
  const [address, setAddress] = useState('');
  const [shippingPolicy, setShippingPolicy] = useState('');
  const [returnPolicy, setReturnPolicy] = useState('');
  const [faqText, setFaqText] = useState('');
  const [operatingMode, setOperatingMode] = useState('SHADOW');
  const [success, setSuccess] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const [whatsappPhoneNumberId, setWhatsappPhoneNumberId] = useState('');
  const [whatsappWabaId, setWhatsappWabaId] = useState('');
  const [whatsappAccessToken, setWhatsappAccessToken] = useState('');
  const [testStatus, setTestStatus] = useState('');
  const [testing, setTesting] = useState(false);

  // Kill Switch State
  const [killSwitchEnabled, setKillSwitchEnabled] = useState(false);
  const [killSwitchReason, setKillSwitchReason] = useState('');
  const [killSwitchActivatedAt, setKillSwitchActivatedAt] = useState(null);
  const [killSwitchLoading, setKillSwitchLoading] = useState(false);

  useEffect(() => {
    fetchProfile();
    fetchKillSwitchStatus();
  }, []);

  const fetchProfile = async () => {
    try {
      const res = await apiFetch('/api/brand/profile');
      if (res.ok) {
        const data = await res.json();
        setName(data.name);
        setWhatsappNumber(data.whatsapp_number || '');
        setAddress(data.address || '');
        setShippingPolicy(data.policies?.shipping || '');
        setReturnPolicy(data.policies?.returns || '');
        setFaqText(data.policies?.faqs || '');
        setOperatingMode(data.policies?.operating_mode || 'SHADOW');
        setWhatsappPhoneNumberId(data.whatsapp_phone_number_id || data.policies?.whatsapp_phone_number_id || '');
        setWhatsappWabaId(data.whatsapp_business_account_id || data.policies?.whatsapp_business_account_id || '');
        setWhatsappAccessToken(data.policies?.whatsapp_access_token || '');
      }
    } catch (err) {
      console.error("Error fetching brand profile:", err);
    }
  };

  const fetchKillSwitchStatus = async () => {
    try {
      const res = await apiFetch('/api/brand/kill-switch');
      if (res.ok) {
        const data = await res.json();
        setKillSwitchEnabled(data.kill_switch_enabled);
        setKillSwitchReason(data.reason || '');
        setKillSwitchActivatedAt(data.activated_at || null);
      }
    } catch (err) {
      console.error("Error fetching kill switch status:", err);
    }
  };

  const handleToggleKillSwitch = async () => {
    const nextEnable = !killSwitchEnabled;
    let reason = '';
    if (nextEnable) {
      reason = window.prompt("Enter a reason for engaging the Emergency Outbound Kill Switch (e.g. pricing error, catalog sync):", "Operational safety check");
      if (reason === null) return; // user cancelled prompt
    } else {
      const confirmDisengage = window.confirm("Are you sure you want to disengage the Emergency Kill Switch and restore outbound messaging?");
      if (!confirmDisengage) return;
      reason = "Resuming normal operations";
    }

    setKillSwitchLoading(true);
    try {
      const res = await apiFetch('/api/brand/kill-switch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enable: nextEnable, reason })
      });
      const data = await res.json();
      if (res.ok) {
        setKillSwitchEnabled(data.kill_switch_enabled);
        setKillSwitchReason(data.reason || '');
        setSuccess(data.message || (nextEnable ? "🚨 Kill Switch ENGAGED" : "✅ Kill Switch DISENGAGED"));
      } else {
        setError(data.detail || "Failed to update kill switch");
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setKillSwitchLoading(false);
    }
  };

  const handleTestConnection = async () => {
    setTestStatus('');
    setTesting(true);
    try {
      const res = await apiFetch('/api/brand/whatsapp/test-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ test_phone: whatsappNumber })
      });
      const data = await res.json();
      if (res.ok) {
        setTestStatus(`✅ ${data.message}`);
      } else {
        setTestStatus(`❌ Test Failed: ${data.detail}`);
      }
    } catch (err) {
      setTestStatus(`❌ Test Failed: ${err.message}`);
    } finally {
      setTesting(false);
    }
  };

  const handleUpdateProfile = async (e) => {
    e.preventDefault();
    setSuccess('');
    setError('');
    setLoading(true);

    const payload = {
      name,
      whatsapp_number: whatsappNumber || null,
      whatsapp_phone_number_id: whatsappPhoneNumberId || null,
      whatsapp_business_account_id: whatsappWabaId || null,
      whatsapp_access_token: whatsappAccessToken || null,
      address: address || null,
      policies: {
        shipping: shippingPolicy,
        returns: returnPolicy,
        faqs: faqText,
        operating_mode: operatingMode,
        whatsapp_phone_number_id: whatsappPhoneNumberId,
        whatsapp_business_account_id: whatsappWabaId,
        whatsapp_access_token: whatsappAccessToken
      }
    };

    try {
      const res = await apiFetch('/api/brand/profile', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to update settings.');
      }

      setSuccess('Brand profile, Meta Cloud API keys, and policies successfully saved!');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.container}>
      <div className="glass-panel animate-fade-in" style={styles.card}>
        <div style={styles.header}>
          <h2>WhatsApp Business & Meta API Integration</h2>
          <p style={styles.subtitle}>Connect your official Meta WhatsApp Business Cloud API or Wasender Gateway credentials and train your AI knowledge base.</p>
        </div>

        <form onSubmit={handleUpdateProfile} style={styles.form}>
          <div style={styles.sectionTitle}>1. Meta WhatsApp Cloud API Integration</div>
          
          <div style={styles.formRow}>
            <div style={styles.inputGroup}>
              <label style={styles.label}>WhatsApp Business Phone Number</label>
              <input 
                type="text" 
                className="form-input" 
                placeholder="e.g. +919876543210" 
                value={whatsappNumber} 
                onChange={e => setWhatsappNumber(e.target.value)} 
              />
            </div>
            
            <div style={styles.inputGroup}>
              <label style={styles.label}>Phone Number ID (Meta Cloud API)</label>
              <input 
                type="text" 
                className="form-input" 
                placeholder="e.g. 104829384729102" 
                value={whatsappPhoneNumberId} 
                onChange={e => setWhatsappPhoneNumberId(e.target.value)} 
              />
            </div>
          </div>

          <div style={styles.formRow}>
            <div style={styles.inputGroup}>
              <label style={styles.label}>WhatsApp Business Account ID (WABA ID)</label>
              <input 
                type="text" 
                className="form-input" 
                placeholder="e.g. 109283746501928" 
                value={whatsappWabaId} 
                onChange={e => setWhatsappWabaId(e.target.value)} 
              />
            </div>

            <div style={styles.inputGroup}>
              <label style={styles.label}>Permanent System User Access Token</label>
              <input 
                type="password" 
                className="form-input" 
                placeholder="EAAG..." 
                value={whatsappAccessToken} 
                onChange={e => setWhatsappAccessToken(e.target.value)} 
              />
            </div>
          </div>

          {/* Webhook Instructions Box */}
          <div style={{ background: 'rgba(0, 255, 196, 0.05)', border: '1px solid rgba(0, 255, 196, 0.15)', borderRadius: '8px', padding: '1rem', marginTop: '0.5rem' }}>
            <div style={{ fontWeight: '600', color: '#00ffc4', fontSize: '0.85rem', marginBottom: '0.4rem' }}>
              🔗 Meta Webhook Configuration Details:
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
              <div><strong>Callback URL:</strong> <code>https://closely-backend.onrender.com/api/webhooks/whatsapp</code></div>
              <div><strong>Verify Token:</strong> <code>closely_verify_token</code></div>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <button 
              type="button" 
              className="btn btn-secondary" 
              onClick={handleTestConnection}
              disabled={testing}
              style={{ fontSize: '0.8rem', padding: '0.4rem 0.8rem' }}
            >
              {testing ? 'Testing...' : '🧪 Test Meta Connection'}
            </button>
            {testStatus && <span style={{ fontSize: '0.8rem' }}>{testStatus}</span>}
          </div>

          <div style={styles.sectionTitle}>2. Brand Profile Details</div>
          
          <div style={styles.formRow}>
            <div style={styles.inputGroup}>
              <label style={styles.label}>Brand Name</label>
              <input 
                type="text" 
                className="form-input" 
                value={name} 
                onChange={e => setName(e.target.value)} 
                required 
              />
            </div>
            
            <div style={styles.inputGroup}>
              <label style={styles.label}>Physical Store Location / Address</label>
              <input 
                type="text" 
                className="form-input" 
                placeholder="Store address if customers ask..." 
                value={address} 
                onChange={e => setAddress(e.target.value)} 
              />
            </div>
          </div>

          <div style={styles.sectionTitle}>3. AI Grounding Policies & Knowledge Base</div>

          <div style={styles.inputGroup}>
            <label style={styles.label}>Shipping & Delivery Policy</label>
            <textarea 
              className="form-input" 
              style={styles.textarea} 
              placeholder="e.g. Free shipping on orders above 2000. Under 2000 we charge 100 shipping fee. Standard delivery takes 3 days to metro cities..." 
              value={shippingPolicy} 
              onChange={e => setShippingPolicy(e.target.value)}
            />
          </div>

          <div style={styles.inputGroup}>
            <label style={styles.label}>Return & Exchange Policy</label>
            <textarea 
              className="form-input" 
              style={styles.textarea} 
              placeholder="e.g. Easy exchanges within 7 days. Returns are only allowed in case of damaged products with opening video proof..." 
              value={returnPolicy} 
              onChange={e => setReturnPolicy(e.target.value)}
            />
          </div>

          <div style={styles.sectionTitle}>4. Operating Mode & Safety Guardrails (Milestone 4 Pilot)</div>

          {killSwitchEnabled && (
            <div style={styles.emergencyKillBanner}>
              <div style={{ fontWeight: '800', fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                🚨 EMERGENCY OUTBOUND KILL SWITCH ACTIVE
              </div>
              <div style={{ fontSize: '0.85rem', marginTop: '0.25rem' }}>
                All outbound WhatsApp messages are unconditionally <strong>BLOCKED</strong> at the gateway. Reason: <em>"{killSwitchReason || 'Manual intervention'}"</em>
              </div>
            </div>
          )}

          <div style={styles.inputGroup}>
            <label style={styles.label}>AI Operating Mode</label>
            <div style={{ display: 'flex', gap: '1rem', marginTop: '0.25rem' }}>
              <label style={{ ...styles.radioLabel, borderColor: operatingMode === 'SHADOW' ? '#00ffc4' : 'rgba(255,255,255,0.1)', background: operatingMode === 'SHADOW' ? 'rgba(0,255,196,0.08)' : 'transparent' }}>
                <input 
                  type="radio" 
                  name="operatingMode" 
                  value="SHADOW" 
                  checked={operatingMode === 'SHADOW'} 
                  onChange={() => setOperatingMode('SHADOW')} 
                />
                <div>
                  <div style={{ fontWeight: '700', color: operatingMode === 'SHADOW' ? '#00ffc4' : '#fff' }}>🛡️ Shadow Mode (Default)</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>AI responses generated & logged internally. 0 outbound customer messages.</div>
                </div>
              </label>

              <label style={{ ...styles.radioLabel, borderColor: operatingMode === 'HUMAN_APPROVAL' ? '#6366f1' : 'rgba(255,255,255,0.1)', background: operatingMode === 'HUMAN_APPROVAL' ? 'rgba(99,102,241,0.08)' : 'transparent' }}>
                <input 
                  type="radio" 
                  name="operatingMode" 
                  value="HUMAN_APPROVAL" 
                  checked={operatingMode === 'HUMAN_APPROVAL'} 
                  onChange={() => setOperatingMode('HUMAN_APPROVAL')} 
                />
                <div>
                  <div style={{ fontWeight: '700', color: operatingMode === 'HUMAN_APPROVAL' ? '#818cf8' : '#fff' }}>👤 Human Approval Pilot Mode</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>AI drafts responses to Inbox. Merchant must approve or edit before sending.</div>
                </div>
              </label>
            </div>
          </div>

          {/* Emergency Kill Switch Control Card */}
          <div style={{ background: killSwitchEnabled ? 'rgba(239, 68, 68, 0.12)' : 'rgba(255, 255, 255, 0.03)', border: killSwitchEnabled ? '1px solid #ef4444' : '1px solid rgba(255, 255, 255, 0.1)', borderRadius: '8px', padding: '1.25rem', marginTop: '0.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontWeight: '700', fontSize: '0.95rem', color: killSwitchEnabled ? '#f87171' : '#fff', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  {killSwitchEnabled ? '🚨 Kill Switch Status: ENGAGED' : '⚡ Emergency Outbound Kill Switch'}
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
                  {killSwitchEnabled 
                    ? `Activated on ${new Date(killSwitchActivatedAt).toLocaleString()}. Outbound messages are frozen.` 
                    : 'Immediately suspend all outbound WhatsApp customer messaging in case of emergency.'}
                </div>
              </div>
              <button
                type="button"
                className={`btn ${killSwitchEnabled ? 'btn-success' : 'btn-danger'}`}
                onClick={handleToggleKillSwitch}
                disabled={killSwitchLoading}
                style={{ fontSize: '0.85rem', padding: '0.5rem 1rem', whiteSpace: 'nowrap' }}
              >
                {killSwitchLoading ? 'Updating...' : killSwitchEnabled ? '✅ Disengage Kill Switch' : '🛑 ENGAGE KILL SWITCH'}
              </button>
            </div>
          </div>

          {success && <div style={styles.success}>{success}</div>}
          {error && <div style={styles.error}>{error}</div>}

          <button type="submit" className="btn btn-primary" style={styles.saveBtn} disabled={loading}>
            {loading ? 'Saving...' : '💾 Save & Apply Operating Mode & Policies'}
          </button>
        </form>
      </div>
    </div>
  );
}

const styles = {
  container: {
    display: 'flex',
    justifyContent: 'center',
    padding: '1.5rem 1rem 4rem 1rem',
    width: '100%',
    boxSizing: 'border-box',
  },
  card: {
    width: '100%',
    maxWidth: '760px',
    padding: '2rem',
    borderRadius: 'var(--border-radius-md)',
    boxSizing: 'border-box',
    display: 'flex',
    flexDirection: 'column',
    gap: '1rem',
  },
  header: {
    borderBottom: '1px solid var(--glass-border)',
    paddingBottom: '1rem',
    marginBottom: '1rem',
  },
  subtitle: {
    fontSize: '0.85rem',
    color: 'var(--text-secondary)',
    marginTop: '0.25rem',
  },
  sectionTitle: {
    fontSize: '0.85rem',
    fontWeight: '700',
    color: 'var(--accent-secondary)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    marginTop: '1.25rem',
    marginBottom: '0.5rem',
    borderBottom: '1px dashed rgba(255, 255, 255, 0.08)',
    paddingBottom: '0.25rem',
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: '1.25rem',
    width: '100%',
    boxSizing: 'border-box',
  },
  formRow: {
    display: 'flex',
    gap: '1rem',
    width: '100%',
    boxSizing: 'border-box',
  },
  inputGroup: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    gap: '0.4rem',
    width: '100%',
    boxSizing: 'border-box',
  },
  label: {
    fontSize: '0.75rem',
    fontWeight: '700',
    color: 'var(--text-secondary)',
  },
  textarea: {
    minHeight: '85px',
    resize: 'vertical',
    lineHeight: '1.4',
    width: '100%',
    boxSizing: 'border-box',
  },
  textareaLarge: {
    minHeight: '110px',
    resize: 'vertical',
    lineHeight: '1.4',
    width: '100%',
    boxSizing: 'border-box',
  },
  success: {
    color: 'var(--success)',
    background: 'rgba(16, 185, 129, 0.1)',
    border: '1px solid rgba(16, 185, 129, 0.2)',
    padding: '0.75rem',
    borderRadius: 'var(--border-radius-sm)',
    fontSize: '0.85rem',
    textAlign: 'center',
  },
  error: {
    color: 'var(--danger)',
    background: 'rgba(239, 68, 68, 0.1)',
    border: '1px solid rgba(239, 68, 68, 0.2)',
    padding: '0.75rem',
    borderRadius: 'var(--border-radius-sm)',
    fontSize: '0.85rem',
    textAlign: 'center',
    wordBreak: 'break-word',
  },
  saveBtn: {
    marginTop: '1rem',
    height: '46px',
    width: '100%',
  },
  emergencyKillBanner: {
    background: 'rgba(239, 68, 68, 0.15)',
    border: '2px solid #ef4444',
    borderRadius: '8px',
    padding: '1rem',
    color: '#fee2e2',
    animation: 'pulse 2s infinite',
  },
  radioLabel: {
    flex: 1,
    display: 'flex',
    alignItems: 'flex-start',
    gap: '0.6rem',
    padding: '0.85rem',
    borderRadius: '8px',
    border: '1px solid rgba(255, 255, 255, 0.1)',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
  },
};
