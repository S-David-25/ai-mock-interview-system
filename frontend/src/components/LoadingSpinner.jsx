import React from 'react';

export function LoadingSpinner({ size = 'medium', message = 'Loading...' }) {
  const sizeMap = {
    small: '1.25rem',
    medium: '2rem',
    large: '3rem',
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '2rem',
      gap: '0.75rem'
    }}>
      <div className="spinner" style={{ width: sizeMap[size], height: sizeMap[size] }} />
      {message && <span style={{ color: '#64748b', fontSize: '0.9rem', fontWeight: '500' }}>{message}</span>}
    </div>
  );
}
