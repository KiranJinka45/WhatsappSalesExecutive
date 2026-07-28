import React, { useState, useEffect } from 'react';
import { apiFetch } from '../api';

export default function Settings({ token }) {
  const [name, setName] = useState('');
  const [whatsappNumber, setWhatsappNumber] = useState('');
  const [address, setAddress] = useState('');
  const [shippingPolicy, setShippingPolicy] = useState('');
  const [returnPolicy, setReturnPolicy] = useState('');
  const [faqText, setFaqText] = useState('');
  const [success, setSuccess] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchProfile();
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
      }
    } catch (err) {
      console.error("Error fetching brand profile:", err);
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
        throw new Error(data.detail || 'Failed to update settings.');
      }

      setSuccess('Brand profile and policies successfully synced with AI knowledge base.');
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
          <h2>AI Knowledge Base & Settings</h2>
          <p style={styles.subtitle}>Configure details and policies. Closely matches customer questions against these configurations.</p>
        </div>

        <form onSubmit={handleUpdateProfile} style={styles.form}>
          <div style={styles.sectionTitle}>Brand Details</div>
          
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
              <label style={styles.label}>Connected WhatsApp Number</label>
              <input 
                type="text" 
                className="form-input" 
                placeholder="e.g. +919876543210" 
                value={whatsappNumber} 
                onChange={e => setWhatsappNumber(e.target.value)} 
              />
            </div>
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

          <div style={styles.sectionTitle}>AI Grounding Policies</div>

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

          <div style={styles.inputGroup}>
            <label style={styles.label}>General FAQs & Custom Knowledge</label>
            <textarea 
              className="form-input" 
              style={styles.textareaLarge} 
              placeholder="e.g. COD is available for all items. We accept UPI and credit card transfers. Wholesale prices require minimum order of 20 pieces..." 
              value={faqText} 
              onChange={e => setFaqText(e.target.value)}
            />
          </div>

          {success && <div style={styles.success}>{success}</div>}
          {error && <div style={styles.error}>{error}</div>}

          <button type="submit" className="btn btn-primary" style={styles.saveBtn} disabled={loading}>
            {loading ? 'Saving...' : '💾 Save & Embed Knowledge'}
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
};
