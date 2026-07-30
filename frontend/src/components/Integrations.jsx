import React, { useState, useEffect } from 'react';

const INTEGRATION_TEMPLATES = [
  {
    id: 'shopify',
    name: 'Shopify Store',
    description: 'Sync products, import catalogs, and send automated abandoned cart/checkout recovery messages.',
    logo: '🛍️',
    color: '#96bf48',
    fields: [
      { name: 'storeUrl', label: 'Shopify Store URL (myshopify.com)', type: 'text', placeholder: 'your-store.myshopify.com' },
      { name: 'accessToken', label: 'Admin API Access Token', type: 'password', placeholder: 'shpat_xxxxxxxxxxxxxxxxxxxxxxxx' }
    ]
  },
  {
    id: 'razorpay',
    name: 'Razorpay Payment',
    description: 'Generate payment links automatically and send payment success receipts with invoices.',
    logo: '💳',
    color: '#0b72e7',
    fields: [
      { name: 'keyId', label: 'Razorpay Key ID', type: 'text', placeholder: 'rzp_live_xxxxxxxx' },
      { name: 'keySecret', label: 'Razorpay Key Secret', type: 'password', placeholder: '••••••••••••••••' }
    ]
  },
  {
    id: 'webengage',
    name: 'WebEngage Marketing',
    description: 'Sync customer events, segment marketing campaigns, and trigger automated workflows.',
    logo: '📊',
    color: '#f15a24',
    fields: [
      { name: 'licenseCode', label: 'License Code', type: 'text', placeholder: 'xx_xxxxxx' },
      { name: 'apiKey', label: 'Rest API Key', type: 'password', placeholder: '••••••••••••••••' }
    ]
  },
  {
    id: 'leadsquared',
    name: 'LeadSquared CRM',
    description: 'Push WhatsApp leads directly to CRM, assign owners, and sync conversation logs.',
    logo: '📈',
    color: '#00aa55',
    fields: [
      { name: 'accessKey', label: 'Access Key', type: 'text', placeholder: 'u_xxxxxxxxxxx' },
      { name: 'secretKey', label: 'Secret Key', type: 'password', placeholder: '••••••••••••••••' }
    ]
  },
  {
    id: 'integrately',
    name: 'Integrately Integration',
    description: 'Connect your WhatsApp AI Assistant to 1000+ third-party business apps.',
    logo: '🔄',
    color: '#6f42c1',
    fields: [
      { name: 'webhookUrl', label: 'Integrately Webhook URL', type: 'text', placeholder: 'https://webhooks.integrately.com/a/xxxxxx' }
    ]
  },
  {
    id: 'webhooks',
    name: 'Custom Webhook APIs',
    description: 'Deliver delivery status reports and incoming messages to your own custom server endpoint.',
    logo: '🔌',
    color: '#e83e8c',
    fields: [
      { name: 'targetUrl', label: 'Target Webhook URL', type: 'text', placeholder: 'https://api.yourdomain.com/webhooks/whatsapp' },
      { name: 'secretToken', label: 'Signature Verification Token', type: 'password', placeholder: 'Webhook auth secret key' }
    ]
  }
];

const INDUSTRIES = [
  {
    id: 'ecommerce',
    name: 'E-Commerce',
    icon: '🛒',
    details: 'Automated order confirmation, real-time tracking links, instant support for exchange requests, and visual image-matching saree catalog searches.'
  },
  {
    id: 'education',
    name: 'Education & Academies',
    icon: '🎓',
    details: 'Send automated admission reminders, fee receipts, class schedules, exam schedules, and coordinate course enrollment updates.'
  },
  {
    id: 'healthcare',
    name: 'Healthcare & Clinics',
    icon: '🏥',
    details: 'Manage appointment bookings, prescription deliveries, automated doctor availability updates, and follow-up consultation reminders.'
  },
  {
    id: 'finance',
    name: 'Finance & Insurance',
    icon: '🏦',
    details: 'Send premium payment alerts, loan verification status, policy document links, secure account notifications, and interest rate calculators.'
  },
  {
    id: 'automobile',
    name: 'Automobile Dealerships',
    icon: '🚗',
    details: 'Test drive scheduler, regular maintenance alerts, insurance renewal details, catalog updates for new model launches, and accessory price list query.'
  },
  {
    id: 'realestate',
    name: 'Real Estate & Property',
    icon: '🏠',
    details: 'Schedule site visits, share property images and brochures, filter properties by budget and layout, and auto-sync prospective buyers with CRM.'
  },
  {
    id: 'it_services',
    name: 'IT Services & Internet',
    icon: '💻',
    details: 'Automate ticket creation, service SLA notifications, server uptime status reports, invoice payment link dispatch, and subscription management.'
  },
  {
    id: 'events_webinars',
    name: 'Events & Webinars',
    icon: '📅',
    details: 'Dispatch joining credentials, tickets with QR codes, daily webinar reminders, interactive feedback collection, and certificate download links.'
  }
];

export default function Integrations() {
  const [activeSettingsTab, setActiveSettingsTab] = useState('integrations');
  const [connections, setConnections] = useState(() => {
    const saved = localStorage.getItem('closely_integrations');
    return saved ? JSON.parse(saved) : {};
  });
  const [editingId, setEditingId] = useState(null);
  const [formData, setFormData] = useState({});
  const [saving, setSaving] = useState(false);
  const [activeIndustry, setActiveIndustry] = useState('ecommerce');

  useEffect(() => {
    localStorage.setItem('closely_integrations', JSON.stringify(connections));
  }, [connections]);

  const handleToggle = (id) => {
    if (connections[id]) {
      // Disconnect
      const updated = { ...connections };
      delete updated[id];
      setConnections(updated);
    } else {
      // Open settings configuration dialog
      setEditingId(id);
      setFormData({});
    }
  };

  const handleSave = (e) => {
    e.preventDefault();
    setSaving(true);
    setTimeout(() => {
      setConnections({
        ...connections,
        [editingId]: { ...formData, connectedAt: new Date().toISOString() }
      });
      setSaving(false);
      setEditingId(null);
    }, 1200);
  };

  return (
    <div style={styles.container}>
      <div style={styles.sidebar}>
        <div style={styles.tabContainer}>
          <button 
            style={{...styles.tabBtn, ...(activeSettingsTab === 'integrations' ? styles.activeTabBtn : {})}}
            onClick={() => setActiveSettingsTab('integrations')}
          >
            🔌 Explore Integrations
          </button>
          <button 
            style={{...styles.tabBtn, ...(activeSettingsTab === 'industries' ? styles.activeTabBtn : {})}}
            onClick={() => setActiveSettingsTab('industries')}
          >
            🏢 Industry Solutions
          </button>
        </div>

        <div style={styles.cardHeader}>
          <h2 style={styles.sidebarTitle}>Closely Hub</h2>
          <p style={styles.sidebarText}>Powering Sri Siddi Vinayaka Silk Sarees with robust third-party ecosystem connectors like AiSensy & Wati.</p>
        </div>
      </div>

      <div style={styles.content}>
        {activeSettingsTab === 'integrations' ? (
          <div>
            <div style={styles.headerArea}>
              <h1 style={styles.title}>All Third-Party Integrations</h1>
              <p style={styles.subtitle}>Connect your WhatsApp AI engine to CRM tools, payment systems, and e-commerce stores to trigger workflows dynamically.</p>
            </div>

            <div style={styles.grid}>
              {INTEGRATION_TEMPLATES.map((item) => {
                const isConnected = !!connections[item.id];
                return (
                  <div key={item.id} className="glass-panel" style={styles.card}>
                    <div style={styles.cardTop}>
                      <div style={{...styles.logoWrapper, backgroundColor: `${item.color}20`}}>
                        <span style={{ fontSize: '1.8rem' }}>{item.logo}</span>
                      </div>
                      <div style={styles.statusArea}>
                        <span style={{
                          ...styles.statusBadge,
                          backgroundColor: isConnected ? 'rgba(76, 175, 80, 0.15)' : 'rgba(255, 255, 255, 0.05)',
                          color: isConnected ? '#4caf50' : '#888'
                        }}>
                          {isConnected ? '● Connected' : 'Disconnected'}
                        </span>
                      </div>
                    </div>

                    <h3 style={styles.cardName}>{item.name}</h3>
                    <p style={styles.cardDesc}>{item.description}</p>

                    <div style={styles.cardAction}>
                      <button 
                        style={{...styles.actionBtn, ...(isConnected ? styles.disconnectBtn : styles.connectBtn)}}
                        onClick={() => handleToggle(item.id)}
                      >
                        {isConnected ? 'Disconnect' : 'Connect'}
                      </button>
                      
                      {isConnected && (
                        <button 
                          style={styles.configureBtn}
                          onClick={() => {
                            setEditingId(item.id);
                            setFormData(connections[item.id] || {});
                          }}
                        >
                          Configure
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {editingId && (
              <div style={styles.modalBackdrop}>
                <div className="glass-panel" style={styles.modal}>
                  <div style={styles.modalHeader}>
                    <h3 style={styles.modalTitle}>
                      Connect {INTEGRATION_TEMPLATES.find(t => t.id === editingId)?.name}
                    </h3>
                    <button style={styles.closeBtn} onClick={() => setEditingId(null)}>×</button>
                  </div>

                  <form onSubmit={handleSave}>
                    <div style={styles.modalBody}>
                      <p style={styles.modalSubtitle}>Provide credentials to securely integrate this connector with Closely AI engine.</p>
                      {INTEGRATION_TEMPLATES.find(t => t.id === editingId)?.fields.map((field) => (
                        <div key={field.name} style={styles.formGroup}>
                          <label style={styles.label}>{field.label}</label>
                          <input
                            type={field.type}
                            required
                            style={styles.input}
                            placeholder={field.placeholder}
                            value={formData[field.name] || ''}
                            onChange={(e) => setFormData({...formData, [field.name]: e.target.value})}
                          />
                        </div>
                      ))}
                    </div>

                    <div style={styles.modalFooter}>
                      <button type="button" style={styles.cancelBtn} onClick={() => setEditingId(null)}>
                        Cancel
                      </button>
                      <button type="submit" disabled={saving} style={styles.saveBtn}>
                        {saving ? 'Connecting...' : 'Save & Connect'}
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div>
            <div style={styles.headerArea}>
              <h1 style={styles.title}>Industry Pre-configurations</h1>
              <p style={styles.subtitle}>Explore how the Conversational AI state machine alters its intent structures to support varied industry verticals.</p>
            </div>

            <div style={styles.industriesContainer}>
              <div style={styles.industriesList}>
                {INDUSTRIES.map((ind) => (
                  <button
                    key={ind.id}
                    style={{
                      ...styles.industryListItem,
                      ...(activeIndustry === ind.id ? styles.activeIndustryItem : {})
                    }}
                    onClick={() => setActiveIndustry(ind.id)}
                  >
                    <span style={{ marginRight: '0.75rem' }}>{ind.icon}</span>
                    {ind.name}
                  </button>
                ))}
              </div>

              <div className="glass-panel" style={styles.industryDetails}>
                <div style={styles.industryDetailHeader}>
                  <span style={styles.detailIcon}>{INDUSTRIES.find(i => i.id === activeIndustry)?.icon}</span>
                  <h2 style={styles.detailTitle}>{INDUSTRIES.find(i => i.id === activeIndustry)?.name} Vertical</h2>
                </div>
                
                <p style={styles.detailText}>
                  {INDUSTRIES.find(i => i.id === activeIndustry)?.details}
                </p>

                <div style={styles.setupCard}>
                  <h4 style={styles.setupCardTitle}>💡 System Grounding Strategy</h4>
                  <p style={styles.setupCardText}>
                    Switching to this vertical automatically updates the system grounding instructions in Gemini Flash, tailoring response scripts to target specific intent classifications such as bookings, scheduling, or catalog mapping.
                  </p>
                  <button 
                    style={styles.activateVerticalBtn}
                    onClick={() => alert(`Activated ${INDUSTRIES.find(i => i.id === activeIndustry)?.name} vertical pre-configuration!`)}
                  >
                    Activate {INDUSTRIES.find(i => i.id === activeIndustry)?.name} Grounding
                  </button>
                </div>
              </div>
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
    height: '100%',
    width: '100%',
    color: 'var(--text-primary)',
    fontFamily: "'Outfit', 'Inter', sans-serif"
  },
  sidebar: {
    width: '280px',
    borderRight: '1px solid var(--glass-border)',
    padding: '1.5rem',
    display: 'flex',
    flexDirection: 'column',
    gap: '2rem',
    backgroundColor: 'rgba(255, 255, 255, 0.02)'
  },
  tabContainer: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.5rem'
  },
  tabBtn: {
    background: 'none',
    border: 'none',
    color: 'var(--text-secondary)',
    padding: '0.8rem 1rem',
    borderRadius: '8px',
    textAlign: 'left',
    cursor: 'pointer',
    fontSize: '0.9rem',
    fontWeight: '500',
    transition: 'all 0.2s ease',
  },
  activeTabBtn: {
    backgroundColor: 'rgba(255, 255, 255, 0.08)',
    color: '#00ffc4',
    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.1)',
  },
  cardHeader: {
    marginTop: 'auto',
    padding: '1rem',
    borderRadius: '12px',
    backgroundColor: 'rgba(255, 255, 255, 0.03)',
    border: '1px solid rgba(255, 255, 255, 0.05)'
  },
  sidebarTitle: {
    fontSize: '1rem',
    fontWeight: '600',
    marginBottom: '0.5rem',
    color: '#00ffc4'
  },
  sidebarText: {
    fontSize: '0.75rem',
    color: 'var(--text-secondary)',
    lineHeight: '1.4'
  },
  content: {
    flex: 1,
    padding: '2rem',
    overflowY: 'auto'
  },
  headerArea: {
    marginBottom: '2rem'
  },
  title: {
    fontSize: '1.75rem',
    fontWeight: '700',
    marginBottom: '0.5rem',
    background: 'linear-gradient(to right, #ffffff, #00ffc4)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent'
  },
  subtitle: {
    fontSize: '0.9rem',
    color: 'var(--text-secondary)',
    maxWidth: '700px',
    lineHeight: '1.5'
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
    gap: '1.5rem',
    marginBottom: '2rem'
  },
  card: {
    padding: '1.5rem',
    display: 'flex',
    flexDirection: 'column',
    gap: '1rem',
    borderRadius: '16px',
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    cursor: 'default',
    '&:hover': {
      transform: 'translateY(-4px)',
      boxShadow: '0 8px 24px rgba(0, 255, 196, 0.08)'
    }
  },
  cardTop: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center'
  },
  logoWrapper: {
    width: '48px',
    height: '48px',
    borderRadius: '12px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center'
  },
  statusArea: {
    fontSize: '0.75rem'
  },
  statusBadge: {
    padding: '0.25rem 0.6rem',
    borderRadius: '20px',
    fontWeight: '600'
  },
  cardName: {
    fontSize: '1.1rem',
    fontWeight: '600'
  },
  cardDesc: {
    fontSize: '0.8rem',
    color: 'var(--text-secondary)',
    lineHeight: '1.4',
    flex: 1
  },
  cardAction: {
    display: 'flex',
    gap: '0.75rem',
    marginTop: '0.5rem'
  },
  actionBtn: {
    flex: 1,
    padding: '0.6rem',
    borderRadius: '8px',
    border: 'none',
    fontWeight: '600',
    fontSize: '0.8rem',
    cursor: 'pointer',
    transition: 'all 0.2s'
  },
  connectBtn: {
    backgroundColor: '#00ffc4',
    color: '#080c10',
    '&:hover': {
      boxShadow: '0 0 12px rgba(0, 255, 196, 0.4)'
    }
  },
  disconnectBtn: {
    backgroundColor: 'rgba(244, 67, 54, 0.15)',
    color: '#f44336',
    border: '1px solid rgba(244, 67, 54, 0.3)'
  },
  configureBtn: {
    padding: '0.6rem 0.8rem',
    borderRadius: '8px',
    border: '1px solid var(--glass-border)',
    background: 'none',
    color: 'var(--text-primary)',
    fontWeight: '500',
    fontSize: '0.8rem',
    cursor: 'pointer'
  },
  modalBackdrop: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.7)',
    backdropFilter: 'blur(8px)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000
  },
  modal: {
    width: '420px',
    borderRadius: '16px',
    padding: '1.5rem',
    border: '1px solid var(--glass-border)',
    boxShadow: '0 20px 40px rgba(0, 0, 0, 0.4)'
  },
  modalHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '1rem'
  },
  modalTitle: {
    fontSize: '1.2rem',
    fontWeight: '600'
  },
  closeBtn: {
    background: 'none',
    border: 'none',
    color: 'var(--text-secondary)',
    fontSize: '1.5rem',
    cursor: 'pointer'
  },
  modalSubtitle: {
    fontSize: '0.8rem',
    color: 'var(--text-secondary)',
    marginBottom: '1.5rem'
  },
  modalBody: {
    display: 'flex',
    flexDirection: 'column',
    gap: '1rem',
    marginBottom: '1.5rem'
  },
  formGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.4rem'
  },
  label: {
    fontSize: '0.8rem',
    color: 'var(--text-secondary)',
    fontWeight: '500'
  },
  input: {
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    border: '1px solid var(--glass-border)',
    borderRadius: '8px',
    padding: '0.75rem',
    color: 'var(--text-primary)',
    fontSize: '0.85rem',
    outline: 'none'
  },
  modalFooter: {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '0.75rem'
  },
  cancelBtn: {
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    border: '1px solid var(--glass-border)',
    borderRadius: '8px',
    color: 'var(--text-primary)',
    padding: '0.6rem 1.2rem',
    fontSize: '0.85rem',
    cursor: 'pointer'
  },
  saveBtn: {
    backgroundColor: '#00ffc4',
    border: 'none',
    borderRadius: '8px',
    color: '#080c10',
    padding: '0.6rem 1.2rem',
    fontSize: '0.85rem',
    fontWeight: '600',
    cursor: 'pointer'
  },
  industriesContainer: {
    display: 'flex',
    gap: '2rem',
    height: '450px'
  },
  industriesList: {
    width: '260px',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.4rem',
    overflowY: 'auto'
  },
  industryListItem: {
    display: 'flex',
    alignItems: 'center',
    padding: '0.85rem 1rem',
    borderRadius: '10px',
    backgroundColor: 'rgba(255, 255, 255, 0.02)',
    border: '1px solid rgba(255, 255, 255, 0.03)',
    color: 'var(--text-secondary)',
    textAlign: 'left',
    fontSize: '0.9rem',
    fontWeight: '500',
    cursor: 'pointer',
    transition: 'all 0.2s'
  },
  activeIndustryItem: {
    backgroundColor: 'rgba(255, 255, 255, 0.06)',
    borderColor: '#00ffc4',
    color: '#00ffc4'
  },
  industryDetails: {
    flex: 1,
    padding: '2rem',
    borderRadius: '16px',
    display: 'flex',
    flexDirection: 'column',
    gap: '1.5rem',
    backgroundColor: 'var(--bg-secondary)',
    border: '1px solid var(--glass-border)'
  },
  industryDetailHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '1rem'
  },
  detailIcon: {
    fontSize: '2.5rem'
  },
  detailTitle: {
    fontSize: '1.4rem',
    fontWeight: '600'
  },
  detailText: {
    fontSize: '0.95rem',
    color: 'var(--text-secondary)',
    lineHeight: '1.6'
  },
  setupCard: {
    marginTop: 'auto',
    padding: '1.25rem',
    borderRadius: '12px',
    backgroundColor: 'rgba(0, 255, 196, 0.03)',
    border: '1px solid rgba(0, 255, 196, 0.1)',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.75rem'
  },
  setupCardTitle: {
    fontSize: '0.9rem',
    fontWeight: '600',
    color: '#00ffc4'
  },
  setupCardText: {
    fontSize: '0.8rem',
    color: 'var(--text-secondary)',
    lineHeight: '1.4'
  },
  activateVerticalBtn: {
    alignSelf: 'flex-start',
    backgroundColor: 'transparent',
    border: '1px solid #00ffc4',
    color: '#00ffc4',
    padding: '0.5rem 1rem',
    borderRadius: '6px',
    fontSize: '0.8rem',
    fontWeight: '600',
    cursor: 'pointer',
    transition: 'all 0.2s',
    '&:hover': {
      backgroundColor: '#00ffc4',
      color: '#080c10'
    }
  }
};
