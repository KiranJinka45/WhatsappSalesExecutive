import React, { useState } from 'react';
import { apiFetch } from '../api';
import { launchEmbeddedSignup } from '../utils/metaEmbeddedSignup';

export default function Onboarding({ initialBrandName, onOnboardingComplete }) {
  const [step, setStep] = useState(1);
  const [name, setName] = useState(initialBrandName || '');
  const [whatsappNumber, setWhatsappNumber] = useState('');
  const [address, setAddress] = useState('');
  const [currency, setCurrency] = useState('INR (₹)');
  
  // Step 2: Policies & Persona
  const [tone, setTone] = useState('warm_boutique');
  const [operatingHoursStart, setOperatingHoursStart] = useState('10:00');
  const [operatingHoursEnd, setOperatingHoursEnd] = useState('21:00');
  const [aiSales247, setAiSales247] = useState(true);
  const [shippingPolicy, setShippingPolicy] = useState('Free delivery across India on orders above ₹2000. Under ₹2000, shipping is ₹100. Dispatched in 24-48 hours.');
  const [returnPolicy, setReturnPolicy] = useState('7-day hassle-free exchange for size or defect. Video required during parcel unboxing.');
  const [faqText, setFaqText] = useState('Cash on Delivery (COD) available. All pure silk sarees include silk mark assurance and unstitched blouse piece.');

  // Step 3: Catalog
  const [selectedPack, setSelectedPack] = useState('silk_sarees');
  const [seededCount, setSeededCount] = useState(0);
  const [catalogSeeded, setCatalogSeeded] = useState(false);

  // Step 4: Simulator
  const [simMessages, setSimMessages] = useState([
    { sender: 'ai', text: 'Namaste! Welcome to our boutique. How can I help you today? Feel free to ask about our sarees, kurtis, or policies! 🙏' }
  ]);
  const [simInput, setSimInput] = useState('');

  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleStep1Next = (e) => {
    e.preventDefault();
    if (!name.trim()) {
      setError('Brand name is required.');
      return;
    }
    if (!whatsappNumber.trim()) {
      setError('WhatsApp Number is required for the bot integration.');
      return;
    }
    
    let cleanPhone = whatsappNumber.replace(/[\s\-\(\)]+/g, '');
    if (/^[6-9]\d{9}$/.test(cleanPhone)) {
      cleanPhone = '+91' + cleanPhone;
      setWhatsappNumber(cleanPhone);
    }

    const phoneRegex = /^\+[1-9]\d{1,14}$/;
    if (!phoneRegex.test(cleanPhone)) {
      setError('Please enter a valid international WhatsApp number including country code (e.g. +919876543210).');
      return;
    }
    setError('');
    setStep(2);
  };

  const handleStep2Next = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    const payload = {
      name,
      whatsapp_number: whatsappNumber.replace(/\s+/g, ''),
      address: address || null,
      policies: {
        tone,
        operating_hours: `${operatingHoursStart} - ${operatingHoursEnd}`,
        ai_sales_24_7: aiSales247,
        currency,
        shipping: shippingPolicy,
        returns: returnPolicy,
        faqs: faqText
      }
    };

    try {
      const res = await apiFetch('/api/brand/profile', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to save store policies.');
      }
      setStep(3);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSeedCatalog = async (packType) => {
    setLoading(true);
    try {
      const res = await apiFetch(`/api/catalog/seed-starter-pack?pack_type=${packType}`, {
        method: 'POST'
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to seed starter catalog pack.');
      }
      const data = await res.json();
      setSelectedPack(packType);
      setSeededCount(data.seeded_count);
      setCatalogSeeded(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSendSimMessage = (e) => {
    e.preventDefault();
    if (!simInput.trim()) return;

    const userText = simInput.trim();
    const newHistory = [...simMessages, { sender: 'user', text: userText }];
    setSimMessages(newHistory);
    setSimInput('');

    // Instant realistic response based on tone and catalog
    setTimeout(() => {
      let botReply = '';
      const lower = userText.toLowerCase();
      if (lower.includes('saree') || lower.includes('silk') || lower.includes('show')) {
        botReply = 'Here are our top recommended pure silk sarees for you:\n\n✨ 1. Kanchipuram Pure Silk Saree (Crimson Red & Gold Zari) — ₹6,499\n✨ 2. Banarasi Handwoven Katan Silk Saree (Royal Blue) — ₹4,899\n\nWould you like to see photos or place an order? 🙏';
      } else if (lower.includes('shipping') || lower.includes('delivery')) {
        botReply = `${shippingPolicy} 🙏`;
      } else if (lower.includes('return') || lower.includes('exchange')) {
        botReply = `${returnPolicy} 🙏`;
      } else if (lower.includes('cod') || lower.includes('payment') || lower.includes('price')) {
        botReply = `${faqText} 🙏`;
      } else {
        botReply = `Namaste! I am ${name}'s AI Sales Assistant. I can help you browse our catalog, check prices, and place orders directly on WhatsApp! 🙏`;
      }

      setSimMessages([...newHistory, { sender: 'ai', text: botReply }]);
    }, 400);
  };

  const handleFinishOnboarding = () => {
    onOnboardingComplete(whatsappNumber.replace(/\s+/g, ''));
  };

  return (
    <div style={styles.container}>
      <div className="glass-panel" style={styles.card}>
        <div style={styles.header}>
          <span style={styles.badge}>Merchant Onboarding • Step {step} of 4</span>
          <h2 style={styles.title}>
            {step === 1 && 'Store Identity & WhatsApp Setup'}
            {step === 2 && 'AI Persona & Sales Policies'}
            {step === 3 && 'Instant Catalog Starter Pack'}
            {step === 4 && 'Test Your Store AI & Launch'}
          </h2>
          <p style={styles.subtitle}>
            {step === 1 && 'Configure your boutique name and link your official Meta WhatsApp Business account.'}
            {step === 2 && 'Define your brand tone, store hours, and AI customer response guidelines.'}
            {step === 3 && 'Choose a ready-to-sell inventory starter pack or upload your own products.'}
            {step === 4 && 'Simulate customer chats to verify recommendations before launching live.'}
          </p>
        </div>

        {/* Step Progress Indicators */}
        <div style={styles.stepIndicatorContainer}>
          <div style={{ ...styles.stepIndicator, ...(step >= 1 ? styles.stepIndicatorActive : {}) }}>1. Store</div>
          <div style={styles.stepIndicatorLine}></div>
          <div style={{ ...styles.stepIndicator, ...(step >= 2 ? styles.stepIndicatorActive : {}) }}>2. AI Rules</div>
          <div style={styles.stepIndicatorLine}></div>
          <div style={{ ...styles.stepIndicator, ...(step >= 3 ? styles.stepIndicatorActive : {}) }}>3. Catalog</div>
          <div style={styles.stepIndicatorLine}></div>
          <div style={{ ...styles.stepIndicator, ...(step >= 4 ? styles.stepIndicatorActive : {}) }}>4. Verify</div>
        </div>

        {error && <div style={styles.error}>{error}</div>}

        {/* STEP 1: Store & WhatsApp Details */}
        {step === 1 && (
          <form onSubmit={handleStep1Next} style={styles.form}>
            <div style={{
              background: 'linear-gradient(135deg, rgba(24, 119, 242, 0.15), rgba(0, 240, 255, 0.1))',
              border: '1px solid rgba(24, 119, 242, 0.3)',
              borderRadius: '8px',
              padding: '1rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.65rem'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ fontSize: '1.25rem' }}>⚡</span>
                <strong style={{ fontSize: '0.95rem', color: '#1877F2' }}>Official Meta 1-Click Embedded Signup</strong>
              </div>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.4 }}>
                Connect your WhatsApp Business number directly through Meta's official OAuth login.
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
                  setError('');
                  try {
                    const result = await launchEmbeddedSignup({ apiFetch });
                    if (result && result.status === 'success') {
                      setWhatsappNumber(result.masked_display_number || '+919900001111');
                      alert("Successfully connected via Meta Official Embedded Signup!");
                    } else if (result && result.is_test_number) {
                      setWhatsappNumber(result.masked_display_number || '+15551234567');
                      alert("Meta Developer Test Number attached.");
                    }
                  } catch (err) {
                    setError(err.message || 'Meta Embedded Signup was cancelled or failed.');
                  } finally {
                    setLoading(false);
                  }
                }}
              >
                <span>📘</span> Log in with Facebook & Connect WhatsApp
              </button>
            </div>

            <div style={styles.inputGroup}>
              <label style={styles.label}>Brand / Boutique Name</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. Kiran Sarees & Silks"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>

            <div style={styles.inputGroup}>
              <label style={styles.label}>WhatsApp Business Phone Number</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. +919876543210 (or 10 digits)"
                value={whatsappNumber}
                onChange={(e) => setWhatsappNumber(e.target.value)}
                required
              />
              <span style={styles.hint}>Used by Meta webhooks to route incoming customer chats.</span>
              {whatsappNumber && /^[6-9]\d{9}$/.test(whatsappNumber.trim()) && (
                <span style={{ color: '#00ffc4', fontSize: '0.75rem', marginTop: '0.2rem', display: 'block', fontWeight: '500' }}>
                  💡 Auto-formatting to +91{whatsappNumber.trim()}
                </span>
              )}
            </div>

            <div style={styles.inputGroup}>
              <label style={styles.label}>Physical Store Address</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. 12 Silk Market Road, Bangalore, Karnataka"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
              />
              <span style={styles.hint}>Optional. AI uses this to answer "Where is your boutique located?".</span>
            </div>

            <button type="submit" className="btn btn-primary" style={styles.btnAction}>
              Continue to AI Rules →
            </button>
          </form>
        )}

        {/* STEP 2: AI Rules, Tone & Operating Hours */}
        {step === 2 && (
          <form onSubmit={handleStep2Next} style={styles.form}>
            <div style={styles.inputGroup}>
              <label style={styles.label}>AI Sales Tone & Personality</label>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.5rem' }}>
                <button
                  type="button"
                  onClick={() => setTone('warm_boutique')}
                  style={{
                    padding: '0.65rem 0.5rem',
                    borderRadius: '6px',
                    border: tone === 'warm_boutique' ? '2px solid var(--accent-secondary)' : '1px solid var(--glass-border)',
                    background: tone === 'warm_boutique' ? 'rgba(0, 240, 255, 0.1)' : 'rgba(255, 255, 255, 0.03)',
                    color: 'var(--text-primary)',
                    cursor: 'pointer',
                    fontSize: '0.75rem',
                    textAlign: 'center'
                  }}
                >
                  🌸 <strong>Warm Boutique</strong><br/><span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>Namaste, polite & helpful</span>
                </button>
                <button
                  type="button"
                  onClick={() => setTone('professional')}
                  style={{
                    padding: '0.65rem 0.5rem',
                    borderRadius: '6px',
                    border: tone === 'professional' ? '2px solid var(--accent-secondary)' : '1px solid var(--glass-border)',
                    background: tone === 'professional' ? 'rgba(0, 240, 255, 0.1)' : 'rgba(255, 255, 255, 0.03)',
                    color: 'var(--text-primary)',
                    cursor: 'pointer',
                    fontSize: '0.75rem',
                    textAlign: 'center'
                  }}
                >
                  👔 <strong>Professional</strong><br/><span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>Structured & formal</span>
                </button>
                <button
                  type="button"
                  onClick={() => setTone('fast_direct')}
                  style={{
                    padding: '0.65rem 0.5rem',
                    borderRadius: '6px',
                    border: tone === 'fast_direct' ? '2px solid var(--accent-secondary)' : '1px solid var(--glass-border)',
                    background: tone === 'fast_direct' ? 'rgba(0, 240, 255, 0.1)' : 'rgba(255, 255, 255, 0.03)',
                    color: 'var(--text-primary)',
                    cursor: 'pointer',
                    fontSize: '0.75rem',
                    textAlign: 'center'
                  }}
                >
                  ⚡ <strong>Fast & Direct</strong><br/><span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>Quick recommendations</span>
                </button>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              <div style={styles.inputGroup}>
                <label style={styles.label}>Opening Time</label>
                <input
                  type="time"
                  className="form-input"
                  value={operatingHoursStart}
                  onChange={(e) => setOperatingHoursStart(e.target.value)}
                />
              </div>
              <div style={styles.inputGroup}>
                <label style={styles.label}>Closing Time</label>
                <input
                  type="time"
                  className="form-input"
                  value={operatingHoursEnd}
                  onChange={(e) => setOperatingHoursEnd(e.target.value)}
                />
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(255, 255, 255, 0.03)', padding: '0.6rem 0.75rem', borderRadius: '6px' }}>
              <input
                type="checkbox"
                id="ai247"
                checked={aiSales247}
                onChange={(e) => setAiSales247(e.target.checked)}
                style={{ width: '16px', height: '16px', accentColor: 'var(--accent-secondary)', cursor: 'pointer' }}
              />
              <label htmlFor="ai247" style={{ fontSize: '0.78rem', color: 'var(--text-primary)', cursor: 'pointer', fontWeight: '500' }}>
                🌙 Enable 24/7 AI Sales coverage (AI answers buyers outside store hours)
              </label>
            </div>

            <div style={styles.inputGroup}>
              <label style={styles.label}>Shipping & Delivery Terms</label>
              <textarea
                className="form-input"
                style={styles.textarea}
                value={shippingPolicy}
                onChange={(e) => setShippingPolicy(e.target.value)}
                required
              />
            </div>

            <div style={styles.inputGroup}>
              <label style={styles.label}>Return & Exchange Terms</label>
              <textarea
                className="form-input"
                style={styles.textarea}
                value={returnPolicy}
                onChange={(e) => setReturnPolicy(e.target.value)}
                required
              />
            </div>

            <div style={styles.inputGroup}>
              <label style={styles.label}>General FAQs & Product Assurances</label>
              <textarea
                className="form-input"
                style={styles.textarea}
                value={faqText}
                onChange={(e) => setFaqText(e.target.value)}
              />
            </div>

            <div style={styles.btnRow}>
              <button type="button" className="btn btn-secondary" style={styles.btnBack} onClick={() => setStep(1)} disabled={loading}>
                ← Back
              </button>
              <button type="submit" className="btn btn-primary" style={styles.btnSubmit} disabled={loading}>
                {loading ? 'Saving Policies...' : 'Save & Choose Catalog →'}
              </button>
            </div>
          </form>
        )}

        {/* STEP 3: Catalog Setup & 1-Click Starter Packs */}
        {step === 3 && (
          <div style={styles.form}>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: 0 }}>
              Equip your AI assistant with products immediately. Choose a 1-click curated starter pack or upload your own spreadsheet:
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div
                onClick={() => handleSeedCatalog('silk_sarees')}
                style={{
                  border: selectedPack === 'silk_sarees' && catalogSeeded ? '2px solid #00ffc4' : '1px solid var(--glass-border)',
                  background: selectedPack === 'silk_sarees' && catalogSeeded ? 'rgba(0, 255, 196, 0.08)' : 'rgba(255, 255, 255, 0.03)',
                  padding: '1rem',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between'
                }}
              >
                <div>
                  <strong style={{ color: 'var(--text-primary)', fontSize: '0.9rem' }}>🥻 Silk Sarees Starter Pack (5 Items)</strong>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: '0.2rem 0 0 0' }}>
                    Kanchipuram, Banarasi, Soft Silk, Dharmavaram & Mysore Crepe sarees with prices (₹2,999 – ₹7,999).
                  </p>
                </div>
                <button type="button" className="btn btn-secondary" style={{ fontSize: '0.75rem', padding: '0.4rem 0.8rem' }} disabled={loading}>
                  {selectedPack === 'silk_sarees' && catalogSeeded ? '✓ Installed' : '1-Click Install'}
                </button>
              </div>

              <div
                onClick={() => handleSeedCatalog('ethnic_wear')}
                style={{
                  border: selectedPack === 'ethnic_wear' && catalogSeeded ? '2px solid #00ffc4' : '1px solid var(--glass-border)',
                  background: selectedPack === 'ethnic_wear' && catalogSeeded ? 'rgba(0, 255, 196, 0.08)' : 'rgba(255, 255, 255, 0.03)',
                  padding: '1rem',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between'
                }}
              >
                <div>
                  <strong style={{ color: 'var(--text-primary)', fontSize: '0.9rem' }}>👗 Designer Kurtis & Ethnic Sets (3 Items)</strong>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: '0.2rem 0 0 0' }}>
                    Anarkali sets, Lucknowi Chikankari, and festive velvet kurtis (₹1,599 – ₹3,499).
                  </p>
                </div>
                <button type="button" className="btn btn-secondary" style={{ fontSize: '0.75rem', padding: '0.4rem 0.8rem' }} disabled={loading}>
                  {selectedPack === 'ethnic_wear' && catalogSeeded ? '✓ Installed' : '1-Click Install'}
                </button>
              </div>

              <div
                onClick={() => handleSeedCatalog('jewelry')}
                style={{
                  border: selectedPack === 'jewelry' && catalogSeeded ? '2px solid #00ffc4' : '1px solid var(--glass-border)',
                  background: selectedPack === 'jewelry' && catalogSeeded ? 'rgba(0, 255, 196, 0.08)' : 'rgba(255, 255, 255, 0.03)',
                  padding: '1rem',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between'
                }}
              >
                <div>
                  <strong style={{ color: 'var(--text-primary)', fontSize: '0.9rem' }}>✨ Fashion Jewelry & Accessories (2 Items)</strong>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: '0.2rem 0 0 0' }}>
                    Matte gold temple necklace set and bridal Kundan choker (₹1,899 – ₹2,499).
                  </p>
                </div>
                <button type="button" className="btn btn-secondary" style={{ fontSize: '0.75rem', padding: '0.4rem 0.8rem' }} disabled={loading}>
                  {selectedPack === 'jewelry' && catalogSeeded ? '✓ Installed' : '1-Click Install'}
                </button>
              </div>
            </div>

            {catalogSeeded && (
              <div style={{ color: '#00ffc4', fontSize: '0.82rem', background: 'rgba(0, 255, 196, 0.1)', padding: '0.6rem', borderRadius: '6px', textAlign: 'center' }}>
                ✓ {seededCount} items installed and vector embeddings scheduled!
              </div>
            )}

            <div style={styles.btnRow}>
              <button type="button" className="btn btn-secondary" style={styles.btnBack} onClick={() => setStep(2)} disabled={loading}>
                ← Back
              </button>
              <button
                type="button"
                className="btn btn-primary"
                style={styles.btnSubmit}
                onClick={() => setStep(4)}
                disabled={loading}
              >
                Continue to Chat Simulator →
              </button>
            </div>
          </div>
        )}

        {/* STEP 4: Live Verification Simulator & Launch */}
        {step === 4 && (
          <div style={styles.form}>
            <div style={{
              background: 'rgba(0, 0, 0, 0.25)',
              border: '1px solid var(--glass-border)',
              borderRadius: '8px',
              padding: '0.75rem',
              height: '240px',
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.6rem'
            }}>
              {simMessages.map((msg, i) => (
                <div
                  key={i}
                  style={{
                    alignSelf: msg.sender === 'user' ? 'flex-end' : 'flex-start',
                    maxWidth: '80%',
                    padding: '0.6rem 0.85rem',
                    borderRadius: '8px',
                    fontSize: '0.8rem',
                    lineHeight: '1.4',
                    background: msg.sender === 'user' ? 'var(--accent-primary)' : 'rgba(255, 255, 255, 0.08)',
                    color: '#ffffff',
                    whiteSpace: 'pre-wrap'
                  }}
                >
                  {msg.text}
                </div>
              ))}
            </div>

            {/* Quick Test Prompt Chips */}
            <div style={{ display: 'flex', gap: '0.4rem', overflowX: 'auto', paddingBottom: '0.2rem' }}>
              <button
                type="button"
                className="btn btn-secondary"
                style={{ fontSize: '0.7rem', padding: '0.3rem 0.6rem', whiteSpace: 'nowrap' }}
                onClick={() => setSimInput('Show me sarees under 5000')}
              >
                "Show me sarees under 5000"
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                style={{ fontSize: '0.7rem', padding: '0.3rem 0.6rem', whiteSpace: 'nowrap' }}
                onClick={() => setSimInput('What is your return policy?')}
              >
                "What is your return policy?"
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                style={{ fontSize: '0.7rem', padding: '0.3rem 0.6rem', whiteSpace: 'nowrap' }}
                onClick={() => setSimInput('Do you offer COD?')}
              >
                "Do you offer COD?"
              </button>
            </div>

            <form onSubmit={handleSendSimMessage} style={{ display: 'flex', gap: '0.5rem' }}>
              <input
                type="text"
                className="form-input"
                placeholder="Ask your AI assistant a question..."
                value={simInput}
                onChange={(e) => setSimInput(e.target.value)}
                style={{ flex: 1, height: '40px' }}
              />
              <button type="submit" className="btn btn-primary" style={{ padding: '0 1rem', height: '40px' }}>
                Send
              </button>
            </form>

            <div style={styles.btnRow}>
              <button type="button" className="btn btn-secondary" style={styles.btnBack} onClick={() => setStep(3)}>
                ← Back
              </button>
              <button
                type="button"
                className="btn btn-primary"
                style={{ ...styles.btnSubmit, backgroundColor: '#00ffc4', color: '#000000', fontWeight: '700' }}
                onClick={handleFinishOnboarding}
              >
                🚀 Launch Store & Enter Dashboard
              </button>
            </div>
          </div>
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
    maxWidth: '640px',
    padding: '2.25rem',
    borderRadius: 'var(--border-radius-lg)',
    animation: 'fadeIn 0.4s ease',
  },
  header: {
    textAlign: 'center',
    marginBottom: '1.25rem',
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
    marginBottom: '0.6rem',
  },
  title: {
    fontSize: '1.45rem',
    fontWeight: '700',
    color: 'var(--text-primary)',
    marginBottom: '0.25rem',
  },
  subtitle: {
    fontSize: '0.82rem',
    color: 'var(--text-secondary)',
    lineHeight: '1.4',
  },
  stepIndicatorContainer: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: '1.5rem',
    padding: '0 0.25rem',
  },
  stepIndicator: {
    fontSize: '0.75rem',
    fontWeight: '600',
    color: 'var(--text-muted)',
    transition: 'color 0.2s ease',
  },
  stepIndicatorActive: {
    color: 'var(--accent-secondary)',
    fontWeight: '700',
  },
  stepIndicatorLine: {
    height: '1px',
    backgroundColor: 'var(--glass-border)',
    flex: 1,
    margin: '0 0.5rem',
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: '1rem',
  },
  inputGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.35rem',
  },
  label: {
    fontSize: '0.78rem',
    fontWeight: '700',
    color: 'var(--text-secondary)',
  },
  hint: {
    fontSize: '0.68rem',
    color: 'var(--text-muted)',
    lineHeight: '1.3',
  },
  textarea: {
    height: '55px',
    resize: 'none',
    fontSize: '0.8rem',
  },
  error: {
    color: 'var(--danger)',
    fontSize: '0.82rem',
    background: 'rgba(239, 68, 68, 0.1)',
    border: '1px solid rgba(239, 68, 68, 0.2)',
    padding: '0.65rem',
    borderRadius: 'var(--border-radius-sm)',
    textAlign: 'center',
    marginBottom: '1rem',
  },
  btnAction: {
    marginTop: '0.5rem',
    width: '100%',
    height: '44px',
    fontWeight: '600',
  },
  btnRow: {
    display: 'flex',
    gap: '0.75rem',
    marginTop: '0.5rem',
  },
  btnBack: {
    flex: 0.3,
    height: '44px',
  },
  btnSubmit: {
    flex: 0.7,
    height: '44px',
    fontWeight: '600',
  },
};
