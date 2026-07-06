import React, { useState } from 'react';

export default function Auth({ onLoginSuccess }) {
  const [isSignup, setIsSignup] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [orgName, setOrgName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    const baseUrl = 'http://localhost:8000';
    
    try {
      if (isSignup) {
        // Signup
        const signupResponse = await fetch(`${baseUrl}/api/auth/signup`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, name, password, organization_name: orgName }),
        });

        if (!signupResponse.ok) {
          const errData = await signupResponse.json();
          throw new Error(errData.detail || 'Signup failed. Please try again.');
        }
      }

      // Login
      const formData = new URLSearchParams();
      formData.append('username', email);
      formData.append('password', password);

      const loginResponse = await fetch(`${baseUrl}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData.toString(),
      });

      if (!loginResponse.ok) {
        const errData = await loginResponse.json();
        throw new Error(errData.detail || 'Invalid email or password.');
      }

      const loginData = await loginResponse.json();
      localStorage.setItem('token', loginData.access_token);
      onLoginSuccess(loginData.access_token);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.container}>
      <div className="glass-panel" style={styles.card}>
        <div style={styles.header}>
          <div style={styles.logo}>🛒</div>
          <h2 style={styles.title}>
            Closely <span className="gradient-text">AI</span>
          </h2>
          <p style={styles.subtitle}>Your Autonomous AI Sales Employee</p>
        </div>

        <form onSubmit={handleSubmit} style={styles.form}>
          {isSignup && (
            <>
              <div style={styles.inputGroup}>
                <label style={styles.label}>Name</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="Kiran Kumar"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </div>
              <div style={styles.inputGroup}>
                <label style={styles.label}>Brand Name</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="Kiran Sarees"
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  required
                />
              </div>
            </>
          )}

          <div style={styles.inputGroup}>
            <label style={styles.label}>Email Address</label>
            <input
              type="email"
              className="form-input"
              placeholder="kiran@brand.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div style={styles.inputGroup}>
            <label style={styles.label}>Password</label>
            <input
              type="password"
              className="form-input"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          {error && <div style={styles.error}>{error}</div>}

          <button type="submit" className="btn btn-primary" style={styles.button} disabled={loading}>
            {loading ? 'Processing...' : isSignup ? 'Create Account' : 'Sign In'}
          </button>
        </form>

        <div style={styles.footer}>
          <span style={styles.footerText}>
            {isSignup ? 'Already have an account?' : "Don't have an account?"}
          </span>
          <button
            onClick={() => {
              setError('');
              setIsSignup(!isSignup);
            }}
            style={styles.toggleBtn}
          >
            {isSignup ? 'Sign In' : 'Sign Up'}
          </button>
        </div>
      </div>
    </div>
  );
}

const styles = {
  container: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '100vh',
    padding: '1.5rem',
    background: 'radial-gradient(circle at top right, rgba(0, 240, 255, 0.05), transparent 40%), radial-gradient(circle at bottom left, rgba(255, 51, 102, 0.05), transparent 40%)',
  },
  card: {
    width: '100%',
    maxWidth: '420px',
    padding: '2.5rem 2rem',
    borderRadius: 'var(--border-radius-lg)',
    animation: 'fadeIn 0.5s ease',
  },
  header: {
    textAlign: 'center',
    marginBottom: '2rem',
  },
  logo: {
    fontSize: '2.5rem',
    marginBottom: '0.5rem',
  },
  title: {
    fontSize: '1.8rem',
    marginBottom: '0.25rem',
  },
  subtitle: {
    fontSize: '0.85rem',
    color: 'var(--text-secondary)',
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: '1.25rem',
  },
  inputGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.4rem',
  },
  label: {
    fontSize: '0.8rem',
    fontWeight: '600',
    color: 'var(--text-secondary)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  },
  button: {
    marginTop: '0.5rem',
    width: '100%',
    height: '46px',
  },
  error: {
    color: 'var(--danger)',
    fontSize: '0.85rem',
    background: 'rgba(239, 68, 68, 0.1)',
    border: '1px solid rgba(239, 68, 68, 0.2)',
    padding: '0.75rem',
    borderRadius: 'var(--border-radius-sm)',
    textAlign: 'center',
  },
  footer: {
    marginTop: '1.5rem',
    textAlign: 'center',
    fontSize: '0.85rem',
  },
  footerText: {
    color: 'var(--text-secondary)',
    marginRight: '0.5rem',
  },
  toggleBtn: {
    background: 'none',
    border: 'none',
    color: 'var(--accent-secondary)',
    fontWeight: '600',
    cursor: 'pointer',
    outline: 'none',
  },
};
