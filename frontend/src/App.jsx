import React, { useState, useEffect } from 'react';
import Landing from './components/Landing';
import Auth from './components/Auth';
import Onboarding from './components/Onboarding';
import Conversations from './components/Conversations';
import Catalog from './components/Catalog';
import Settings from './components/Settings';
import Analytics from './components/Analytics';
import PublicCatalog from './components/PublicCatalog';
import { apiFetch } from './api';

export default function App() {
  const [token, setToken] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [activeTab, setActiveTab] = useState('inbox');
  const [brandName, setBrandName] = useState('Closely Boutique');
  const [brandPhone, setBrandPhone] = useState(null);
  const [publicView, setPublicView] = useState('landing'); // 'landing', 'login', 'signup'
  const [isPublicCatalog, setIsPublicCatalog] = useState(false);
  const [tenantSlug, setTenantSlug] = useState('');

  useEffect(() => {
    // Check if url path is public catalog route: /catalog/:tenant_slug
    const path = window.location.pathname;
    if (path.startsWith('/catalog/')) {
      const slug = path.split('/')[2];
      setTenantSlug(slug || '');
      setIsPublicCatalog(true);
      setCheckingAuth(false);
    } else {
      checkAuth();
    }
  }, []);

  const checkAuth = async () => {
    try {
      const res = await apiFetch('/api/auth/me');
      if (res.ok) {
        setIsAuthenticated(true);
        setToken('cookie-auth');
        await fetchBrandProfile();
      } else {
        setIsAuthenticated(false);
        setToken(null);
        setBrandPhone(null);
      }
    } catch (err) {
      console.error("Auth check failed:", err);
      setIsAuthenticated(false);
      setToken(null);
      setBrandPhone(null);
    } finally {
      setCheckingAuth(false);
    }
  };

  const fetchBrandProfile = async () => {
    try {
      const res = await apiFetch('/api/brand/profile');
      if (res.ok) {
        const data = await res.json();
        setBrandName(data.name || 'Closely Boutique');
        setBrandPhone(data.whatsapp_number || null);
      }
    } catch (err) {
      console.error("Error fetching brand profile:", err);
    }
  };

  const handleLogout = async () => {
    try {
      await apiFetch('/api/auth/logout', { method: 'POST' });
    } catch (err) {
      console.error("Logout request failed:", err);
    }
    localStorage.removeItem('closely_token');
    setToken(null);
    setIsAuthenticated(false);
    setBrandPhone(null);
    setPublicView('landing');
  };

  if (isPublicCatalog) {
    return <PublicCatalog tenantSlug={tenantSlug} />;
  }

  if (checkingAuth) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', justifyContent: 'center', alignItems: 'center', height: '100vh', backgroundColor: 'var(--bg-primary)', color: 'var(--text-primary)' }}>
        <div className="spinner"></div>
        <div style={{ fontWeight: '500', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>Loading Closely AI...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    if (publicView === 'landing') {
      return <Landing onNavigate={(view) => setPublicView(view)} />;
    }
    return (
      <Auth 
        initialMode={publicView} 
        onLoginSuccess={checkAuth}
        onBackToLanding={() => setPublicView('landing')}
      />
    );
  }

  // Authenticated but not onboarded yet
  if (!brandPhone) {
    return (
      <Onboarding 
        initialBrandName={brandName}
        onOnboardingComplete={(whatsappNum) => {
          setBrandPhone(whatsappNum);
        }}
      />
    );
  }

  return (
    <div style={styles.appContainer}>
      {/* Dashboard Top Header Navigation Bar */}
      <header className="glass-panel" style={styles.header}>
        <div style={styles.headerBrand}>
          <span style={styles.logo}>⚡</span>
          <div>
            <h1 style={styles.brandTitle}>{brandName}</h1>
            <span className="badge badge-ai" style={{ fontSize: '0.65rem', marginLeft: '0.5rem' }}>Active</span>
          </div>
        </div>

        <nav style={styles.nav}>
          <button
            className={`btn ${activeTab === 'inbox' ? 'btn-primary' : 'btn-secondary'}`}
            style={styles.navBtn}
            onClick={() => setActiveTab('inbox')}
          >
            Conversations
          </button>
          <button
            className={`btn ${activeTab === 'catalog' ? 'btn-primary' : 'btn-secondary'}`}
            style={styles.navBtn}
            onClick={() => setActiveTab('catalog')}
          >
            Product Catalog
          </button>
          <button
            className={`btn ${activeTab === 'settings' ? 'btn-primary' : 'btn-secondary'}`}
            style={styles.navBtn}
            onClick={() => setActiveTab('settings')}
          >
            System Settings
          </button>
          <button
            className={`btn ${activeTab === 'analytics' ? 'btn-primary' : 'btn-secondary'}`}
            style={styles.navBtn}
            onClick={() => setActiveTab('analytics')}
          >
            Analytics
          </button>
        </nav>

        <button className="btn btn-secondary" style={styles.logoutBtn} onClick={handleLogout}>
          Sign Out
        </button>
      </header>

      {/* Dynamic Tab Body Render */}
      <main style={styles.mainContent}>
        {activeTab === 'inbox' && <Conversations token={token} brandPhone={brandPhone} />}
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
    backgroundColor: 'var(--bg-primary)',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0.75rem 2rem',
    borderBottom: '1px solid var(--glass-border)',
    borderRadius: 0,
    backgroundColor: 'var(--bg-secondary)',
    marginBottom: '1rem',
  },
  headerBrand: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.75rem',
  },
  logo: {
    fontSize: '1.25rem',
    fontWeight: '800',
    color: 'var(--accent-primary)',
  },
  brandTitle: {
    fontSize: '1.15rem',
    fontWeight: '600',
    fontFamily: 'var(--font-title)',
    display: 'inline-block',
  },
  nav: {
    display: 'flex',
    gap: '0.5rem',
  },
  navBtn: {
    padding: '0.45rem 1rem',
    fontSize: '0.8rem',
    borderRadius: 'var(--border-radius-sm)',
  },
  logoutBtn: {
    padding: '0.45rem 0.85rem',
    fontSize: '0.8rem',
    color: 'var(--text-secondary)',
  },
  mainContent: {
    flex: 1,
    overflow: 'auto',
    padding: '0 2rem 2rem 2rem',
  },
};
