import React from 'react';

export function StatCard({ title, value, subtitle, icon, highlightColor = '#3b82f6' }) {
  return (
    <div className="stat-card">
      <div className="stat-card-header">
        <span className="stat-card-title">{title}</span>
        <div className="stat-card-icon" style={{ color: highlightColor, backgroundColor: `${highlightColor}15` }}>
          {icon}
        </div>
      </div>
      <div className="stat-card-value">{value ?? '—'}</div>
      {subtitle && <div className="stat-card-subtitle">{subtitle}</div>}
    </div>
  );
}
