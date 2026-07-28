import React, { useState } from 'react';
import { apiFetch } from '../api';

export default function Onboarding({ initialBrandName, onOnboardingComplete }) {
  const [step, setStep] = useState(1);
  const [name, setName] = useState(initialBrandName || '');
  const [whatsappNumber, setWhatsappNumber] = useState('');
  const [address, setAddress] = useState('');
  const [shippingPolicy, setShippingPolicy] = useState('');
  const [returnPolicy, setReturnPolicy] = useState('');
  const [faqText, setFaqText] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleNext = (e) => {
    e.preventDefault();
    if (!name.trim()) {
      setError('Brand name is required.');
      return;
    }
    if (!whatsappNumber.trim()) {
      setError('WhatsApp Number is required for the bot integration.');
      return;
    }
    // Simple phone verification (requires + and digits)
    const phoneRegex = /^\+[1-9]\d{1,14}$/;
    if (!phoneRegex.test(whatsappNumber.replace(/\s+/g, ''))) {
      setError('Please enter a valid international WhatsApp number including country code (e.g. +919876543210).');
      return;
    }
    setError('');
    setStep(2);
  };

  const handleBack = () => {
    setError('');
    setStep(1);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    const payload = {
      name,
      whatsapp_number: whatsappNumber.replace(/\s+/g, ''),
      address: address || null,
      policies: {
        shipping: shippingPolicy,
        returns: returnPolicy,
        faqs: faqText
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
        throw new Error(data.detail || 'Failed to initialize brand profile.');
      }

      onOnboardingComplete(whatsappNumber.replace(/\s+/g, ''));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.container}>
      <div className="glass-panel" style={styles.card}>
        <div style={styles.header}>
          <span style={styles.badge}>Onboarding Setup</span>
          <h2 style={styles.title}>Configure Your Brand Store</h2>
          <p style={styles.subtitle}>Let's set up your store identity and AI instructions to start selling on WhatsApp.</p>
        </div>

        {/* Step Progress Indicators */}
        <div style={styles.stepIndicatorContainer}>
          <div style={{ ...styles.stepIndicator, ...(step >= 1 ? styles.stepIndicatorActive : {}) }}>
            1. Brand Details
          </div>
          <div style={styles.stepIndicatorLine}></div>
          <div style={{ ...styles.stepIndicator, ...(step >= 2 ? styles.stepIndicatorActive : {}) }}>
            2. AI Grounding Policies
          </div>
        </div>

        {error && <div style={styles.error}>{error}</div>}

        {step === 1 ? (
          <form onSubmit={handleNext} style={styles.form}>
            {/* Meta Embedded Signup Enterprise Banner */}
            <div style={{
              background: 'linear-gradient(135deg, rgba(24, 119, 242, 0.15), rgba(0, 240, 255, 0.1))',
              border: '1px solid rgba(24, 119, 242, 0.3)',
              borderRadius: '8px',
              padding: '1rem',
              marginBottom: '1.25rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.75rem'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ fontSize: '1.25rem' }}>⚡</span>
                <strong style={{ fontSize: '0.95rem', color: '#1877F2' }}>Enterprise 1-Click Meta Integration</strong>
              </div>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.4 }}>
                Skip manual API keys! Connect your WhatsApp Business number instantly via Meta's 1-click OAuth flow.
              </p>
              <button
                type="button"
                className="btn"
                style={{
                  backgroundColor: '#1877F2',
                  color: '#ffffff',
                  fontWeight: '600',
                  padding: '0.65rem 1.25rem',
                  borderRadius: '6px',
                  border: 'none',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.5rem',
                  boxShadow: '0 4px 12px rgba(24, 119, 242, 0.3)'
                }}
                onClick={async () => {
                  setLoading(true);
                  try {
                    const res = await apiFetch('/api/brand/whatsapp/embedded-signup', {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ code: 'demo_meta_oauth_code_123', waba_id: '1098237498234', phone_number_id: '982734982734' })
                    });
                    if (res.ok) {
                      const data = await res.json();
                      setWhatsappNumber(data.whatsapp_number || '+919900001111');
                      alert("Successfully connected via Meta 1-Click Embedded Signup!");
                    }
                  } catch (err) {
                    console.error("Meta embedded signup failed:", err);
                  } finally {
                    setLoading(false);
                  }
                }}
              >
                <span>📘</span> Log in with Facebook & Connect WhatsApp
              </button>
            </div>

            <div style={styles.inputGroup}>
              <label style={styles.label}>Brand/Boutique Name</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. Kiran Sarees"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>

            <div style={styles.inputGroup}>
              <label style={styles.label}>Connected WhatsApp Number</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. +919876543210 (Must include country code)"
                value={whatsappNumber}
                onChange={(e) => setWhatsappNumber(e.target.value)}
                required
              />
              <span style={styles.hint}>This is the WhatsApp business phone number our AI agent connects to.</span>
            </div>

            <div style={styles.inputGroup}>
              <label style={styles.label}>Physical Store Location / Address</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. 123 Silk Street, Kanchipuram, Tamil Nadu"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
              />
              <span style={styles.hint}>Optional. Used by the AI to answer "Where is your shop located?".</span>
            </div>

            <button type="submit" className="btn btn-primary" style={styles.btnAction}>
              Continue to AI Rules
            </button>
          </form>
        ) : (
          <form onSubmit={handleSubmit} style={styles.form}>
            <div style={styles.inputGroup}>
              <label style={styles.label}>Shipping & Delivery Policy</label>
              <textarea
                className="form-input"
                style={styles.textarea}
                placeholder="e.g. Free shipping on orders above ₹2000. Under ₹2000, we charge ₹100. Delivery takes 3-5 working days."
                value={shippingPolicy}
                onChange={(e) => setShippingPolicy(e.target.value)}
                required
              />
              <span style={styles.hint}>Helps the AI respond to "Do you ship to Mumbai?" or "What are shipping charges?".</span>
            </div>

            <div style={styles.inputGroup}>
              <label style={styles.label}>Return & Exchange Policy</label>
              <textarea
                className="form-input"
                style={styles.textarea}
                placeholder="e.g. Easy exchanges within 7 days of delivery. Returns allowed only for damaged goods with package opening video proof."
                value={returnPolicy}
                onChange={(e) => setReturnPolicy(e.target.value)}
                required
              />
              <span style={styles.hint}>Helps the AI handle customer refund or exchange inquiries correctly.</span>
            </div>

            <div style={styles.inputGroup}>
              <label style={styles.label}>General FAQs & Custom Knowledge</label>
              <textarea
                className="form-input"
                style={styles.textareaLarge}
                placeholder="e.g. COD is available. Wholesale orders get 15% discount (minimum 15 pieces). All sarees include running blouse material."
                value={faqText}
                onChange={(e) => setFaqText(e.target.value)}
              />
              <span style={styles.hint}>Any extra details you want your AI assistant to know when talking to buyers.</span>
            </div>

            <div style={styles.btnRow}>
              <button type="button" className="btn btn-secondary" style={styles.btnBack} onClick={handleBack} disabled={loading}>
                Back
              </button>
              <button type="submit" className="btn btn-primary" style={styles.btnSubmit} disabled={loading}>
                {loading ? 'Finalizing Setup...' : '💾 Complete Setup & Launch'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

const styles = {
  container: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '100vh',
    padding: '2rem 1.5rem',
    background: 'radial-gradient(circle at top right, rgba(0, 240, 255, 0.03), transparent 50%), radial-gradient(circle at bottom left, rgba(79, 70, 229, 0.05), transparent 50%)',
    backgroundColor: 'var(--bg-primary)',
  },
  card: {
    width: '100%',
    maxWidth: '580px',
    padding: '2.5rem',
    borderRadius: 'var(--border-radius-lg)',
    animation: 'fadeIn 0.4s ease',
  },
  header: {
    textAlign: 'center',
    marginBottom: '1.5rem',
  },
  badge: {
    display: 'inline-block',
    backgroundColor: 'rgba(79, 70, 229, 0.15)',
    color: 'var(--accent-secondary)',
    border: '1px solid rgba(79, 70, 229, 0.3)',
    borderRadius: '4px',
    padding: '0.2rem 0.5rem',
    fontSize: '0.65rem',
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    marginBottom: '0.75rem',
  },
  title: {
    fontSize: '1.6rem',
    fontWeight: '700',
    color: 'var(--text-primary)',
    marginBottom: '0.25rem',
  },
  subtitle: {
    fontSize: '0.85rem',
    color: 'var(--text-secondary)',
    lineHeight: '1.4',
  },
  stepIndicatorContainer: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: '2rem',
    padding: '0 0.5rem',
  },
  stepIndicator: {
    fontSize: '0.8rem',
    fontWeight: '600',
    color: 'var(--text-muted)',
    transition: 'color 0.2s ease',
  },
  stepIndicatorActive: {
    color: 'var(--accent-secondary)',
  },
  stepIndicatorLine: {
    height: '1px',
    backgroundColor: 'var(--glass-border)',
    flex: 1,
    margin: '0 1rem',
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: '1.25rem',
  },
  inputGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.4rem',
  },
  label: {
    fontSize: '0.8rem',
    fontWeight: '700',
    color: 'var(--text-secondary)',
  },
  hint: {
    fontSize: '0.7rem',
    color: 'var(--text-muted)',
    lineHeight: '1.3',
  },
  textarea: {
    height: '75px',
    resize: 'none',
  },
  textareaLarge: {
    height: '100px',
    resize: 'none',
  },
  error: {
    color: 'var(--danger)',
    fontSize: '0.85rem',
    background: 'rgba(239, 68, 68, 0.1)',
    border: '1px solid rgba(239, 68, 68, 0.2)',
    padding: '0.75rem',
    borderRadius: 'var(--border-radius-sm)',
    textAlign: 'center',
    marginBottom: '1.25rem',
  },
  btnAction: {
    marginTop: '0.75rem',
    width: '100%',
    height: '46px',
    fontWeight: '600',
  },
  btnRow: {
    display: 'flex',
    gap: '1rem',
    marginTop: '0.75rem',
  },
  btnBack: {
    flex: 0.3,
    height: '46px',
  },
  btnSubmit: {
    flex: 0.7,
    height: '46px',
    fontWeight: '600',
  },
};
