import React, { useState, useEffect } from 'react';
import { apiFetch } from '../api';

export default function Catalog({ token }) {
  const [products, setProducts] = useState([]);
  const [allProducts, setAllProducts] = useState([]);
  const [noResultsFound, setNoResultsFound] = useState(false);
  const [editingProductId, setEditingProductId] = useState(null);
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
  const [imageUrl, setImageUrl] = useState('');
  const [uploadingImage, setUploadingImage] = useState(false);
  const [file, setFile] = useState(null);
  const [importMode, setImportMode] = useState('atomic');
  const [importErrors, setImportErrors] = useState([]);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchProducts();
  }, [searchQuery]);

  const fetchProducts = async () => {
    try {
      if (!searchQuery.trim()) {
        const res = await apiFetch('/api/catalog/products');
        if (res.ok) {
          const data = await res.json();
          setProducts(data);
          setAllProducts(data);
          setNoResultsFound(false);
        }
      } else {
        const res = await apiFetch(`/api/catalog/products?q=${encodeURIComponent(searchQuery.trim())}`);
        if (res.ok) {
          const data = await res.json();
          if (data && data.length > 0) {
            setProducts(data);
            setNoResultsFound(false);
          } else {
            // No matching results found -> fallback to showing all products + notification
            setProducts(allProducts);
            setNoResultsFound(true);
          }
        }
      }
    } catch (err) {
      console.error("Error fetching products:", err);
    }
  };

  const resetForm = () => {
    setEditingProductId(null);
    setSku('');
    setName('');
    setPrice('');
    setColor('');
    setFabric('');
    setCategoryName('');
    setGender('Women');
    setSizes('Free Size');
    setStockCount('10');
    setDescription('');
    setImageUrl('');
  };

  const handleEditClick = (product) => {
    setEditingProductId(product.id);
    setSku(product.sku || '');
    setName(product.name || '');
    setPrice(product.price || '');
    setColor(product.color || '');
    setFabric(product.fabric || '');
    setCategoryName(product.category_name || '');
    setGender(product.gender || 'Women');
    setSizes(Array.isArray(product.sizes) ? product.sizes.join(', ') : 'Free Size');
    setStockCount(product.stock_count !== undefined ? String(product.stock_count) : '10');
    setDescription(product.description || '');
    setImageUrl(Array.isArray(product.image_urls) ? product.image_urls.join(', ') : '');
    setError('');
    setSuccess('');
  };

  const handleManualSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    const sizeArray = sizes.split(',').map(s => s.trim()).filter(Boolean);
    const imageUrlArray = imageUrl.split(',').map(s => s.trim()).filter(Boolean);

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
      image_urls: imageUrlArray,
      video_urls: []
    };

    try {
      const url = editingProductId ? `/api/catalog/products/${editingProductId}` : '/api/catalog/products';
      const method = editingProductId ? 'PUT' : 'POST';

      const res = await apiFetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || `Failed to ${editingProductId ? 'update' : 'create'} product.`);
      }

      setSuccess(`Product ${editingProductId ? 'updated' : 'created'} successfully!`);
      resetForm();
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
    setImportErrors([]);
    setLoading(true);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await apiFetch(`/api/catalog/upload?mode=${importMode}`, {
        method: 'POST',
        body: formData
      });

      if (!res.ok) {
        let errorMsg = 'Bulk upload failed.';
        try {
          const data = await res.json();
          errorMsg = data.detail || errorMsg;
        } catch (parseErr) {
          errorMsg = `Server error: ${res.status} ${res.statusText}`;
        }
        throw new Error(errorMsg);
      }

      const data = await res.json();
      setSuccess(`Upload ${data.status}! Created ${data.created} and updated ${data.updated} items.`);
      if (data.errors && data.errors.length > 0) {
        setImportErrors(data.errors);
      }
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
      const res = await apiFetch(`/api/catalog/products/${id}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        if (editingProductId === id) resetForm();
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
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '0.5rem' }}>
              <label style={{ fontSize: '0.8rem', opacity: 0.8 }}>Mode:</label>
              <select 
                value={importMode} 
                onChange={(e) => setImportMode(e.target.value)}
                style={{ padding: '0.2rem 0.4rem', fontSize: '0.75rem', borderRadius: '4px', background: 'rgba(255,255,255,0.05)', color: '#fff', border: '1px solid rgba(255,255,255,0.1)' }}
              >
                <option value="atomic">Atomic (All or Nothing)</option>
                <option value="partial">Partial (Import valid rows, report errors)</option>
              </select>
            </div>
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
          {error && <div style={styles.error}>{error}</div>}
          {success && <div style={styles.success}>{success}</div>}
          {importErrors.length > 0 && (
            <div style={{ marginTop: '0.5rem', maxHeight: '120px', overflowY: 'auto', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', padding: '0.5rem', borderRadius: '4px', fontSize: '0.75rem' }}>
              <strong>Row Errors ({importErrors.length}):</strong>
              <ul style={{ margin: '0.25rem 0 0 1rem', padding: 0 }}>
                {importErrors.map((err, i) => (
                  <li key={i} style={{ color: '#fca5a5' }}>{err}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* 2. Compact Manual Add / Edit Product Form (Always Visible) */}
        <div className="glass-panel" style={{ ...styles.card, padding: '0.85rem 1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.2rem' }}>
            <h3 style={{ fontSize: '0.9rem', margin: 0 }}>
              {editingProductId ? '✏️ Edit Product' : 'Add Product Manually'}
            </h3>
            {editingProductId && (
              <button 
                type="button" 
                className="btn btn-secondary" 
                style={{ padding: '0.15rem 0.5rem', fontSize: '0.7rem' }}
                onClick={resetForm}
              >
                ✖ Cancel
              </button>
            )}
          </div>

          <form onSubmit={handleManualSubmit} style={styles.manualForm}>
            <div style={styles.formRow}>
              <div style={styles.inputGroup}>
                <label style={styles.label}>SKU *</label>
                <input type="text" className="form-input" style={styles.compactInput} value={sku} onChange={e => setSku(e.target.value)} required />
              </div>
              <div style={styles.inputGroup}>
                <label style={styles.label}>Name *</label>
                <input type="text" className="form-input" style={styles.compactInput} value={name} onChange={e => setName(e.target.value)} required />
              </div>
            </div>

            <div style={styles.formRow}>
              <div style={styles.inputGroup}>
                <label style={styles.label}>Price (INR) *</label>
                <input type="number" className="form-input" style={styles.compactInput} value={price} onChange={e => setPrice(e.target.value)} required />
              </div>
              <div style={styles.inputGroup}>
                <label style={styles.label}>Color *</label>
                <input type="text" className="form-input" style={styles.compactInput} placeholder="Black" value={color} onChange={e => setColor(e.target.value)} required />
              </div>
            </div>

            <div style={styles.formRow}>
              <div style={styles.inputGroup}>
                <label style={styles.label}>Fabric</label>
                <input type="text" className="form-input" style={styles.compactInput} placeholder="Silk" value={fabric} onChange={e => setFabric(e.target.value)} />
              </div>
              <div style={styles.inputGroup}>
                <label style={styles.label}>Category</label>
                <input type="text" className="form-input" style={styles.compactInput} placeholder="Sarees" value={categoryName} onChange={e => setCategoryName(e.target.value)} />
              </div>
            </div>

            <div style={styles.formRow}>
              <div style={styles.inputGroup}>
                <label style={styles.label}>Gender</label>
                <select className="form-input" style={styles.compactInput} value={gender} onChange={e => setGender(e.target.value)}>
                  <option value="Women">Women</option>
                  <option value="Men">Men</option>
                  <option value="Unisex">Unisex</option>
                </select>
              </div>
              <div style={styles.inputGroup}>
                <label style={styles.label}>Sizes</label>
                <input type="text" className="form-input" style={styles.compactInput} value={sizes} onChange={e => setSizes(e.target.value)} />
              </div>
              <div style={styles.inputGroup}>
                <label style={styles.label}>Stock</label>
                <input type="number" className="form-input" style={styles.compactInput} value={stockCount} onChange={e => setStockCount(e.target.value)} />
              </div>
            </div>

            <div style={styles.inputGroup}>
              <label style={styles.label}>Image File / URL</label>
              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                <input 
                  type="text" 
                  className="form-input" 
                  style={{ ...styles.compactInput, flex: 1 }} 
                  placeholder="Paste URL or upload file..." 
                  value={imageUrl} 
                  onChange={e => setImageUrl(e.target.value)} 
                />
                <label className="btn btn-secondary" style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem', cursor: 'pointer', whiteSpace: 'nowrap', margin: 0 }}>
                  {uploadingImage ? '⏳' : '📷 Upload'}
                  <input 
                    type="file" 
                    accept="image/*" 
                    style={{ display: 'none' }} 
                    onChange={async (e) => {
                      const imgFile = e.target.files[0];
                      if (!imgFile) return;
                      try {
                        setUploadingImage(true);
                        const formData = new FormData();
                        formData.append('file', imgFile);
                        const res = await apiFetch('/api/catalog/upload-image', {
                          method: 'POST',
                          body: formData
                        });
                        if (!res.ok) throw new Error('Image upload failed');
                        const data = await res.json();
                        setImageUrl(prev => prev ? `${prev}, ${data.url}` : data.url);
                      } catch (err) {
                        setError(err.message);
                      } finally {
                        setUploadingImage(false);
                      }
                    }} 
                  />
                </label>
              </div>
              {imageUrl && (
                <div style={{ marginTop: '0.5rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                  {imageUrl.split(',').map((url, idx) => {
                    const trimmed = url.trim();
                    if (!trimmed) return null;
                    return (
                      <a key={idx} href={trimmed} target="_blank" rel="noopener noreferrer" title="Click to view full image">
                        <img 
                          src={trimmed} 
                          alt="Preview" 
                          style={{ width: '50px', height: '50px', objectFit: 'cover', borderRadius: '4px', border: '1px solid rgba(255,255,255,0.2)', cursor: 'pointer' }} 
                        />
                      </a>
                    );
                  })}
                </div>
              )}
            </div>

            <div style={styles.inputGroup}>
              <label style={styles.label}>Description</label>
              <textarea className="form-input" style={styles.compactTextarea} value={description} onChange={e => setDescription(e.target.value)} />
            </div>

            {error && <div style={styles.error}>{error}</div>}
            {success && <div style={styles.success}>{success}</div>}

            <button type="submit" className="btn btn-primary" style={{ width: '100%', padding: '0.35rem 0.5rem', fontSize: '0.8rem' }}>
              {editingProductId ? 'Update Product' : 'Create Product'}
            </button>
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
            placeholder="🔍 Search SKU, name, color, fabric..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        {noResultsFound && (
          <div style={styles.noResultNotice}>
            ⚠️ No products found matching "<strong>{searchQuery}</strong>". Displaying all available inventory ({allProducts.length} items) below:
          </div>
        )}

        <div style={styles.tableWrapper}>
          <table style={styles.table}>
            <thead>
              <tr style={styles.thRow}>
                <th style={{ ...styles.th, whiteSpace: 'nowrap' }}>Image</th>
                <th style={{ ...styles.th, whiteSpace: 'nowrap' }}>SKU</th>
                <th style={styles.th}>Name</th>
                <th style={{ ...styles.th, whiteSpace: 'nowrap' }}>Price</th>
                <th style={styles.th}>Color</th>
                <th style={styles.th}>Fabric</th>
                <th style={{ ...styles.th, whiteSpace: 'nowrap' }}>Sizes</th>
                <th style={{ ...styles.th, whiteSpace: 'nowrap' }}>Stock</th>
                <th style={{ ...styles.th, whiteSpace: 'nowrap', textAlign: 'center' }}>Actions</th>
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
                    <td style={{ ...styles.td, textAlign: 'center' }}>
                      {Array.isArray(prod.image_urls) && prod.image_urls.length > 0 ? (
                        <a href={prod.image_urls[0]} target="_blank" rel="noopener noreferrer" title="Click to view full image">
                          <img 
                            src={prod.image_urls[0]} 
                            alt={prod.name} 
                            style={{ width: '36px', height: '36px', objectFit: 'cover', borderRadius: '4px', border: '1px solid rgba(255,255,255,0.2)', cursor: 'pointer' }} 
                          />
                        </a>
                      ) : (
                        <span style={{ fontSize: '0.7rem', opacity: 0.5 }}>No Image</span>
                      )}
                    </td>
                    <td style={{ ...styles.td, whiteSpace: 'nowrap', fontSize: '0.8rem' }}>{prod.sku}</td>
                    <td style={styles.td}><strong>{prod.name}</strong></td>
                    <td style={{ ...styles.td, whiteSpace: 'nowrap' }}>₹{prod.price}</td>
                    <td style={styles.td}>{prod.color}</td>
                    <td style={styles.td}>{prod.fabric || 'N/A'}</td>
                    <td style={{ ...styles.td, whiteSpace: 'nowrap' }}>{Array.isArray(prod.sizes) ? prod.sizes.join(', ') : prod.sizes}</td>
                    <td style={{ ...styles.td, whiteSpace: 'nowrap' }}>
                      <span className={`badge ${prod.stock_count > 0 ? 'badge-success' : 'badge-human'}`} style={{ textTransform: 'none', padding: '0.2rem 0.4rem', fontSize: '0.75rem' }}>
                        {prod.stock_count} left
                      </span>
                    </td>
                    <td style={{ ...styles.td, whiteSpace: 'nowrap', textAlign: 'center' }}>
                      <div style={{ display: 'inline-flex', gap: '0.3rem' }}>
                        <button 
                          className="btn btn-secondary" 
                          style={styles.actionBtn}
                          title="Edit product"
                          onClick={() => handleEditClick(prod)}
                        >
                          ✏️
                        </button>
                        <button 
                          className="btn btn-secondary" 
                          style={styles.actionBtn}
                          title="Delete product"
                          onClick={() => handleDeleteProduct(prod.id)}
                        >
                          🗑️
                        </button>
                      </div>
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
    gap: '0.4rem',
  },
  formRow: {
    display: 'flex',
    gap: '0.4rem',
  },
  inputGroup: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    gap: '0.15rem',
  },
  label: {
    fontSize: '0.7rem',
    fontWeight: '600',
    color: 'var(--text-secondary)',
  },
  compactInput: {
    padding: '0.25rem 0.5rem',
    fontSize: '0.8rem',
    height: '28px',
  },
  compactTextarea: {
    padding: '0.25rem 0.5rem',
    fontSize: '0.8rem',
    height: '38px',
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
  noResultNotice: {
    padding: '0.75rem 1.25rem',
    background: 'rgba(234, 179, 8, 0.1)',
    color: '#eab308',
    borderBottom: '1px solid rgba(234, 179, 8, 0.2)',
    fontSize: '0.85rem',
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
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
  actionBtn: {
    padding: '0.3rem 0.5rem',
    fontSize: '0.8rem',
  },
};
