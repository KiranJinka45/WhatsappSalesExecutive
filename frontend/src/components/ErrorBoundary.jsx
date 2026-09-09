import React from 'react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ errorInfo });
    console.error("ErrorBoundary caught an unhandled rendering error:", error, errorInfo);
  }

  handleReload = () => {
    window.location.reload();
  };

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div style={styles.container}>
          <div className="glass-panel" style={styles.card}>
            <span style={{ fontSize: '3rem' }}>🛡️</span>
            <h2 style={{ margin: '0.5rem 0', color: 'var(--accent-primary)' }}>Application Error Intercepted</h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', maxWidth: '500px', lineHeight: '1.5' }}>
              Closely AI encountered an unexpected client-side rendering error. The error boundary caught the fault to prevent a white-screen crash.
            </p>

            {this.state.error && (
              <div style={styles.errorBox}>
                <code>{this.state.error.toString()}</code>
              </div>
            )}

            <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem' }}>
              <button className="btn btn-primary" onClick={this.handleReload}>
                🔄 Reload Dashboard
              </button>
              <button className="btn btn-secondary" onClick={this.handleReset}>
                Dismiss & Retry View
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

const styles = {
  container: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '100vh',
    width: '100vw',
    backgroundColor: 'var(--bg-primary)',
    padding: '2rem',
    boxSizing: 'border-box',
  },
  card: {
    padding: '2.5rem',
    borderRadius: 'var(--border-radius-md)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    textAlign: 'center',
    maxWidth: '600px',
    width: '100%',
  },
  errorBox: {
    marginTop: '1rem',
    padding: '0.75rem 1rem',
    background: 'rgba(239, 68, 68, 0.1)',
    border: '1px solid rgba(239, 68, 68, 0.3)',
    borderRadius: '4px',
    color: '#fca5a5',
    fontSize: '0.8rem',
    textAlign: 'left',
    width: '100%',
    overflowX: 'auto',
  },
};
