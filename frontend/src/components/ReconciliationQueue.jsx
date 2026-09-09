import React, { useState, useEffect } from 'react';
import { apiFetch } from '../api';

export default function ReconciliationQueue({ token }) {
  const [messages, setMessages] = useState([]);
  const [statusFilter, setStatusFilter] = useState('UNKNOWN_PROVIDER_OUTCOME');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [actionSuccess, setActionSuccess] = useState('');
  const [reconcilingId, setReconcilingId] = useState(null);
  const [reconcileNotes, setReconcileNotes] = useState({});

  useEffect(() => {
    fetchOutboxMessages();
  }, [statusFilter]);

  const fetchOutboxMessages = async () => {
    setLoading(true);
    setError('');
    try {
      const queryParam = statusFilter && statusFilter !== 'ALL' ? `?status=${statusFilter}` : '';
      const res = await apiFetch(`/api/outbox${queryParam}`);
      if (!res.ok) {
        throw new Error(`Failed to load outbox queue: ${res.statusText}`);
      }
      const data = await res.json();
      setMessages(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleReconcile = async (outboxId, action) => {
    setReconcilingId(outboxId);
    setActionSuccess('');
    setError('');
    try {
      const notes = reconcileNotes[outboxId] || `Merchant manual action: ${action}`;
      const res = await apiFetch(`/api/outbox/${outboxId}/reconcile`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          action: action,
          notes: notes
        })
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Reconciliation failed');
      }

      const data = await res.json();
      setActionSuccess(`Message ${outboxId.slice(0, 8)}... successfully reconciled to ${data.new_status}!`);
      
      // Clean up notes for this item
      setReconcileNotes(prev => {
        const next = { ...prev };
        delete next[outboxId];
        return next;
      });

      // Refresh list
      fetchOutboxMessages();
    } catch (err) {
      setError(err.message);
    } finally {
      setReconcilingId(null);
    }
  };

  const getStatusBadgeClass = (status) => {
    switch (status) {
      case 'UNKNOWN_PROVIDER_OUTCOME':
        return 'badge-warning';
      case 'FAILED':
        return 'badge-human';
      case 'DELIVERED':
      case 'SENT':
        return 'badge-success';
      case 'PENDING':
        return 'badge-ai';
      default:
        return 'badge-ai';
    }
  };

  return (
    <div style={styles.container}>
      {/* Header & Controls */}
      <div className="glass-panel" style={styles.headerCard}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <h2 style={{ margin: 0, fontSize: '1.25rem' }}>⚖️ Outbox Reconciliation Queue</h2>
              <span className="badge badge-warning" style={{ fontSize: '0.7rem' }}>Resilience Layer</span>
            </div>
            <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              Inspect and resolve outbound WhatsApp messages stuck in uncertain provider states or delivery timeouts.
            </p>
          </div>

          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <button 
              className="btn btn-secondary" 
              onClick={fetchOutboxMessages} 
              disabled={loading}
              style={{ fontSize: '0.8rem', padding: '0.4rem 0.8rem' }}
            >
              🔄 Refresh Queue
            </button>
          </div>
        </div>

        {/* Filter Pills */}
        <div style={styles.filterRow}>
          <button
            className={`btn ${statusFilter === 'UNKNOWN_PROVIDER_OUTCOME' ? 'btn-primary' : 'btn-secondary'}`}
            style={styles.filterBtn}
            onClick={() => setStatusFilter('UNKNOWN_PROVIDER_OUTCOME')}
          >
            ⚠️ Unknown Outcome
          </button>
          <button
            className={`btn ${statusFilter === 'FAILED' ? 'btn-primary' : 'btn-secondary'}`}
            style={styles.filterBtn}
            onClick={() => setStatusFilter('FAILED')}
          >
            ❌ Failed Dispatches
          </button>
          <button
            className={`btn ${statusFilter === 'PENDING' ? 'btn-primary' : 'btn-secondary'}`}
            style={styles.filterBtn}
            onClick={() => setStatusFilter('PENDING')}
          >
            ⏳ Pending Dispatch
          </button>
          <button
            className={`btn ${statusFilter === 'ALL' ? 'btn-primary' : 'btn-secondary'}`}
            style={styles.filterBtn}
            onClick={() => setStatusFilter('ALL')}
          >
            📋 All Messages
          </button>
        </div>
      </div>

      {error && <div style={styles.errorBanner}>⚠️ {error}</div>}
      {actionSuccess && <div style={styles.successBanner}>✓ {actionSuccess}</div>}

      {/* Main Message List */}
      <div style={styles.listContainer}>
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem' }}>
            <div className="spinner"></div>
          </div>
        ) : messages.length === 0 ? (
          <div className="glass-panel" style={styles.emptyState}>
            <span style={{ fontSize: '2.5rem' }}>🎉</span>
            <h3 style={{ margin: '0.5rem 0' }}>Queue is Clear!</h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
              No messages currently match status: <strong>{statusFilter}</strong>. All outbox dispatches are reconciled.
            </p>
          </div>
        ) : (
          messages.map((msg) => (
            <div key={msg.id} className="glass-panel" style={styles.messageCard}>
              <div style={styles.cardHeader}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <span className={`badge ${getStatusBadgeClass(msg.status)}`}>
                    {msg.status}
                  </span>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                    ID: <code>{msg.id}</code>
                  </span>
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                  {msg.created_at ? new Date(msg.created_at).toLocaleString() : 'N/A'}
                </div>
              </div>

              <div style={styles.cardBody}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem', marginBottom: '0.75rem' }}>
                  <div>
                    <span style={styles.fieldLabel}>Recipient:</span>
                    <strong style={{ color: 'var(--accent-secondary)' }}>{msg.recipient_phone}</strong>
                  </div>
                  <div>
                    <span style={styles.fieldLabel}>Attempts:</span>
                    <strong>{msg.attempt_count}</strong>
                  </div>
                  <div>
                    <span style={styles.fieldLabel}>Conversation ID:</span>
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{msg.conversation_id}</span>
                  </div>
                </div>

                <div style={styles.contentBox}>
                  <div style={styles.fieldLabel}>Dispatched Payload:</div>
                  <div style={{ fontSize: '0.9rem', color: 'var(--text-primary)', whiteSpace: 'pre-wrap' }}>
                    {msg.content}
                  </div>
                </div>

                {msg.last_error && (
                  <div style={styles.errorBox}>
                    <span style={{ fontWeight: 'bold', color: '#f87171' }}>Last Provider Error / Timeout:</span>
                    <div style={{ fontSize: '0.8rem', color: '#fca5a5', marginTop: '0.2rem' }}>
                      {msg.last_error}
                    </div>
                  </div>
                )}

                {/* Reconcile Action Bar */}
                <div style={styles.reconcileActionArea}>
                  <div style={{ flex: 1 }}>
                    <input
                      type="text"
                      className="form-input"
                      style={{ fontSize: '0.8rem', padding: '0.35rem 0.6rem', width: '100%' }}
                      placeholder="Optional audit notes (e.g. 'Customer confirmed order on call')..."
                      value={reconcileNotes[msg.id] || ''}
                      onChange={(e) => setReconcileNotes({ ...reconcileNotes, [msg.id]: e.target.value })}
                      disabled={reconcilingId === msg.id}
                    />
                  </div>

                  <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      style={{ borderColor: 'var(--accent-secondary)', color: 'var(--accent-secondary)', fontSize: '0.8rem' }}
                      disabled={reconcilingId === msg.id}
                      onClick={() => handleReconcile(msg.id, 'allow_resend')}
                      title="Reset outbox status to PENDING for automatic retry"
                    >
                      🔁 Allow Resend
                    </button>

                    <button
                      type="button"
                      className="btn btn-primary"
                      style={{ fontSize: '0.8rem' }}
                      disabled={reconcilingId === msg.id}
                      onClick={() => handleReconcile(msg.id, 'close_loop')}
                      title="Mark as DELIVERED to resolve stuck state"
                    >
                      ✓ Close Loop (Mark Delivered)
                    </button>

                    <button
                      type="button"
                      className="btn btn-secondary"
                      style={{ borderColor: 'var(--accent-primary)', color: 'var(--accent-primary)', fontSize: '0.8rem' }}
                      disabled={reconcilingId === msg.id}
                      onClick={() => handleReconcile(msg.id, 'mark_failed')}
                      title="Acknowledge delivery failure permanently"
                    >
                      ✖ Mark Failed
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    gap: '1rem',
    maxWidth: '1200px',
    margin: '0 auto',
    width: '100%',
  },
  headerCard: {
    padding: '1.25rem',
    borderRadius: 'var(--border-radius-md)',
    display: 'flex',
    flexDirection: 'column',
    gap: '1rem',
  },
  filterRow: {
    display: 'flex',
    gap: '0.5rem',
    flexWrap: 'wrap',
    borderTop: '1px solid var(--glass-border)',
    paddingTop: '0.75rem',
  },
  filterBtn: {
    fontSize: '0.8rem',
    padding: '0.35rem 0.75rem',
    borderRadius: 'var(--border-radius-sm)',
  },
  listContainer: {
    display: 'flex',
    flexDirection: 'column',
    gap: '1rem',
  },
  emptyState: {
    padding: '4rem 2rem',
    textAlign: 'center',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 'var(--border-radius-md)',
  },
  messageCard: {
    padding: '1.25rem',
    borderRadius: 'var(--border-radius-md)',
    border: '1px solid var(--glass-border)',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.75rem',
  },
  cardHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottom: '1px solid var(--glass-border)',
    paddingBottom: '0.5rem',
  },
  cardBody: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.75rem',
  },
  fieldLabel: {
    display: 'block',
    fontSize: '0.7rem',
    color: 'var(--text-secondary)',
    fontWeight: 'bold',
    textTransform: 'uppercase',
    marginBottom: '0.15rem',
  },
  contentBox: {
    background: 'rgba(0, 0, 0, 0.25)',
    padding: '0.75rem',
    borderRadius: '4px',
    borderLeft: '3px solid var(--accent-primary)',
  },
  errorBox: {
    background: 'rgba(239, 68, 68, 0.1)',
    border: '1px solid rgba(239, 68, 68, 0.3)',
    padding: '0.6rem 0.75rem',
    borderRadius: '4px',
  },
  reconcileActionArea: {
    display: 'flex',
    gap: '0.75rem',
    alignItems: 'center',
    flexWrap: 'wrap',
    marginTop: '0.5rem',
    paddingTop: '0.75rem',
    borderTop: '1px solid var(--glass-border)',
  },
  errorBanner: {
    background: 'rgba(239, 68, 68, 0.15)',
    border: '1px solid rgba(239, 68, 68, 0.35)',
    color: '#fca5a5',
    padding: '0.75rem',
    borderRadius: '6px',
    fontSize: '0.85rem',
  },
  successBanner: {
    background: 'rgba(16, 185, 129, 0.15)',
    border: '1px solid rgba(16, 185, 129, 0.35)',
    color: '#6ee7b7',
    padding: '0.75rem',
    borderRadius: '6px',
    fontSize: '0.85rem',
  },
};
