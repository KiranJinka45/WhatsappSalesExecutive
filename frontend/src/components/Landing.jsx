import React from 'react';

export default function Landing({ onNavigate }) {
  const handleScroll = (id) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <div style={styles.container}>
      {/* Public Header */}
      <header className="glass-panel" style={styles.header}>
        <div style={styles.logoGroup}>
          <span style={styles.logoIcon}>🛍️</span>
          <span style={styles.logoText}>
            Closely <span className="gradient-text" style={{ color: 'var(--accent-secondary)' }}>AI</span>
          </span>
        </div>

        <nav style={styles.navLinks}>
          <button style={styles.navLinkBtn} onClick={() => handleScroll('services')}>Services</button>
          <button style={styles.navLinkBtn} onClick={() => handleScroll('features')}>How It Works</button>
          <button style={styles.navLinkBtn} onClick={() => handleScroll('pricing')}>Pricing</button>
        </nav>

        <div style={styles.headerActions}>
          <button 
            className="btn btn-secondary" 
            style={styles.headerBtn} 
            onClick={() => onNavigate('login')}
          >
            Login
          </button>
          <button 
            className="btn btn-primary" 
            style={styles.headerBtnPrimary} 
            onClick={() => onNavigate('signup')}
          >
            Create Business Account
          </button>
        </div>
      </header>

      {/* Hero Section */}
      <section style={styles.heroSection}>
        <div style={styles.heroGlow}></div>
        <div style={styles.heroContent}>
          <span className="badge badge-ai" style={styles.heroBadge}>v1.0 Pilot Release</span>
          <h1 style={styles.heroTitle}>
            Your Autonomous <span style={{ color: 'var(--accent-secondary)' }}>AI Sales Employee</span> for Clothing Brands
          </h1>
          <p style={styles.heroSubhead}>
            Meet Closely AI. It connects to your WhatsApp business account, understands customer questions, showcases sarees & apparel directly from your catalog, and guides buyers to payment—24/7.
          </p>
          <div style={styles.heroActions}>
            <button 
              className="btn btn-primary btn-lg" 
              style={styles.heroBtnMain} 
              onClick={() => onNavigate('signup')}
            >
              Start Free 14-Day Trial
            </button>
            <button 
              className="btn btn-secondary btn-lg" 
              style={styles.heroBtnSec} 
              onClick={() => handleScroll('features')}
            >
              See How It Works
            </button>
          </div>
        </div>
      </section>

      {/* Services Section */}
      <section id="services" style={styles.section}>
        <div style={styles.sectionHeader}>
          <h2 style={styles.sectionTitle}>Built Exclusively for Fashion & Apparel Retailers</h2>
          <p style={styles.sectionSubtitle}>
            Our AI engine maps directly to the specific sales workflows clothing store owners face every day.
          </p>
        </div>

        <div style={styles.grid}>
          <div className="glass-card" style={styles.serviceCard}>
            <div style={styles.cardIcon}>🔍</div>
            <h3 style={styles.cardTitle}>Product Discovery</h3>
            <p style={styles.cardText}>
              Customers can ask for "red silk saree under 5000" or "cotton dress materials". The AI searches your inventory and replies with matching catalog photos and details.
            </p>
          </div>

          <div className="glass-card" style={styles.serviceCard}>
            <div style={styles.cardIcon}>✨</div>
            <h3 style={styles.cardTitle}>AI Recommendations</h3>
            <p style={styles.cardText}>
              Uses customer context to suggest matching blouses, borders, or coordinating items to increase your average cart value automatically.
            </p>
          </div>

          <div className="glass-card" style={styles.serviceCard}>
            <div style={styles.cardIcon}>💬</div>
            <h3 style={styles.cardTitle}>WhatsApp Automation</h3>
            <p style={styles.cardText}>
              No complex apps for buyers to install. Your AI assistant converses naturally directly inside WhatsApp chats, answering FAQs about fabric, colors, and stock.
            </p>
          </div>

          <div className="glass-card" style={styles.serviceCard}>
            <div style={styles.cardIcon}>👤</div>
            <h3 style={styles.cardTitle}>Seamless Human Takeover</h3>
            <p style={styles.cardText}>
              If a customer wants a refund, requests a heavy bulk discount, or gets frustrated, the AI halts immediately and alerts you to take over the chat.
            </p>
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section id="features" style={styles.sectionSecondary}>
        <div style={styles.sectionHeader}>
          <h2 style={styles.sectionTitle}>Get Up & Running In 10 Minutes</h2>
          <p style={styles.sectionSubtitle}>
            We make onboarding simple so you can focus on inventory and fulfillment.
          </p>
        </div>

        <div style={styles.stepsContainer}>
          <div style={styles.stepItem}>
            <div style={styles.stepBadge}>1</div>
            <h4 style={styles.stepTitle}>Register Your Brand</h4>
            <p style={styles.stepText}>Create your account and define your boutique name and store location.</p>
          </div>
          <div style={styles.stepLine}></div>
          <div style={styles.stepItem}>
            <div style={styles.stepBadge}>2</div>
            <h4 style={styles.stepTitle}>Configure AI Knowledge</h4>
            <p style={styles.stepText}>Paste your shipping fees, return window, and standard FAQs to ground the AI.</p>
          </div>
          <div style={styles.stepLine}></div>
          <div style={styles.stepItem}>
            <div style={styles.stepBadge}>3</div>
            <h4 style={styles.stepTitle}>Upload Your Catalog</h4>
            <p style={styles.stepText}>Import your CSV or Excel listing SKUs, fabrics, prices, and photo URLs.</p>
          </div>
          <div style={styles.stepLine}></div>
          <div style={styles.stepItem}>
            <div style={styles.stepBadge}>4</div>
            <h4 style={styles.stepTitle}>Activate WhatsApp</h4>
            <p style={styles.stepText}>Link your WhatsApp number and watch the AI process client chats in real time.</p>
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" style={styles.section}>
        <div style={styles.sectionHeader}>
          <h2 style={styles.sectionTitle}>Simple, Transparent Pricing</h2>
          <p style={styles.sectionSubtitle}>
            Choose the plan that matches your business volume. 14-day free trial on all plans.
          </p>
        </div>

        <div style={styles.pricingContainer}>
          {/* Starter Plan */}
          <div className="glass-panel" style={styles.priceCard}>
            <div style={styles.priceHeader}>
              <h3 style={styles.pricePlanTitle}>Starter Plan</h3>
              <p style={styles.priceDescription}>Best for boutique stores just starting to automate.</p>
              <div style={styles.priceDisplay}>
                <span style={styles.priceCurrency}>₹</span>
                <span style={styles.priceAmount}>1,999</span>
                <span style={styles.pricePeriod}>/mo</span>
              </div>
            </div>
            <ul style={styles.featureList}>
              <li style={styles.featureItem}>⚡ Dedicated AI Agent</li>
              <li style={styles.featureItem}>💬 Up to 500 active chats/mo</li>
              <li style={styles.featureItem}>📦 Up to 100 catalog products</li>
              <li style={styles.featureItem}>🔄 Standard backup & recovery</li>
              <li style={styles.featureItem}>🛡️ Basic tenant isolation</li>
            </ul>
            <button 
              className="btn btn-secondary" 
              style={styles.pricingBtn} 
              onClick={() => onNavigate('signup')}
            >
              Start Free Trial
            </button>
          </div>

          {/* Growth Plan */}
          <div className="glass-panel" style={{ ...styles.priceCard, ...styles.priceCardActive }}>
            <div style={styles.badgePopular}>RECOMMENDED</div>
            <div style={styles.priceHeader}>
              <h3 style={styles.pricePlanTitle}>Growth Plan</h3>
              <p style={styles.priceDescription}>Perfect for scaling apparel stores with high volume.</p>
              <div style={styles.priceDisplay}>
                <span style={styles.priceCurrency}>₹</span>
                <span style={styles.priceAmount}>3,999</span>
                <span style={styles.pricePeriod}>/mo</span>
              </div>
            </div>
            <ul style={styles.featureList}>
              <li style={styles.featureItem}>⚡ Premium, faster AI model</li>
              <li style={styles.featureItem}>💬 Unlimited customer chats</li>
              <li style={styles.featureItem}>📦 Up to 1,000 catalog products</li>
              <li style={styles.featureItem}>🔄 Automated backup schedules</li>
              <li style={styles.featureItem}>🛡️ Dedicated RLS security database</li>
              <li style={styles.featureItem}>📞 Priority WhatsApp line support</li>
            </ul>
            <button 
              className="btn btn-primary" 
              style={styles.pricingBtn} 
              onClick={() => onNavigate('signup')}
            >
              Start Free Trial
            </button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer style={styles.footer}>
        <div style={styles.footerContent}>
          <div style={styles.footerBrand}>
            <span>🛍️ Closely AI</span>
            <p style={styles.footerCopyright}>&copy; 2026 Closely Technologies Inc. All rights reserved.</p>
          </div>
          <div style={styles.footerLinks}>
            <a href="#services" style={styles.footerLink}>Services</a>
            <a href="#features" style={styles.footerLink}>How It Works</a>
            <a href="#pricing" style={styles.footerLink}>Pricing</a>
          </div>
        </div>
      </footer>
    </div>
  );
}

const styles = {
  container: {
    backgroundColor: 'var(--bg-primary)',
    color: 'var(--text-primary)',
    minHeight: '100vh',
    display: 'flex',
    flexDirection: 'column',
    overflowX: 'hidden',
  },
  header: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0.8rem 3rem',
    zIndex: 1000,
    backgroundColor: 'rgba(11, 15, 25, 0.85)',
    backdropFilter: 'blur(12px)',
    borderBottom: '1px solid var(--glass-border)',
    borderRadius: 0,
  },
  logoGroup: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
  },
  logoIcon: {
    fontSize: '1.5rem',
  },
  logoText: {
    fontSize: '1.25rem',
    fontWeight: '800',
    letterSpacing: '-0.02em',
  },
  navLinks: {
    display: 'flex',
    gap: '2rem',
  },
  navLinkBtn: {
    background: 'none',
    border: 'none',
    color: 'var(--text-secondary)',
    fontSize: '0.85rem',
    fontWeight: '500',
    cursor: 'pointer',
    transition: 'color 0.15s ease',
  },
  headerActions: {
    display: 'flex',
    gap: '0.75rem',
  },
  headerBtn: {
    padding: '0.45rem 1rem',
    fontSize: '0.8rem',
  },
  headerBtnPrimary: {
    padding: '0.45rem 1.15rem',
    fontSize: '0.8rem',
    fontWeight: '600',
  },
  heroSection: {
    position: 'relative',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '10rem 2rem 6rem 2rem',
    minHeight: '85vh',
    textAlign: 'center',
  },
  heroGlow: {
    position: 'absolute',
    top: '20%',
    width: '400px',
    height: '400px',
    background: 'radial-gradient(circle, rgba(79, 70, 229, 0.12) 0%, transparent 70%)',
    pointerEvents: 'none',
    zIndex: 1,
  },
  heroContent: {
    maxWidth: '850px',
    zIndex: 2,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '1.5rem',
    animation: 'fadeIn 0.6s ease',
  },
  heroBadge: {
    alignSelf: 'center',
    padding: '0.35rem 0.75rem',
    fontSize: '0.75rem',
    letterSpacing: '0.05em',
  },
  heroTitle: {
    fontSize: '3.2rem',
    lineHeight: '1.15',
    fontWeight: '800',
    letterSpacing: '-0.03em',
    color: 'var(--text-primary)',
  },
  heroSubhead: {
    fontSize: '1.15rem',
    lineHeight: '1.6',
    color: 'var(--text-secondary)',
    maxWidth: '700px',
  },
  heroActions: {
    display: 'flex',
    gap: '1rem',
    marginTop: '1rem',
  },
  heroBtnMain: {
    padding: '0.75rem 1.75rem',
    fontSize: '0.95rem',
    fontWeight: '600',
  },
  heroBtnSec: {
    padding: '0.75rem 1.75rem',
    fontSize: '0.95rem',
  },
  section: {
    padding: '6rem 2rem',
    maxWidth: '1100px',
    margin: '0 auto',
    width: '100%',
  },
  sectionSecondary: {
    padding: '6rem 2rem',
    backgroundColor: '#0e1322',
    width: '100vw',
    alignSelf: 'center',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
  },
  sectionHeader: {
    textAlign: 'center',
    marginBottom: '3.5rem',
    maxWidth: '650px',
    margin: '0 auto 3.5rem auto',
  },
  sectionTitle: {
    fontSize: '2rem',
    fontWeight: '700',
    letterSpacing: '-0.02em',
    marginBottom: '0.75rem',
  },
  sectionSubtitle: {
    fontSize: '0.95rem',
    color: 'var(--text-secondary)',
    lineHeight: '1.5',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
    gap: '1.5rem',
    marginTop: '1rem',
  },
  serviceCard: {
    borderRadius: 'var(--border-radius-md)',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.85rem',
    padding: '2rem',
  },
  cardIcon: {
    fontSize: '2rem',
    marginBottom: '0.25rem',
  },
  cardTitle: {
    fontSize: '1.1rem',
    fontWeight: '700',
  },
  cardText: {
    fontSize: '0.85rem',
    color: 'var(--text-secondary)',
    lineHeight: '1.5',
  },
  stepsContainer: {
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    maxWidth: '1100px',
    width: '100%',
    gap: '1.5rem',
    marginTop: '1rem',
    flexWrap: 'wrap',
  },
  stepItem: {
    flex: 1,
    minWidth: '200px',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    textAlign: 'center',
    gap: '0.75rem',
  },
  stepBadge: {
    width: '40px',
    height: '40px',
    borderRadius: '50%',
    backgroundColor: 'var(--accent-primary)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '1rem',
    fontWeight: '700',
    color: 'white',
    boxShadow: '0 0 15px rgba(79, 70, 229, 0.4)',
  },
  stepTitle: {
    fontSize: '1rem',
    fontWeight: '700',
  },
  stepText: {
    fontSize: '0.8rem',
    color: 'var(--text-secondary)',
    lineHeight: '1.4',
  },
  stepLine: {
    height: '2px',
    backgroundColor: 'var(--glass-border)',
    flex: 0.5,
    marginTop: '20px',
    minWidth: '20px',
  },
  pricingContainer: {
    display: 'flex',
    justifyContent: 'center',
    gap: '2rem',
    flexWrap: 'wrap',
    marginTop: '1rem',
    alignItems: 'stretch',
  },
  priceCard: {
    flex: 1,
    maxWidth: '400px',
    minWidth: '300px',
    padding: '2.5rem 2rem',
    borderRadius: 'var(--border-radius-lg)',
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'space-between',
    gap: '2rem',
    position: 'relative',
    backgroundColor: '#111827',
  },
  priceCardActive: {
    borderColor: 'var(--accent-primary)',
    boxShadow: '0 10px 30px rgba(79, 70, 229, 0.15)',
    transform: 'scale(1.03)',
  },
  badgePopular: {
    position: 'absolute',
    top: '-12px',
    right: '24px',
    backgroundColor: 'var(--accent-primary)',
    color: 'white',
    fontSize: '0.65rem',
    fontWeight: '800',
    padding: '0.3rem 0.65rem',
    borderRadius: '4px',
    letterSpacing: '0.05em',
  },
  priceHeader: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.5rem',
  },
  pricePlanTitle: {
    fontSize: '1.4rem',
    fontWeight: '700',
  },
  priceDescription: {
    fontSize: '0.8rem',
    color: 'var(--text-secondary)',
    lineHeight: '1.4',
  },
  priceDisplay: {
    display: 'flex',
    alignItems: 'baseline',
    marginTop: '0.5rem',
  },
  priceCurrency: {
    fontSize: '1.4rem',
    fontWeight: '600',
    color: 'var(--text-primary)',
  },
  priceAmount: {
    fontSize: '2.5rem',
    fontWeight: '800',
    color: 'var(--text-primary)',
    letterSpacing: '-0.02em',
  },
  pricePeriod: {
    fontSize: '0.85rem',
    color: 'var(--text-secondary)',
    marginLeft: '0.2rem',
  },
  featureList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.8rem',
    listStyle: 'none',
  },
  featureItem: {
    fontSize: '0.85rem',
    color: 'var(--text-secondary)',
  },
  pricingBtn: {
    width: '100%',
    padding: '0.75rem',
    fontWeight: '600',
  },
  footer: {
    marginTop: 'auto',
    borderTop: '1px solid var(--glass-border)',
    padding: '3rem 2rem',
    backgroundColor: '#070a12',
  },
  footerContent: {
    maxWidth: '1100px',
    margin: '0 auto',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: '1.5rem',
  },
  footerBrand: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.35rem',
  },
  footerCopyright: {
    fontSize: '0.75rem',
    color: 'var(--text-muted)',
  },
  footerLinks: {
    display: 'flex',
    gap: '1.5rem',
  },
  footerLink: {
    textDecoration: 'none',
    color: 'var(--text-secondary)',
    fontSize: '0.8rem',
    fontWeight: '500',
    transition: 'color 0.15s ease',
  },
};
