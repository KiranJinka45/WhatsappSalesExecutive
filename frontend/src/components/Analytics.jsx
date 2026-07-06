import React, { useState, useEffect } from 'react';

export default function Analytics({ token }) {
  const [stats, setStats] = useState({
    conversationsCount: 124,
    aiResolutionRate: 74, // %
    humanTakeoverCount: 32,
    medianResponseTime: 2.8, // sec
    activeLeads: 18,
    topProducts: [
      { sku: 'SKU001', name: 'Banarasi Silk Saree', views: 82 },
      { sku: 'SKU003', name: 'Cotton Designer Kurta', views: 45 },
      { sku: 'SKU002', name: 'Kanchipuram Silk Saree', views: 31 }
    ]
  });

  const baseUrl = 'http://localhost:8000';

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      // Fetch stats from backend API
      const res = await fetch(`${baseUrl}/api/analytics/dashboard`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setStats(prev => ({
          ...prev,
          conversationsCount: data.total_conversations,
          humanTakeoverCount: data.human_takeover_count,
          aiResolutionRate: Math.round(data.ai_containment_rate),
          activeLeads: data.ai_active_count + data.human_takeover_count,
          // Custom addition: display other backend metrics if available
          conversationsToday: data.conversations_today
        }));
      }
    } catch (err) {
      console.error("Error fetching stats:", err);
    }
  };

  return (
    <div style={styles.container}>
      {/* 1. Metric Cards Grid */}
      <div style={styles.metricsGrid}>
        <div className="glass-card animate-fade-in" style={styles.metricCard}>
          <div style={styles.metricLabel}>Total Conversations</div>
          <div style={styles.metricValue}>{stats.conversationsCount}</div>
          <div style={styles.metricChange}>⚡ Active this month</div>
        </div>

        <div className="glass-card animate-fade-in" style={{ ...styles.metricCard, animationDelay: '0.1s' }}>
          <div style={styles.metricLabel}>AI Resolution Rate</div>
          <div style={{ ...styles.metricValue, color: 'var(--accent-secondary)' }}>{stats.aiResolutionRate}%</div>
          <div style={styles.metricChange}>🎯 Target: &ge; 70%</div>
        </div>

        <div className="glass-card animate-fade-in" style={{ ...styles.metricCard, animationDelay: '0.2s' }}>
          <div style={styles.metricLabel}>Human Escalations</div>
          <div style={{ ...styles.metricValue, color: 'var(--accent-primary)' }}>{stats.humanTakeoverCount}</div>
          <div style={styles.metricChange}>👥 Awaiting staff response</div>
        </div>

        <div className="glass-card animate-fade-in" style={{ ...styles.metricCard, animationDelay: '0.3s' }}>
          <div style={styles.metricLabel}>Median Response Latency</div>
          <div style={{ ...styles.metricValue, color: 'var(--success)' }}>{stats.medianResponseTime}s</div>
          <div style={styles.metricChange}> P50 processing time</div>
        </div>
      </div>

      {/* 2. Top Products & Funnel Section */}
      <div style={styles.detailsSection}>
        {/* Top Products */}
        <div className="glass-panel" style={styles.detailCard}>
          <h3>🔥 Top Viewed Products</h3>
          <p style={styles.subtitle}>Most popular items inquired about in AI conversations.</p>
          <div style={styles.productsList}>
            {stats.topProducts.map((p, idx) => (
              <div key={p.sku} style={styles.productRow}>
                <div style={styles.prodRank}>#{idx + 1}</div>
                <div style={styles.prodInfo}>
                  <strong>{p.name}</strong>
                  <small style={{ color: 'var(--text-secondary)' }}>SKU: {p.sku}</small>
                </div>
                <div style={styles.prodViews}>{p.views} inquiries</div>
              </div>
            ))}
          </div>
        </div>

        {/* Funnel chart */}
        <div className="glass-panel" style={styles.detailCard}>
          <h3>📊 Intent Classification Distribution</h3>
          <p style={styles.subtitle}>Customer inquiries breakdown by NLU intent.</p>
          <div style={styles.funnel}>
            <div style={styles.funnelItem}>
              <span>1. Product Discovery</span>
              <div style={styles.barContainer}>
                <div style={{ ...styles.bar, width: '48%', background: 'var(--accent-primary)' }} />
                <span>48%</span>
              </div>
            </div>
            <div style={styles.funnelItem}>
              <span>2. Product Information</span>
              <div style={styles.barContainer}>
                <div style={{ ...styles.bar, width: '22%', background: 'var(--accent-secondary)' }} />
                <span>22%</span>
              </div>
            </div>
            <div style={styles.funnelItem}>
              <span>3. Logistics & Policies</span>
              <div style={styles.barContainer}>
                <div style={{ ...styles.bar, width: '18%', background: 'var(--success)' }} />
                <span>18%</span>
              </div>
            </div>
            <div style={styles.funnelItem}>
              <span>4. Price Negotiation</span>
              <div style={styles.barContainer}>
                <div style={{ ...styles.bar, width: '12%', background: 'var(--warning)' }} />
                <span>12%</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

const styles = {
  container: {
    padding: '0 1rem 2rem 1rem',
    overflowY: 'auto',
    height: 'calc(100vh - 90px)',
    display: 'flex',
    flexDirection: 'column',
    gap: '1.5rem',
  },
  metricsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
    gap: '1rem',
  },
  metricCard: {
    borderRadius: 'var(--border-radius-md)',
  },
  metricLabel: {
    fontSize: '0.8rem',
    fontWeight: '700',
    color: 'var(--text-secondary)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  },
  metricValue: {
    fontSize: '2.5rem',
    fontFamily: 'var(--font-title)',
    fontWeight: '800',
    margin: '0.5rem 0',
  },
  metricChange: {
    fontSize: '0.8rem',
    color: 'var(--text-muted)',
  },
  detailsSection: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '1rem',
  },
  detailCard: {
    padding: '1.5rem',
    borderRadius: 'var(--border-radius-md)',
  },
  subtitle: {
    fontSize: '0.8rem',
    color: 'var(--text-secondary)',
    marginBottom: '1rem',
  },
  productsList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.75rem',
  },
  productRow: {
    display: 'flex',
    alignItems: 'center',
    padding: '0.75rem',
    background: 'rgba(255, 255, 255, 0.02)',
    borderRadius: 'var(--border-radius-sm)',
    border: '1px solid var(--glass-border)',
  },
  prodRank: {
    fontSize: '1rem',
    fontFamily: 'var(--font-title)',
    fontWeight: '800',
    color: 'var(--accent-secondary)',
    width: '40px',
  },
  prodInfo: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
  },
  prodViews: {
    fontSize: '0.85rem',
    fontWeight: '600',
    color: 'var(--accent-primary)',
  },
  funnel: {
    display: 'flex',
    flexDirection: 'column',
    gap: '1rem',
  },
  funnelItem: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.4rem',
    fontSize: '0.85rem',
  },
  barContainer: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.75rem',
  },
  bar: {
    height: '10px',
    borderRadius: '5px',
  },
};
