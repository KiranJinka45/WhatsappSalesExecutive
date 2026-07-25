import React, { useState, useEffect, useRef } from 'react';
import { apiFetch, API_BASE_URL } from '../api';

export default function Conversations({ token, brandPhone }) {
  const [conversations, setConversations] = useState([]);
  const [selectedConvId, setSelectedConvId] = useState(null);
  const [chatDetail, setChatDetail] = useState(null);
  const [inputText, setInputText] = useState('');
  const [simText, setSimText] = useState('');
  const [simPhone, setSimPhone] = useState('+919900001111');
  const [simName, setSimName] = useState('Sita Reddy');
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(false);
  const [inspectedMessage, setInspectedMessage] = useState(null);
  const [replayStepIndex, setReplayStepIndex] = useState(-1);
  const [pendingApprovals, setPendingApprovals] = useState([]);
  const [editApprovalText, setEditApprovalText] = useState('');
  const messagesEndRef = useRef(null);

  const selectedConvIdRef = useRef(selectedConvId);
  const statusFilterRef = useRef(statusFilter);

  useEffect(() => {
    selectedConvIdRef.current = selectedConvId;
  }, [selectedConvId]);

  useEffect(() => {
    statusFilterRef.current = statusFilter;
  }, [statusFilter]);

  useEffect(() => {
    fetchConversations();
  }, [statusFilter]);

  useEffect(() => {
    if (selectedConvId) {
      fetchChatDetail(selectedConvId);
      setReplayStepIndex(-1);
    }
  }, [selectedConvId]);

  useEffect(() => {
    fetchPendingApprovals();

    const url = `${API_BASE_URL || ''}/api/conversations/stream`;
    const eventSource = new EventSource(url, { withCredentials: true });

    eventSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        const { event: eventType, data } = payload;
        console.log("SSE Event Received:", eventType, data);

        fetchConversations();

        if (eventType === 'new_approval' || eventType === 'status_change') {
          fetchPendingApprovals();
        }

        const currentSelectedId = selectedConvIdRef.current;
        if (data && data.conversation_id && currentSelectedId === data.conversation_id) {
          fetchChatDetail(currentSelectedId);
        }
      } catch (err) {
        console.error("Error parsing SSE event data:", err);
      }
    };

    eventSource.onerror = (err) => {
      console.error("SSE Connection error:", err);
    };

    return () => {
      eventSource.close();
    };
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [chatDetail]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const fetchConversations = async () => {
    try {
      const currentFilter = statusFilterRef.current;
      const path = currentFilter 
        ? `/api/conversations?status_filter=${currentFilter}`
        : '/api/conversations';

      const res = await apiFetch(path);
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
      const res = await apiFetch(`/api/conversations/${id}`);
      if (res.ok) {
        const data = await res.json();
        setChatDetail(data);
      }
    } catch (err) {
      console.error("Error fetching chat detail:", err);
    }
  };

  const fetchPendingApprovals = async () => {
    try {
      const res = await apiFetch('/api/conversations/approvals/pending');
      if (res.ok) {
        const data = await res.json();
        setPendingApprovals(data);
      }
    } catch (err) {
      console.error("Error fetching pending approvals:", err);
    }
  };

  const handleToggleTakeover = async (id, currentStatus) => {
    // Toggle between AI_ACTIVE/WAITING_APPROVAL and OWNER_ACTIVE
    const nextStatus = (currentStatus === 'AI_ACTIVE' || currentStatus === 'WAITING_APPROVAL') ? 'OWNER_ACTIVE' : 'AI_ACTIVE';
    try {
      const res = await apiFetch(`/api/conversations/${id}/takeover?status_val=${nextStatus}`, {
        method: 'POST'
      });
      if (res.ok) {
        fetchConversations();
        fetchPendingApprovals();
        fetchChatDetail(id);
      }
    } catch (err) {
      console.error("Error toggling takeover status:", err);
    }
  };

  const handleRespondToApproval = async (approvalId, action, text = '') => {
    try {
      const res = await apiFetch(`/api/conversations/approvals/${approvalId}/respond`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ action: action, edited_response: text })
      });
      if (res.ok) {
        setEditApprovalText('');
        fetchPendingApprovals();
        fetchConversations();
        if (selectedConvId) fetchChatDetail(selectedConvId);
      }
    } catch (err) {
      console.error("Error responding to approval:", err);
    }
  };

  const handleSendManualMessage = async (e) => {
    e.preventDefault();
    if (!inputText.trim() || !selectedConvId) return;

    try {
      const res = await apiFetch(`/api/conversations/${selectedConvId}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
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
      const res = await apiFetch('/api/webhooks/whatsapp/simulated', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          customer_phone: simPhone,
          message: simText,
          customer_name: simName,
          brand_phone: brandPhone
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

  const submitFeedback = async (messageId, sku, rating, reason = null) => {
    try {
      const res = await apiFetch('/api/conversations/feedback', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          message_id: messageId,
          product_sku: sku,
          rating: rating,
          reason: reason
        })
      });
      if (res.ok) {
        alert("Feedback submitted successfully!");
      }
    } catch (err) {
      console.error("Error submitting recommendation feedback:", err);
    }
  };

  const exportDebugLog = (chat, msg) => {
    const diagnosticPayload = {
      timestamp: new Date().toISOString(),
      conversation_id: chat.id,
      customer_phone: chat.customer_phone,
      inspected_message: {
        id: msg.id,
        content: msg.content,
        created_at: msg.created_at,
        metadata: msg.metadata
      },
      full_thread: chat.messages.map(m => ({
        sender: m.sender,
        content: m.content,
        created_at: m.created_at,
        metadata: m.metadata
      }))
    };
    
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(jsonStringifySafe(diagnosticPayload));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `closely_diagnostic_${chat.id}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const jsonStringifySafe = (obj) => {
    return JSON.stringify(obj, null, 2);
  };

  return (
    <div style={styles.container}>
      {/* 1. Left Sidebar: Conversation List */}
      <div className="glass-panel" style={styles.inboxSidebar}>
        <div style={styles.sidebarHeader}>
          <h3 style={{ fontSize: '1rem', fontWeight: '600' }}>Inbox</h3>
          <div style={styles.tabButtonGroup}>
            <button 
              style={{
                ...styles.tabButton,
                ...(statusFilter === '' ? styles.tabButtonActive : {})
              }}
              onClick={() => setStatusFilter('')}
            >
              All
            </button>
            <button 
              style={{
                ...styles.tabButton,
                ...(statusFilter === 'AI_ACTIVE' ? styles.tabButtonActive : {})
              }}
              onClick={() => setStatusFilter('AI_ACTIVE')}
            >
              AI Active
            </button>
            <button 
              style={{
                ...styles.tabButton,
                ...(statusFilter === 'WAITING_APPROVAL' ? styles.tabButtonActive : {})
              }}
              onClick={() => setStatusFilter('WAITING_APPROVAL')}
            >
              Wait Approval {pendingApprovals.length > 0 && `(${pendingApprovals.length})`}
            </button>
            <button 
              style={{
                ...styles.tabButton,
                ...(statusFilter === 'OWNER_ACTIVE' ? styles.tabButtonActive : {})
              }}
              onClick={() => setStatusFilter('OWNER_ACTIVE')}
            >
              Human Agent
            </button>
          </div>
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
                  <span className={`badge ${conv.status === 'AI_ACTIVE' ? 'badge-ai' : conv.status === 'WAITING_APPROVAL' ? 'badge-warning' : 'badge-human'}`}>
                    {conv.status === 'AI_ACTIVE' ? 'AI' : conv.status === 'WAITING_APPROVAL' ? 'Approval' : 'Human'}
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
                  color: (chatDetail.status === 'AI_ACTIVE' || chatDetail.status === 'WAITING_APPROVAL') ? 'var(--accent-secondary)' : 'var(--accent-primary)',
                  borderColor: (chatDetail.status === 'AI_ACTIVE' || chatDetail.status === 'WAITING_APPROVAL') ? 'rgba(0, 240, 255, 0.3)' : 'rgba(255, 51, 102, 0.3)'
                }}
                onClick={() => handleToggleTakeover(chatDetail.id, chatDetail.status)}
              >
                {(chatDetail.status === 'AI_ACTIVE' || chatDetail.status === 'WAITING_APPROVAL') ? '⚡ AI Responding (Pause)' : '👤 Owner Responding (Resume)'}
              </button>
            </div>

            {chatDetail.messages && chatDetail.messages.length > 0 && (
              <div style={styles.replayControls}>
                <span style={{ fontSize: '0.8rem', fontWeight: '800' }}>⏮ REPLAY STEPPER:</span>
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={styles.replayBtn}
                  disabled={replayStepIndex === 0}
                  onClick={() => {
                    setReplayStepIndex(0);
                    const msg = chatDetail.messages[0];
                    if (msg.sender === 'ai') setInspectedMessage(msg);
                  }}
                >
                  First
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={styles.replayBtn}
                  disabled={replayStepIndex === 0 || (replayStepIndex === -1 && chatDetail.messages.length <= 1)}
                  onClick={() => {
                    const nextIdx = replayStepIndex === -1 ? chatDetail.messages.length - 2 : replayStepIndex - 1;
                    setReplayStepIndex(nextIdx);
                    const msg = chatDetail.messages[nextIdx];
                    if (msg.sender === 'ai') setInspectedMessage(msg);
                  }}
                >
                  Prev
                </button>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                  {replayStepIndex === -1 ? chatDetail.messages.length : replayStepIndex + 1} of {chatDetail.messages.length}
                </span>
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={styles.replayBtn}
                  disabled={replayStepIndex === -1}
                  onClick={() => {
                    const nextIdx = replayStepIndex === chatDetail.messages.length - 1 ? -1 : replayStepIndex + 1;
                    setReplayStepIndex(nextIdx);
                    if (nextIdx !== -1) {
                      const msg = chatDetail.messages[nextIdx];
                      if (msg.sender === 'ai') setInspectedMessage(msg);
                    } else {
                      setInspectedMessage(null);
                    }
                  }}
                >
                  Next
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={styles.replayBtn}
                  disabled={replayStepIndex === -1}
                  onClick={() => {
                    setReplayStepIndex(-1);
                    setInspectedMessage(null);
                  }}
                >
                  Live Mode
                </button>
              </div>
            )}

            <div style={styles.messagesContainer}>
              {chatDetail.messages && chatDetail.messages
                .slice(0, replayStepIndex === -1 ? chatDetail.messages.length : replayStepIndex + 1)
                .map((msg) => {
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
                        {isAI && msg.metadata && (
                          <button
                            type="button"
                            style={styles.inspectBtn}
                            onClick={() => setInspectedMessage(msg)}
                          >
                            🔍 Inspect Decision
                          </button>
                        )}
                        <span style={styles.msgTime}>
                          {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                    </div>
                  );
                })}
              <div ref={messagesEndRef} />
            </div>

            {chatDetail.status === 'WAITING_APPROVAL' ? (() => {
              const approval = pendingApprovals.find(a => a.conversation_id === chatDetail.id);
              if (!approval) return <div style={{...styles.chatInputForm, padding: '1rem', color: 'var(--text-secondary)'}}>Loading approval request details...</div>;
              
              const getRiskLabel = (score) => {
                if (score >= 70) return { label: 'High Risk', color: 'var(--accent-primary)' };
                if (score >= 35) return { label: 'Medium Risk', color: '#ffcc00' };
                return { label: 'Low Risk', color: 'var(--accent-secondary)' };
              };
              const risk = getRiskLabel(approval.risk_score || 0);

              return (
                <div style={{ ...styles.chatInputForm, flexDirection: 'column', alignItems: 'stretch', backgroundColor: 'rgba(255, 204, 0, 0.1)', border: '1px solid rgba(255, 204, 0, 0.4)' }}>
                  <div style={{ marginBottom: '0.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div>
                      <strong style={{ color: '#ffcc00' }}>⚠️ AI Requesting Approval</strong>
                      <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Rule Triggered: <em>{approval.reason || 'Escalation required'}</em></div>
                    </div>
                    <div style={{ padding: '0.2rem 0.5rem', borderRadius: '4px', fontSize: '0.8rem', backgroundColor: risk.color + '22', color: risk.color, border: `1px solid ${risk.color}55` }}>
                      {risk.label} ({approval.risk_score})
                    </div>
                  </div>
                  <div style={{ marginBottom: '0.5rem', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                    <strong>Intent:</strong> {approval.metadata?.intent || 'Unknown'}<br />
                  </div>
                  <textarea
                    className="form-input"
                    style={{ minHeight: '60px', marginBottom: '0.5rem', resize: 'vertical', width: '100%', fontFamily: 'inherit' }}
                    value={editApprovalText !== '' ? editApprovalText : approval.proposed_response}
                    onChange={(e) => setEditApprovalText(e.target.value)}
                  />
                  <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                    <button type="button" className="btn btn-secondary" style={{ borderColor: 'var(--accent-primary)', color: 'var(--accent-primary)' }} onClick={() => handleRespondToApproval(approval.id, 'reject')}>Reject (Takeover)</button>
                    <button type="button" className="btn btn-secondary" onClick={() => handleRespondToApproval(approval.id, 'edit', editApprovalText || approval.proposed_response)}>Edit & Send</button>
                    <button type="button" className="btn btn-primary" onClick={() => handleRespondToApproval(approval.id, 'approve')}>Approve</button>
                  </div>
                </div>
              );
            })() : (
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
            )}
          </>
        ) : (
          <div style={styles.selectPrompt}>
            <h3>Please select a conversation from the left to manage it.</h3>
          </div>
        )}
      </div>

      {/* 3. Right Sidebar: Customer WhatsApp Simulator Sandbox Console / AI Explainability Inspector */}
      <div className="glass-panel" style={styles.simulatorPanel}>
        {inspectedMessage ? (
          <div>
            <div style={styles.simHeader}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                <h3>AI Inspector</h3>
                <div style={{ display: 'flex', gap: '0.25rem' }}>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem' }}
                    onClick={() => exportDebugLog(chatDetail, inspectedMessage)}
                  >
                    📥 Export
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem' }}
                    onClick={() => setInspectedMessage(null)}
                  >
                    ← Sandbox
                  </button>
                </div>
              </div>
              <p>Audit trail of AI decisions and logic for this message.</p>
            </div>

            <div style={styles.inspectorScroll}>
              <div style={styles.inspectorSection}>
                <div style={styles.label}>Why AI Recommended This</div>
                <div style={{ marginTop: '0.5rem', fontSize: '0.85rem' }}>
                  <strong>✓ Customer requirements detected:</strong>
                  <ul style={{ paddingLeft: '1.25rem', marginTop: '0.25rem', color: 'var(--text-secondary)' }}>
                    {Object.entries(inspectedMessage.metadata.entities_extracted || {}).map(([key, val]) => (
                      val ? (
                        <li key={key}>
                          {key.replace('_', ' ').toUpperCase()}: <strong>{String(val)}</strong>
                        </li>
                      ) : null
                    ))}
                    {(!inspectedMessage.metadata.entities_extracted || Object.keys(inspectedMessage.metadata.entities_extracted).length === 0) && (
                      <li>No specific filters detected (General browsing query)</li>
                    )}
                  </ul>
                </div>
              </div>

              <div style={styles.inspectorSection}>
                <div style={styles.label}>Matching Products Recommended</div>
                {inspectedMessage.metadata.retrieved_products && inspectedMessage.metadata.retrieved_products.length > 0 ? (
                  <ul style={{ paddingLeft: '1.25rem', marginTop: '0.25rem', listStyleType: 'none' }}>
                    {inspectedMessage.metadata.retrieved_products.map((sku, index) => (
                      <li key={sku} style={{ fontSize: '0.85rem', color: 'var(--accent-secondary)', marginBottom: '0.75rem' }}>
                        <strong>{sku}</strong> (Rank #{index + 1})
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          Matches budget, color, and fabric preferences.
                        </div>
                        {/* Rating section */}
                        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginTop: '0.25rem' }}>
                          <button
                            type="button"
                            className="btn btn-secondary"
                            style={{ padding: '0.1rem 0.3rem', fontSize: '0.7rem' }}
                            onClick={() => submitFeedback(inspectedMessage.id, sku, 1)}
                          >
                            👍 Good
                          </button>
                          <select
                            defaultValue=""
                            style={{ padding: '0.1rem 0.3rem', fontSize: '0.7rem', background: 'rgba(0,0,0,0.2)', color: 'var(--text-primary)', border: '1px solid var(--glass-border)' }}
                            onChange={(e) => {
                              if (e.target.value) {
                                submitFeedback(inspectedMessage.id, sku, -1, e.target.value);
                                e.target.value = ""; // Reset
                              }
                            }}
                          >
                            <option value="" disabled>👎 Incorrect (Select Reason)</option>
                            <option value="Wrong Product">Wrong Product</option>
                            <option value="Wrong Budget">Wrong Budget</option>
                            <option value="Wrong Color">Wrong Color</option>
                            <option value="Wrong Fabric">Wrong Fabric</option>
                            <option value="Wrong Size">Wrong Size</option>
                            <option value="Hallucinated">Hallucinated</option>
                            <option value="Other">Other</option>
                          </select>
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>None found matching criteria.</div>
                )}
              </div>

              <div style={styles.inspectorSection}>
                <div style={styles.label}>Excluded/Rejected Products</div>
                {inspectedMessage.metadata.rejected_products && inspectedMessage.metadata.rejected_products.length > 0 ? (
                  <ul style={{ paddingLeft: '1.25rem', marginTop: '0.25rem' }}>
                    {inspectedMessage.metadata.rejected_products.map((sku) => (
                      <li key={sku} style={{ fontSize: '0.85rem', color: 'var(--accent-primary)', marginBottom: '0.4rem' }}>
                        <strong>{sku}</strong>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          Excluded: Budget limit exceeded or item is Out of Stock.
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>None filtered out.</div>
                )}
              </div>

              {inspectedMessage.metadata.escalation_reason && (
                <div style={styles.inspectorSection}>
                  <div style={{ ...styles.label, color: 'var(--accent-primary)' }}>Escalated to Merchant</div>
                  <div style={{ fontSize: '0.85rem', color: 'var(--accent-primary)', marginTop: '0.25rem' }}>
                    Reason: <strong>{inspectedMessage.metadata.escalation_reason}</strong>
                  </div>
                </div>
              )}
            </div>
          </div>
        ) : (
          <>
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
          </>
        )}
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
  tabButtonGroup: {
    display: 'flex',
    backgroundColor: '#111827',
    padding: '2px',
    borderRadius: 'var(--border-radius-sm)',
    border: '1px solid var(--glass-border)',
  },
  tabButton: {
    flex: 1,
    padding: '0.35rem 0.5rem',
    fontSize: '0.72rem',
    fontWeight: '500',
    backgroundColor: 'transparent',
    color: 'var(--text-secondary)',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    textAlign: 'center',
    transition: 'all 0.15s ease',
  },
  tabButtonActive: {
    backgroundColor: 'var(--bg-tertiary)',
    color: 'var(--text-primary)',
    boxShadow: 'var(--shadow-lg)',
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
    background: '#1f2937',
    color: 'var(--text-primary)',
    border: '1px solid #374151',
    borderTopLeftRadius: '2px',
  },
  aiBubble: {
    background: 'var(--accent-primary)',
    color: '#ffffff',
    border: '1px solid var(--accent-primary)',
    borderTopRightRadius: '2px',
  },
  humanBubble: {
    background: '#312e81',
    color: '#ffffff',
    border: '1px solid #4338ca',
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
  inspectBtn: {
    background: 'rgba(255, 255, 255, 0.1)',
    border: '1px solid var(--glass-border)',
    borderRadius: '4px',
    color: 'var(--text-primary)',
    padding: '0.2rem 0.5rem',
    fontSize: '0.75rem',
    cursor: 'pointer',
    marginTop: '0.4rem',
    alignSelf: 'flex-start',
  },
  inspectorScroll: {
    maxHeight: 'calc(100vh - 200px)',
    overflowY: 'auto',
    paddingRight: '0.5rem',
  },
  inspectorSection: {
    marginTop: '1.25rem',
    borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
    paddingBottom: '1rem',
  },
  preCode: {
    background: 'rgba(0, 0, 0, 0.2)',
    padding: '0.5rem',
    borderRadius: '4px',
    fontSize: '0.75rem',
    fontFamily: 'monospace',
    overflowX: 'auto',
    marginTop: '0.4rem',
    color: 'var(--text-secondary)',
  },
  replayControls: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0.5rem 1rem',
    background: 'rgba(255, 255, 255, 0.02)',
    borderBottom: '1px solid var(--glass-border)',
    gap: '0.5rem',
  },
  replayBtn: {
    padding: '0.2rem 0.5rem',
    fontSize: '0.75rem',
  },
};
