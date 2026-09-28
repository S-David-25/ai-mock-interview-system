import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Alert } from '../components/Alert';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { adminService } from '../services/adminService';

const AdminDashboardCharts = React.lazy(() => import('../components/AdminDashboardCharts').then((module) => ({ default: module.AdminDashboardCharts })));

export function AdminDashboard() {
  const [dashboard, setDashboard] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [analyticsLoading, setAnalyticsLoading] = useState(true);
  const [selectedCandidateId, setSelectedCandidateId] = useState('');
  const [error, setError] = useState('');

  const loadDashboard = async (overridePage = page, overrideSearch = search) => {
    setIsLoading(true);
    setError('');
    try {
      const data = await adminService.getCandidates({ page: overridePage, limit: 20, search: overrideSearch });
      setDashboard(data);
    } catch (err) {
      setError(err.message || 'Failed to load admin dashboard.');
    } finally {
      setIsLoading(false);
    }
  };

  const loadAnalytics = async () => {
    try {
      const data = await adminService.getDashboard();
      setAnalytics(data);
    } catch (err) {
      setError(err.message || 'Failed to load admin analytics.');
    } finally {
      setAnalyticsLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard(page, search);
  }, [page]);

  useEffect(() => {
    loadAnalytics();
  }, []);

  useEffect(() => {
    if (page !== 1) setPage(1);
    else loadDashboard(1, search);
  }, [search]);

  const summary = useMemo(() => {
    if (!dashboard) return null;
    return {
      totalCandidates: analytics?.total_candidates ?? 0,
      candidates: dashboard.items ?? [],
      totalPages: dashboard.total_pages ?? 0,
    };
  }, [dashboard, analytics]);

  const progressionData = useMemo(() => {
    const points = analytics?.score_progression ?? [];
    if (selectedCandidateId) {
      return points
        .filter((point) => String(point.candidate_id) === selectedCandidateId)
        .map((point) => ({ ...point, label: `Interview ${point.interview_number}` }));
    }

    const averages = new Map();
    points.forEach((point) => {
      const current = averages.get(point.interview_number) || { label: `Interview ${point.interview_number}`, scoreTotal: 0, count: 0 };
      current.scoreTotal += point.score;
      current.count += 1;
      averages.set(point.interview_number, current);
    });
    return [...averages.values()].map((point) => ({
      label: point.label,
      score: Math.round((point.scoreTotal / point.count) * 10) / 10,
      candidate_count: point.count,
    }));
  }, [analytics, selectedCandidateId]);

  const handleSearch = (event) => {
    setSearch(event.target.value);
  };

  return (
    <div className="dashboard-container">
      <section className="welcome-banner">
        <div className="welcome-content">
          <h1 className="welcome-title">Admin Dashboard</h1>
          <p className="welcome-subtitle">Read-only access to candidate performance and interview analytics.</p>
        </div>
      </section>

      <Alert type="error" message={error} onDismiss={() => setError('')} />

      {isLoading ? (
        <div className="card-box text-center py-5"><LoadingSpinner size="medium" message="Loading candidate analytics..." /></div>
      ) : (
        <>
          <section className="stats-grid">
            <div className="stat-card">
              <span className="stat-title">Total Candidates: </span>
              <strong className="stat-value">{summary?.totalCandidates ?? 0}</strong>
            </div>
            <div className="stat-card">
              <span className="stat-title">Total Interviews: </span>
              <strong className="stat-value">{analytics?.total_interviews ?? 0}</strong>
            </div>
            <div className="stat-card">
              <span className="stat-title">Average Candidate Score: </span>
              <strong className="stat-value">{analytics?.average_score ?? 0}%</strong>
            </div>
            <div className="stat-card">
              <span className="stat-title">Highest Score: </span>
              <strong className="stat-value">{analytics?.highest_score ?? 0}%</strong>
            </div>
            <div className="stat-card">
              <span className="stat-title">Average Improvement: </span>
              <strong className="stat-value">{analytics?.average_improvement ?? 0}%</strong>
            </div>
            <div className="stat-card">
              <span className="stat-title">Active Candidates: </span>
              <strong className="stat-value">{analytics?.active_candidates ?? 0}</strong>
            </div>
          </section>

          <React.Suspense fallback={<section className="admin-chart-grid"><div className="admin-chart-card chart-empty-state">Loading analytics charts...</div></section>}>
            <AdminDashboardCharts
              analytics={analytics}
              analyticsLoading={analyticsLoading}
              progressionData={progressionData}
              selectedCandidateId={selectedCandidateId}
              onCandidateChange={setSelectedCandidateId}
            />
          </React.Suspense>

          <section className="card-box" style={{ marginTop: '1.5rem' }}>
            <div className="section-header">
              <div>
                <h2 className="section-title">Candidate Performance Overview</h2>
                <p className="section-subtitle">Search and review read-only candidate performance.</p>
              </div>
            </div>

            <div className="form-group" style={{ maxWidth: '420px', marginTop: '1rem' }}>
              <input
                type="text"
                value={search}
                onChange={handleSearch}
                placeholder="Search candidate by name or email"
              />
            </div>

            {summary?.candidates?.length ? (
              <div style={{ overflowX: 'auto', marginTop: '1rem' }}>
                <table className="admin-candidates-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr>
                      <th style={{ textAlign: 'left', padding: '0.75rem', borderBottom: '1px solid #e2e8f0' }}>Candidate</th>
                      <th style={{ textAlign: 'left', padding: '0.75rem', borderBottom: '1px solid #e2e8f0' }}>Email</th>
                      <th style={{ textAlign: 'left', padding: '0.75rem', borderBottom: '1px solid #e2e8f0' }}>Interviews</th>
                      <th style={{ textAlign: 'left', padding: '0.75rem', borderBottom: '1px solid #e2e8f0' }}>Avg Score</th>
                      <th style={{ textAlign: 'left', padding: '0.75rem', borderBottom: '1px solid #e2e8f0' }}>Best Score</th>
                      <th style={{ textAlign: 'left', padding: '0.75rem', borderBottom: '1px solid #e2e8f0' }}>Improvement</th>
                      <th style={{ textAlign: 'left', padding: '0.75rem', borderBottom: '1px solid #e2e8f0' }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.candidates.map((candidate) => (
                      <tr key={candidate.id}>
                        <td style={{ padding: '0.75rem', borderBottom: '1px solid var(--table-row-border)' }}>{candidate.name}</td>
                        <td style={{ padding: '0.75rem', borderBottom: '1px solid var(--table-row-border)' }}>{candidate.email}</td>
                        <td style={{ padding: '0.75rem', borderBottom: '1px solid var(--table-row-border)' }}>{candidate.interviews}</td>
                        <td style={{ padding: '0.75rem', borderBottom: '1px solid var(--table-row-border)' }}>{candidate.avg_score ?? 0}%</td>
                        <td style={{ padding: '0.75rem', borderBottom: '1px solid var(--table-row-border)' }}>{candidate.best_score ?? 0}%</td>
                        <td style={{ padding: '0.75rem', borderBottom: '1px solid var(--table-row-border)' }}>{candidate.improvement ?? 0}%</td>
                        <td style={{ padding: '0.75rem', borderBottom: '1px solid var(--table-row-border)' }}>
                          <Link to={`/admin/candidates/${candidate.id}`} className="btn btn-secondary btn-sm">View Details</Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="empty-state-card"><h3>No candidates registered yet.</h3></div>
            )}

            {summary?.totalPages > 1 && (
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1rem' }}>
                <button className="btn btn-secondary btn-sm" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>Previous</button>
                <span>Page {page} of {summary.totalPages}</span>
                <button className="btn btn-secondary btn-sm" disabled={page >= summary.totalPages} onClick={() => setPage((p) => Math.min(summary.totalPages, p + 1))}>Next</button>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
