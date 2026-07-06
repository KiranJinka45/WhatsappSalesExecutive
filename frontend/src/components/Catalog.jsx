import React, { useState, useEffect } from 'react';

export default function Catalog({ token }) {
  const [products, setProducts] = useState([]);
  const [sku, setSku] = useState('');
  const [name, setName] = useState('');
  const [price, setPrice] = useState('');
  const [color, setColor] = useState('');
  const [fabric, setFabric] = useState('');
  const [categoryName, setCategoryName] = useState('');
  const [gender, setGender] = useState('Women');
  const [sizes, setSizes] = useState('Free Size');
  const [stockCount, setStockCount] = useState('10');
  const [description, setDescription] = useState('');
  const [file, setFile] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);

  const baseUrl = 'http://localhost:8000';

  useEffect(() => {
    fetchProducts();
  }, [searchQuery]);

  const fetchProducts = async () => {
    try {
      const url = searchQuery 
        ? `${baseUrl}/api/catalog/products?q=${encodeURIComponent(searchQuery)}`
        : `${baseUrl}/api/catalog/products`;
      
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setProducts(data);
      }
    } catch (err) {
      console.error("Error fetching products:", err);
    }
  };

  const handleManualSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    const sizeArray = sizes.split(',').map(s => s.strip ? s.strip() : s.trim()).filter(Boolean);

    const payload = {
      sku,
      name,
      price: parseFloat(price),
      color,
      fabric,
      category_name: categoryName,
      gender,
      sizes: sizeArray,
      stock_count: parseInt(stockCount),
      description,
      image_urls: [],
      video_urls: []
    };

    try {
      const res = await fetch(`${baseUrl}/api/catalog/products`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to create product.');
      }

      setSuccess('Product created successfully!');
      setSku('');
      setName('');
      setPrice('');
      setColor('');
      setFabric('');
      setCategoryName('');
      setDescription('');
      fetchProducts();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleUploadCSV = async (e) => {
    e.preventDefault();
    if (!file) return;

    setError('');
    setSuccess('');
    setLoading(true);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`${baseUrl}/api/catalog/upload`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Bulk upload failed.');
      }

      const data = await res.json();
      setSuccess(`Upload success! Created ${data.created} and updated ${data.updated} items.`);
      setFile(null);
      fetchProducts();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteProduct = async (id) => {
    if (!window.confirm("Are you sure you want to delete this product?")) return;
    try {
      const res = await fetch(`${baseUrl}/api/catalog/products/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        fetchProducts();
      }
    } catch (err) {
      console.error("Error deleting product:", err);
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.leftCol}>
        {/* 1. Bulk Catalog Upload Zone */}
        <div className="glass-panel" style={styles.card}>
          <h3>Bulk Catalog Sync (CSV)</h3>
          <p style={styles.subtitle}>Upload CSV to bulk create/sync products and compute vector embeddings.</p>
          
          <form onSubmit={handleUploadCSV} style={styles.uploadForm}>
            <input 
              type="file" 
              accept=".csv"
              className="form-input"
              onChange={(e) => setFile(e.target.files[0])}
              required
            />
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'Processing & Embedding...' : '⬆️ Sync Catalog'}
            </button>
          </form>
        </div>

        {/* 2. Manual Add Product Form */}
        <div className="glass-panel" style={styles.card}>
          <h3>Add Product Manually</h3>
          
          <form onSubmit={handleManualSubmit} style={styles.manualForm}>
            <div style={styles.formRow}>
              <div style={styles.inputGroup}>
                <label style={styles.label}>SKU *</label>
                <input type="text" className="form-input" value={sku} onChange={e => setSku(e.target.value)} required />
              </div>
              <div style={styles.inputGroup}>
                <label style={styles.label}>Name *</label>
                <input type="text" className="form-input" value={name} onChange={e => setName(e.target.value)} required />
              </div>
            </div>

            <div style={styles.formRow}>
              <div style={styles.inputGroup}>
                <label style={styles.label}>Price (INR) *</label>
                <input type="number" className="form-input" value={price} onChange={e => setPrice(e.target.value)} required />
              </div>
              <div style={styles.inputGroup}>
                <label style={styles.label}>Color *</label>
                <input type="text" className="form-input" placeholder="Black" value={color} onChange={e => setColor(e.target.value)} required />
              </div>
            </div>

            <div style={styles.formRow}>
              <div style={styles.inputGroup}>
                <label style={styles.label}>Fabric</label>
                <input type="text" className="form-input" placeholder="Silk" value={fabric} onChange={e => setFabric(e.target.value)} />
              </div>
              <div style={styles.inputGroup}>
                <label style={styles.label}>Category</label>
                <input type="text" className="form-input" placeholder="Sarees" value={categoryName} onChange={e => setCategoryName(e.target.value)} />
              </div>
            </div>

            <div style={styles.formRow}>
              <div style={styles.inputGroup}>
                <label style={styles.label}>Gender</label>
                <select className="form-input" value={gender} onChange={e => setGender(e.target.value)}>
                  <option value="Women">Women</option>
                  <option value="Men">Men</option>
                  <option value="Unisex">Unisex</option>
                </select>
              </div>
              <div style={styles.inputGroup}>
                <label style={styles.label}>Sizes (comma separated)</label>
                <input type="text" className="form-input" value={sizes} onChange={e => setSizes(e.target.value)} />
              </div>
              <div style={styles.inputGroup}>
                <label style={styles.label}>Stock</label>
                <input type="number" className="form-input" value={stockCount} onChange={e => setStockCount(e.target.value)} />
              </div>
            </div>

            <div style={styles.inputGroup}>
              <label style={styles.label}>Description</label>
              <textarea className="form-input" style={styles.textarea} value={description} onChange={e => setDescription(e.target.value)} />
            </div>

            {error && <div style={styles.error}>{error}</div>}
            {success && <div style={styles.success}>{success}</div>}

            <button type="submit" className="btn btn-primary" style={{ width: '100%' }}>Create Product</button>
          </form>
        </div>
      </div>

      {/* 3. Product Inventory List */}
      <div className="glass-panel" style={styles.rightCol}>
        <div style={styles.header}>
          <h3>Product Inventory ({products.length})</h3>
          <input
            type="text"
            className="form-input"
            style={styles.searchBar}
            placeholder="🔍 Search products semantically..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        <div style={styles.tableWrapper}>
          <table style={styles.table}>
            <thead>
              <tr style={styles.thRow}>
                <th style={styles.th}>SKU</th>
                <th style={styles.th}>Name</th>
                <th style={styles.th}>Price</th>
                <th style={styles.th}>Color</th>
                <th style={styles.th}>Fabric</th>
                <th style={styles.th}>Sizes</th>
                <th style={styles.th}>Stock</th>
                <th style={styles.th}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {products.length === 0 ? (
                <tr>
                  <td colSpan="8" style={styles.emptyTd}>No products in catalog. Upload a CSV or add manually to start.</td>
                </tr>
              ) : (
                products.map((prod) => (
                  <tr key={prod.id} style={styles.trRow}>
                    <td style={styles.td}>{prod.sku}</td>
                    <td style={styles.td}><strong>{prod.name}</strong></td>
                    <td style={styles.td}>₹{prod.price}</td>
                    <td style={styles.td}>{prod.color}</td>
                    <td style={styles.td}>{prod.fabric || 'N/A'}</td>
                    <td style={styles.td}>{prod.sizes.join(', ')}</td>
                    <td style={styles.td}>
                      <span className={`badge ${prod.stock_count > 0 ? 'badge-success' : 'badge-human'}`} style={{ textTransform: 'none' }}>
                        {prod.stock_count} left
                      </span>
                    </td>
                    <td style={styles.td}>
                      <button 
                        className="btn btn-secondary" 
                        style={styles.deleteBtn}
                        onClick={() => handleDeleteProduct(prod.id)}
                      >
                        🗑️
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

const styles = {
  container: {
    display: 'flex',
    gap: '1rem',
    height: 'calc(100vh - 90px)',
    padding: '0 1rem',
  },
  leftCol: {
    width: '420px',
    display: 'flex',
    flexDirection: 'column',
    gap: '1rem',
    overflowY: 'auto',
  },
  rightCol: {
    flex: 1,
    borderRadius: 'var(--border-radius-md)',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  },
  card: {
    padding: '1.25rem',
    borderRadius: 'var(--border-radius-md)',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.75rem',
  },
  subtitle: {
    fontSize: '0.8rem',
    color: 'var(--text-secondary)',
  },
  uploadForm: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.75rem',
  },
  manualForm: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.9rem',
  },
  formRow: {
    display: 'flex',
    gap: '0.75rem',
  },
  inputGroup: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    gap: '0.3rem',
  },
  label: {
    fontSize: '0.75rem',
    fontWeight: '700',
    color: 'var(--text-secondary)',
  },
  textarea: {
    height: '60px',
    resize: 'none',
  },
  error: {
    color: 'var(--danger)',
    fontSize: '0.8rem',
    textAlign: 'center',
    background: 'rgba(239, 68, 68, 0.05)',
    padding: '0.5rem',
    borderRadius: '4px',
  },
  success: {
    color: 'var(--success)',
    fontSize: '0.8rem',
    textAlign: 'center',
    background: 'rgba(16, 185, 129, 0.05)',
    padding: '0.5rem',
    borderRadius: '4px',
  },
  header: {
    padding: '1.25rem',
    borderBottom: '1px solid var(--glass-border)',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  searchBar: {
    width: '280px',
    fontSize: '0.85rem',
    padding: '0.4rem 0.75rem',
  },
  tableWrapper: {
    flex: 1,
    overflowY: 'auto',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    textAlign: 'left',
    fontSize: '0.85rem',
  },
  thRow: {
    borderBottom: '1px solid var(--glass-border)',
    background: 'rgba(0, 0, 0, 0.2)',
  },
  th: {
    padding: '1rem',
    color: 'var(--text-secondary)',
    fontWeight: '600',
  },
  trRow: {
    borderBottom: '1px solid rgba(255, 255, 255, 0.03)',
    transition: 'background 0.2s',
  },
  td: {
    padding: '1rem',
    color: 'var(--text-primary)',
  },
  emptyTd: {
    padding: '3rem',
    textAlign: 'center',
    color: 'var(--text-muted)',
  },
  deleteBtn: {
    padding: '0.3rem 0.5rem',
    fontSize: '0.8rem',
  },
};
