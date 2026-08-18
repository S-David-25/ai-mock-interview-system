/**
 * Formatting helpers for UI presentation.
 */

export function formatDate(dateString) {
  if (!dateString) return 'N/A';
  try {
    const d = new Date(dateString.endsWith('Z') ? dateString : dateString + 'Z');
    return d.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  } catch (e) {
    return dateString;
  }
}

export function formatScore(score) {
  if (score === null || score === undefined || isNaN(score)) {
    return 'N/A';
  }
  return `${Number(score).toFixed(1)}%`;
}

export function formatFileSize(bytes) {
  if (!bytes || isNaN(bytes)) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

export function getStatusInfo(status) {
  switch (status) {
    case 'ready':
      return { label: 'Ready to Start', bg: '#dcfce7', color: '#15803d', border: '#86efac' };
    case 'in_progress':
      return { label: 'In Progress', bg: '#fef3c7', color: '#b45309', border: '#fde68a' };
    case 'completed':
      return { label: 'Completed', bg: '#e0e7ff', color: '#4338ca', border: '#c7d2fe' };
    case 'failed':
      return { label: 'Failed', bg: '#fee2e2', color: '#b91c1c', border: '#fca5a5' };
    case 'setup':
    default:
      return { label: 'Setup Incomplete', bg: '#f1f5f9', color: '#475569', border: '#cbd5e1' };
  }
}
