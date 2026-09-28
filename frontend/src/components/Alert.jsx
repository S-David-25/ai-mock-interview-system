import React from 'react';

export function Alert({ type = 'error', message, onDismiss }) {
  if (!message) return null;

  const styles = {
    error: {
      bg: 'var(--alert-error-bg)',
      border: 'var(--alert-error-border)',
      color: 'var(--alert-error-text)',
      icon: '⚠️'
    },
    success: {
      bg: 'var(--alert-success-bg)',
      border: 'var(--alert-success-border)',
      color: 'var(--alert-success-text)',
      icon: '✅'
    },
    info: {
      bg: 'var(--alert-info-bg)',
      border: 'var(--alert-info-border)',
      color: 'var(--alert-info-text)',
      icon: 'ℹ️'
    },
    warning: {
      bg: 'var(--alert-warning-bg)',
      border: 'var(--alert-warning-border)',
      color: 'var(--alert-warning-text)',
      icon: '⚡'
    }
  };

  const style = styles[type] || styles.error;

  return (
    <div style={{
      backgroundColor: style.bg,
      border: `1px solid ${style.border}`,
      color: style.color,
      padding: '0.85rem 1.15rem',
      borderRadius: '8px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      margin: '0.75rem 0',
      fontSize: '0.925rem',
      fontWeight: '500',
      boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
      animation: 'fadeIn 0.2s ease-in-out'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
        <span>{style.icon}</span>
        <span>{message}</span>
      </div>
      {onDismiss && (
        <button
          onClick={onDismiss}
          style={{
            background: 'none',
            border: 'none',
            color: style.color,
            cursor: 'pointer',
            fontSize: '1.1rem',
            padding: '0 0.25rem',
            opacity: 0.75
          }}
          title="Dismiss"
        >
          ✕
        </button>
      )}
    </div>
  );
}
