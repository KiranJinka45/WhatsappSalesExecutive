import React, { useState, useEffect } from 'react';
import { apiFetch } from '../api';

export default function PublicCatalog({ tenantSlug }) {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Extract filter parameters from URL query string
  const queryParams = new URLSearchParams(window.location.search);
  const category = queryParams.get('category') || '';
  const maxPrice = queryParams.get('max_price') || '';

  useEffect(() => {
    fetchProducts();
  }, [tenantSlug, category, maxPrice]);

  const fetchProducts = async () => {
    try {
      setLoading(true);
      const url = `/api/catalog/public/products?tenant_slug=${tenantSlug}&category=${category}&max_price=${maxPrice}`;
      const res = await apiFetch(url);
      if (res.ok) {
        const data = await res.json();
        setProducts(data);
      } else {
        const errData = await res.json();
        setError(errData.detail || 'Failed to load catalog.');
      }
    } catch (err) {
      setError('Connection error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const capitalize = (str) => {
    if (!str) return '';
    return str.charAt(0).toUpperCase() + str.slice(1);
  };

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <div style={styles.branding}>
          <div style={styles.logoCircle}>🛍️</div>
          <div>
            <h1 style={styles.brandTitle}>{capitalize(tenantSlug.replace('-', ' '))}</h1>
            <p style={styles.subtitle}>Boutique Catalog</p>
          </div>
        </div>
        {(category || maxPrice) && (
          <div style={styles.filtersBadge}>
            Filtering: {category && <span>Category: {category}</span>} {maxPrice && <span> | Max Price: ₹{maxPrice}</span>}
          </div>
        )}
      </header>

      {loading && (
        <div style={styles.loadingContainer}>
          <div className="spinner"></div>
          <p style={{ marginTop: '1rem', color: 'var(--text-secondary)' }}>Retrieving visual catalog...</p>
        </div>
      )}

      {error && (
        <div style={styles.errorContainer}>
          <p style={styles.errorText}>⚠️ {error}</p>
        </div>
      )}

      {!loading && !error && products.length === 0 && (
        <div style={styles.emptyState}>
          <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>👚</div>
          <h3>No Matching Items</h3>
          <p style={{ color: 'var(--text-secondary)' }}>We couldn't find items in this specific category or budget.</p>
        </div>
      )}

      {!loading && !error && products.length > 0 && (
        <div style={styles.grid}>
          {products.map((product) => (
            <div key={product.id} className="glass-panel card-hover" style={styles.card}>
              <div style={styles.imageContainer}>
                <img 
                  src={product.image_url} 
                  alt={product.name} 
                  style={styles.image} 
                  onError={(e) => { e.target.src = 'https://via.placeholder.com/300'; }}
                />
              </div>
              <div style={styles.details}>
                <h4 style={styles.productName}>{product.name}</h4>
                <div style={styles.priceTag}>₹{product.price.toLocaleString('en-IN')}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const styles = {
  container: {
    maxWidth: '800px',
    margin: '0 auto',
    padding: '1.5rem',
    minHeight: '100vh',
    backgroundColor: '#0a0d16',
    color: '#ffffff',
    fontFamily: '"Outfit", "Inter", sans-serif'
  },
  header: {
    borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
    paddingBottom: '1.25rem',
    marginBottom: '2rem',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.75rem'
  },
  branding: {
    display: 'flex',
    alignItems: 'center',
    gap: '1rem'
  },
  logoCircle: {
    width: '48px',
    height: '48px',
    borderRadius: '50%',
    background: 'linear-gradient(135deg, #7000ff, #00f0ff)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '1.5rem'
  },
  brandTitle: {
    fontSize: '1.4rem',
    fontWeight: '700',
    margin: 0,
    background: 'linear-gradient(135deg, #ffffff, #8b9bb4)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent'
  },
  subtitle: {
    fontSize: '0.82rem',
    color: '#00f0ff',
    margin: 0,
    fontWeight: '600',
    letterSpacing: '0.5px'
  },
  filtersBadge: {
    fontSize: '0.8rem',
    color: 'rgba(255, 255, 255, 0.6)',
    backgroundColor: 'rgba(255, 255, 255, 0.04)',
    padding: '0.4rem 0.75rem',
    borderRadius: '6px',
    border: '1px solid rgba(255, 255, 255, 0.06)',
    alignSelf: 'flex-start'
  },
  loadingContainer: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '4rem 0'
  },
  errorContainer: {
    padding: '2rem',
    textAlign: 'center',
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    borderRadius: '8px',
    border: '1px solid rgba(239, 68, 68, 0.2)'
  },
  errorText: {
    color: '#ef4444',
    margin: 0
  },
  emptyState: {
    textAlign: 'center',
    padding: '4rem 2rem',
    backgroundColor: 'rgba(255, 255, 255, 0.02)',
    borderRadius: '12px',
    border: '1px dashed rgba(255, 255, 255, 0.08)'
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
    gap: '1.25rem'
  },
  card: {
    borderRadius: '12px',
    overflow: 'hidden',
    border: '1px solid rgba(255, 255, 255, 0.06)',
    backgroundColor: 'rgba(255, 255, 255, 0.03)',
    display: 'flex',
    flexDirection: 'column'
  },
  imageContainer: {
    width: '100%',
    paddingTop: '100%', // 1:1 Aspect Ratio
    position: 'relative',
    backgroundColor: '#111522',
    borderBottom: '1px solid rgba(255, 255, 255, 0.04)'
  },
  image: {
    position: 'absolute',
    top: 0,
    left: 0,
    width: '100%',
    height: '100%',
    objectFit: 'cover'
  },
  details: {
    padding: '0.85rem',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.4rem'
  },
  productName: {
    fontSize: '0.9rem',
    fontWeight: '500',
    margin: 0,
    color: '#ffffff',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis'
  },
  priceTag: {
    fontSize: '1rem',
    fontWeight: '700',
    color: '#00f0ff'
  }
};
