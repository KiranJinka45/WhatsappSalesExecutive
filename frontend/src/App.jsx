import React, { useState, useEffect } from 'react';
import Auth from './components/Auth';
import Conversations from './components/Conversations';
import Catalog from './components/Catalog';
import Settings from './components/Settings';
import Analytics from './components/Analytics';

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [activeTab, setActiveTab] = useState('inbox');
  const [brandName, setBrandName] = useState('Closely Boutique');

  useEffect(() => {
    if (token) {
      fetchBrandName();
    }
  }, [token]);

  const fetchBrandName = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/brand/profile', {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setBrandName(data.name);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setToken(null);
  };

  if (!token) {
    return <Auth onLoginSuccess={(tok) => setToken(tok)} />;
  }

  return (
    <div style={styles.appContainer}>
      {/* Dashboard Top Header Navigation Bar */}
      <header className="glass-panel" style={styles.header}>
        <div style={styles.headerBrand}>
          <span style={styles.logo}>🛒</span>
          <div>
            <h1 style={styles.brandTitle}>{brandName}</h1>
            <span className="badge badge-ai" style={{ fontSize: '0.65rem' }}>Closely AI ACTIVE</span>
          </div>
        </div>

        <nav style={styles.nav}>
          <button
            className={`btn ${activeTab === 'inbox' ? 'btn-primary' : 'btn-secondary'}`}
            style={styles.navBtn}
            onClick={() => setActiveTab('inbox')}
          >
            💬 Inbox
          </button>
          <button
            className={`btn ${activeTab === 'catalog' ? 'btn-primary' : 'btn-secondary'}`}
            style={styles.navBtn}
            onClick={() => setActiveTab('catalog')}
          >
            👗 Catalog
          </button>
          <button
            className={`btn ${activeTab === 'settings' ? 'btn-primary' : 'btn-secondary'}`}
            style={styles.navBtn}
            onClick={() => setActiveTab('settings')}
          >
            ⚙️ Settings
          </button>
          <button
            className={`btn ${activeTab === 'analytics' ? 'btn-primary' : 'btn-secondary'}`}
            style={styles.navBtn}
            onClick={() => setActiveTab('analytics')}
          >
            📊 Analytics
          </button>
        </nav>

        <button className="btn btn-secondary" style={styles.logoutBtn} onClick={handleLogout}>
          Sign Out
        </button>
      </header>

      {/* Dynamic Tab Body Render */}
      <main style={styles.mainContent}>
        {activeTab === 'inbox' && <Conversations token={token} />}
        {activeTab === 'catalog' && <Catalog token={token} />}
        {activeTab === 'settings' && <Settings token={token} />}
        {activeTab === 'analytics' && <Analytics token={token} />}
      </main>
    </div>
  );
}

const styles = {
  appContainer: {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    width: '100vw',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0.75rem 2rem',
    borderBottom: '1px solid var(--glass-border)',
    borderRadius: 0,
    marginBottom: '1rem',
  },
  headerBrand: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.75rem',
  },
  logo: {
    fontSize: '1.75rem',
  },
  brandTitle: {
    fontSize: '1.25rem',
    fontWeight: '700',
    fontFamily: 'var(--font-title)',
  },
  nav: {
    display: 'flex',
    gap: '0.5rem',
  },
  navBtn: {
    padding: '0.5rem 1.25rem',
    fontSize: '0.85rem',
    borderRadius: 'var(--border-radius-sm)',
  },
  logoutBtn: {
    padding: '0.5rem 1rem',
    fontSize: '0.85rem',
    color: 'var(--text-secondary)',
  },
  mainContent: {
    flex: 1,
    overflow: 'hidden',
  },
};
