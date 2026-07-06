import React, { useState, useEffect, useRef } from 'react';

export default function Conversations({ token }) {
  const [conversations, setConversations] = useState([]);
  const [selectedConvId, setSelectedConvId] = useState(null);
  const [chatDetail, setChatDetail] = useState(null);
  const [inputText, setInputText] = useState('');
  const [simText, setSimText] = useState('');
  const [simPhone, setSimPhone] = useState('+919900001111');
  const [simName, setSimName] = useState('Sita Reddy');
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const baseUrl = 'http://localhost:8000';

  useEffect(() => {
    fetchConversations();
    const interval = setInterval(fetchConversations, 5000);
    return () => clearInterval(interval);
  }, [statusFilter]);

  useEffect(() => {
    if (selectedConvId) {
      fetchChatDetail(selectedConvId);
      const chatInterval = setInterval(() => fetchChatDetail(selectedConvId), 3000);
      return () => clearInterval(chatInterval);
    }
  }, [selectedConvId]);

  useEffect(() => {
    scrollToBottom();
  }, [chatDetail]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const fetchConversations = async () => {
    try {
      const url = statusFilter 
        ? `${baseUrl}/api/conversations?status_filter=${statusFilter}`
        : `${baseUrl}/api/conversations`;

      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setConversations(data);
      }
    } catch (err) {
      console.error("Error fetching conversations:", err);
    }
  };

  const fetchChatDetail = async (id) => {
    try {
      const res = await fetch(`${baseUrl}/api/conversations/${id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setChatDetail(data);
      }
    } catch (err) {
      console.error("Error fetching chat detail:", err);
    }
  };

  const handleToggleTakeover = async (id, currentStatus) => {
    const nextStatus = currentStatus === 'ai_active' ? 'human_takeover' : 'ai_active';
    try {
      const res = await fetch(`${baseUrl}/api/conversations/${id}/takeover?status_val=${nextStatus}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        fetchConversations();
        fetchChatDetail(id);
      }
    } catch (err) {
      console.error("Error toggling takeover status:", err);
    }
  };

  const handleSendManualMessage = async (e) => {
    e.preventDefault();
    if (!inputText.trim() || !selectedConvId) return;

    try {
      const res = await fetch(`${baseUrl}/api/conversations/${selectedConvId}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ content: inputText })
      });
      if (res.ok) {
        setInputText('');
        fetchChatDetail(selectedConvId);
        fetchConversations();
      }
    } catch (err) {
      console.error("Error sending manual message:", err);
    }
  };

  const handleSendSimulatedMessage = async (e) => {
    e.preventDefault();
    if (!simText.trim()) return;

    setLoading(true);
    try {
      const res = await fetch(`${baseUrl}/api/webhooks/whatsapp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          customer_phone: simPhone,
          message: simText,
          customer_name: simName
        })
      });
      if (res.ok) {
        setSimText('');
        fetchConversations();
        const data = await res.json();
        if (data.conversation_id) {
          setSelectedConvId(data.conversation_id);
          fetchChatDetail(data.conversation_id);
        }
      }
    } catch (err) {
      console.error("Error sending simulated message:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.container}>
      {/* 1. Left Sidebar: Conversation List */}
      <div className="glass-panel" style={styles.inboxSidebar}>
        <div style={styles.sidebarHeader}>
          <h3>Inbox</h3>
          <select 
            className="form-input" 
            style={styles.filterSelect}
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">All Statuses</option>
            <option value="ai_active">AI Active</option>
            <option value="human_takeover">Human Agent</option>
            <option value="resolved">Resolved</option>
          </select>
        </div>

        <div style={styles.listContainer}>
          {conversations.length === 0 ? (
            <p style={styles.emptyText}>No chats active.</p>
          ) : (
            conversations.map((conv) => (
              <div
                key={conv.id}
                onClick={() => setSelectedConvId(conv.id)}
                style={{
                  ...styles.convItem,
                  ...(selectedConvId === conv.id ? styles.convItemActive : {})
                }}
              >
                <div style={styles.convHeader}>
                  <strong style={styles.convName}>{conv.customer_name || conv.customer_phone}</strong>
                  <span className={`badge ${conv.status === 'ai_active' ? 'badge-ai' : 'badge-human'}`}>
                    {conv.status === 'ai_active' ? 'AI' : 'Human'}
                  </span>
                </div>
                <div style={styles.convSubtitle}>{conv.customer_phone}</div>
                {conv.metadata?.budget_limit && (
                  <div style={styles.budgetTag}>Budget Limit: ₹{conv.metadata.budget_limit}</div>
                )}
              </div>
            ))
          )}
        </div>
      </div>

      {/* 2. Middle Panel: Conversation Thread */}
      <div className="glass-panel" style={styles.chatArea}>
        {chatDetail ? (
          <>
            <div style={styles.chatHeader}>
              <div>
                <h2>{chatDetail.customer_name || chatDetail.customer_phone}</h2>
                <small style={{ color: 'var(--text-secondary)' }}>{chatDetail.customer_phone}</small>
              </div>
              <button
                className="btn btn-secondary"
                style={{
                  color: chatDetail.status === 'ai_active' ? 'var(--accent-secondary)' : 'var(--accent-primary)',
                  borderColor: chatDetail.status === 'ai_active' ? 'rgba(0, 240, 255, 0.3)' : 'rgba(255, 51, 102, 0.3)'
                }}
                onClick={() => handleToggleTakeover(chatDetail.id, chatDetail.status)}
              >
                {chatDetail.status === 'ai_active' ? '⚡ AI Responding (Pause)' : '👤 Human Takeover (Resume AI)'}
              </button>
            </div>

            <div style={styles.messagesContainer}>
              {chatDetail.messages && chatDetail.messages.map((msg) => {
                const isCustomer = msg.sender === 'customer';
                const isAI = msg.sender === 'ai';
                return (
                  <div
                    key={msg.id}
                    style={{
                      ...styles.msgRow,
                      justifyContent: isCustomer ? 'flex-start' : 'flex-end'
                    }}
                  >
                    <div
                      style={{
                        ...styles.msgBubble,
                        ...(isCustomer ? styles.customerBubble : isAI ? styles.aiBubble : styles.humanBubble)
                      }}
                    >
                      <div style={styles.msgSenderBadge}>
                        {msg.sender.toUpperCase()}
                      </div>
                      <p style={styles.msgContent}>{msg.content}</p>
                      <span style={styles.msgTime}>
                        {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                  </div>
                );
              })}
              <div ref={messagesEndRef} />
            </div>

            <form onSubmit={handleSendManualMessage} style={styles.chatInputForm}>
              <input
                type="text"
                className="form-input"
                placeholder="Type a message as a Human Agent (This immediately silences AI)..."
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
              />
              <button type="submit" className="btn btn-primary">Send</button>
            </form>
          </>
        ) : (
          <div style={styles.selectPrompt}>
            <h3>Please select a conversation from the left to manage it.</h3>
          </div>
        )}
      </div>

      {/* 3. Right Sidebar: Customer WhatsApp Simulator Sandbox Console */}
      <div className="glass-panel" style={styles.simulatorPanel}>
        <div style={styles.simHeader}>
          <h3>WhatsApp Sandbox</h3>
          <p>Simulate customer requests to test AI classification & semantic searches.</p>
        </div>

        <form onSubmit={handleSendSimulatedMessage} style={styles.simForm}>
          <div style={styles.inputGroup}>
            <label style={styles.label}>Simulated Phone</label>
            <input
              type="text"
              className="form-input"
              value={simPhone}
              onChange={(e) => setSimPhone(e.target.value)}
            />
          </div>
          <div style={styles.inputGroup}>
            <label style={styles.label}>Simulated Name</label>
            <input
              type="text"
              className="form-input"
              value={simName}
              onChange={(e) => setSimName(e.target.value)}
            />
          </div>
          <div style={styles.inputGroup}>
            <label style={styles.label}>Inbound Message</label>
            <textarea
              className="form-input"
              style={styles.simTextarea}
              placeholder="e.g. show me black sarees under 5000"
              value={simText}
              onChange={(e) => setSimText(e.target.value)}
              required
            />
          </div>
          <button type="submit" className="btn btn-primary" style={{ width: '100%' }} disabled={loading}>
            {loading ? 'AI thinking...' : '🚀 Send Inbound Webhook'}
          </button>
        </form>

        <div style={styles.simInfoCard}>
          <h4>Recommended Sandbox Queries:</h4>
          <ul>
            <li>"Show me black sarees under 5000" (Check semantic catalog retrieval)</li>
            <li>"Is COD available?" (Check logistics policy RAG)</li>
            <li>"Can I talk to a human?" (Check instant takeover escalation)</li>
          </ul>
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
  inboxSidebar: {
    width: '280px',
    borderRadius: 'var(--border-radius-md)',
    display: 'flex',
    flexDirection: 'column',
  },
  sidebarHeader: {
    padding: '1.25rem',
    borderBottom: '1px solid var(--glass-border)',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.75rem',
  },
  filterSelect: {
    fontSize: '0.85rem',
    padding: '0.4rem 0.75rem',
  },
  listContainer: {
    flex: 1,
    overflowY: 'auto',
    padding: '0.5rem',
  },
  emptyText: {
    textAlign: 'center',
    color: 'var(--text-muted)',
    fontSize: '0.9rem',
    padding: '2rem 0',
  },
  convItem: {
    padding: '0.9rem',
    borderRadius: 'var(--border-radius-sm)',
    cursor: 'pointer',
    marginBottom: '0.4rem',
    transition: 'all 0.2s ease',
    border: '1px solid transparent',
  },
  convItemActive: {
    background: 'rgba(255, 255, 255, 0.05)',
    borderColor: 'var(--glass-border)',
  },
  convHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '0.2rem',
  },
  convName: {
    fontSize: '0.9rem',
    color: 'var(--text-primary)',
  },
  convSubtitle: {
    fontSize: '0.75rem',
    color: 'var(--text-secondary)',
  },
  budgetTag: {
    display: 'inline-block',
    marginTop: '0.4rem',
    fontSize: '0.7rem',
    color: 'var(--accent-secondary)',
    background: 'rgba(0, 240, 255, 0.05)',
    padding: '0.1rem 0.4rem',
    borderRadius: '4px',
  },
  chatArea: {
    flex: 1,
    borderRadius: 'var(--border-radius-md)',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  },
  chatHeader: {
    padding: '1.25rem',
    borderBottom: '1px solid var(--glass-border)',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  selectPrompt: {
    flex: 1,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: 'var(--text-muted)',
  },
  messagesContainer: {
    flex: 1,
    padding: '1.5rem',
    overflowY: 'auto',
    display: 'flex',
    flexDirection: 'column',
    gap: '1rem',
    background: 'rgba(0, 0, 0, 0.15)',
  },
  msgRow: {
    display: 'flex',
    width: '100%',
  },
  msgBubble: {
    maxWidth: '70%',
    padding: '0.8rem 1rem',
    borderRadius: '16px',
    position: 'relative',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.3rem',
    boxShadow: '0 4px 10px rgba(0, 0, 0, 0.2)',
  },
  msgSenderBadge: {
    fontSize: '0.6rem',
    fontWeight: '800',
    letterSpacing: '0.05em',
    opacity: 0.7,
  },
  msgContent: {
    fontSize: '0.9rem',
    lineHeight: '1.4',
    wordBreak: 'break-word',
    whiteSpace: 'pre-wrap',
  },
  msgTime: {
    fontSize: '0.65rem',
    alignSelf: 'flex-end',
    opacity: 0.5,
  },
  customerBubble: {
    background: 'rgba(255, 255, 255, 0.05)',
    color: 'var(--text-primary)',
    border: '1px solid var(--glass-border)',
    borderTopLeftRadius: '2px',
  },
  aiBubble: {
    background: 'rgba(0, 240, 255, 0.1)',
    color: 'var(--text-primary)',
    border: '1px solid rgba(0, 240, 255, 0.2)',
    borderTopRightRadius: '2px',
  },
  humanBubble: {
    background: 'rgba(255, 51, 102, 0.1)',
    color: 'var(--text-primary)',
    border: '1px solid rgba(255, 51, 102, 0.2)',
    borderTopRightRadius: '2px',
  },
  chatInputForm: {
    padding: '1.25rem',
    borderTop: '1px solid var(--glass-border)',
    display: 'flex',
    gap: '0.75rem',
  },
  simulatorPanel: {
    width: '320px',
    borderRadius: 'var(--border-radius-md)',
    padding: '1.25rem',
    display: 'flex',
    flexDirection: 'column',
    gap: '1.25rem',
  },
  simHeader: {
    borderBottom: '1px solid var(--glass-border)',
    paddingBottom: '0.75rem',
  },
  simForm: {
    display: 'flex',
    flexDirection: 'column',
    gap: '1rem',
  },
  inputGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.4rem',
  },
  label: {
    fontSize: '0.75rem',
    fontWeight: '700',
    color: 'var(--text-secondary)',
    textTransform: 'uppercase',
  },
  simTextarea: {
    height: '80px',
    resize: 'none',
  },
  simInfoCard: {
    background: 'rgba(255, 255, 255, 0.02)',
    border: '1px solid var(--glass-border)',
    borderRadius: 'var(--border-radius-sm)',
    padding: '0.9rem',
    fontSize: '0.8rem',
  },
};
