import React, { lazy, Suspense, useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Alert } from '../components/Alert';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { adminService } from '../services/adminService';

const AdminCandidateAnalytics = lazy(() => import('../components/AdminCandidateAnalytics').then((module) => ({ default: module.AdminCandidateAnalytics })));

export function AdminCandidateDetail() {
  const { candidateId } = useParams();
  const [detail, setDetail] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    async function load() {
      setIsLoading(true);
      setError('');
      try {
        const data = await adminService.getCandidateDetail(candidateId);
        setDetail(data);
      } catch (err) {
        setError(err.message || 'Candidate details unavailable.');
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, [candidateId]);

  if (isLoading) return <div className="dashboard-container"><div className="card-box text-center py-5"><LoadingSpinner size="medium" message="Loading candidate profile..." /></div></div>;
  if (!detail) return <div className="dashboard-container"><Alert type="error" message={error || 'Candidate not found.'} /></div>;

  const { candidate, performance } = detail;
  const scoredInterviews = (performance.analytics_interviews || []).filter((item) => item.overall_score !== null && item.overall_score !== undefined);
  const improvementText = performance.analytics_interviews?.length === 1 && scoredInterviews.length === 1
    ? 'No previous interview'
    : performance.improvement === null || performance.improvement === undefined
      ? 'N/A'
    : `${performance.improvement > 0 ? '+' : ''}${performance.improvement} percentage points`;

  return (
    <div className="dashboard-container">
      <section className="welcome-banner">
        <div className="welcome-content">
          <h1 className="welcome-title">Candidate Performance</h1>
          <p className="welcome-subtitle">Read-only analytics for {candidate.name}</p>
        </div>
        <div className="welcome-actions">
          <Link to="/admin/dashboard" className="btn btn-secondary">Back to Dashboard</Link>
        </div>
      </section>

      <section className="stats-grid">
        <div className="stat-card"><span className="stat-title">Candidate Name: </span><strong className="stat-value">{candidate.name}</strong></div>
        <div className="stat-card"><span className="stat-title">Email: </span><strong className="stat-value">{candidate.email}</strong></div>
        <div className="stat-card"><span className="stat-title">Interviews: </span><strong className="stat-value">{performance.interviews}</strong></div>
        <div className="stat-card"><span className="stat-title">Average Score: </span><strong className="stat-value">{performance.average_score ?? 'N/A'}{performance.average_score !== null && performance.average_score !== undefined ? '%' : ''}</strong></div>
        <div className="stat-card"><span className="stat-title">Best Score: </span><strong className="stat-value">{performance.best_score ?? 'N/A'}{performance.best_score !== null && performance.best_score !== undefined ? '%' : ''}</strong></div>
        <div className="stat-card"><span className="stat-title">Improvement: </span><strong className="stat-value">{improvementText}</strong></div>
      </section>

      <Suspense fallback={<section className="card-box chart-empty-state">Loading candidate analytics...</section>}>
        <AdminCandidateAnalytics interviews={performance.analytics_interviews || []} />
      </Suspense>

      <section className="card-box" style={{ marginTop: '1.5rem' }}>
        <h2 className="section-title">Interview History</h2>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={{ textAlign: 'left', padding: '0.75rem' }}>Interview</th>
                <th style={{ textAlign: 'left', padding: '0.75rem' }}>Date</th>
                <th style={{ textAlign: 'left', padding: '0.75rem' }}>Score</th>
                <th style={{ textAlign: 'left', padding: '0.75rem' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {(performance.analytics_interviews || []).slice().reverse().map((item) => (
                <tr key={item.interview_id}>
                  <td style={{ padding: '0.75rem', borderBottom: '1px solid #eef2f7' }}>Interview {item.interview_number}</td>
                  <td style={{ padding: '0.75rem', borderBottom: '1px solid #eef2f7' }}>{new Date(item.date).toLocaleDateString()}</td>
                  <td style={{ padding: '0.75rem', borderBottom: '1px solid #eef2f7' }}>{item.overall_score !== null && item.overall_score !== undefined ? `${item.overall_score}%` : 'N/A'}</td>
                  <td style={{ padding: '0.75rem', borderBottom: '1px solid #eef2f7' }}>
                    <Link to={`/admin/interviews/${item.interview_id}`} className="btn btn-secondary btn-sm">View Interview</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
