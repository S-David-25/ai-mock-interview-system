import React, { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { interviewService } from '../services/interviewService';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { Alert } from '../components/Alert';
import { formatDate } from '../utils/formatters';

export function InterviewCompare() {
  const [searchParams, setSearchParams] = useSearchParams();
  const firstIdParam = searchParams.get('first_id');
  const secondIdParam = searchParams.get('second_id');

  const [interviews, setInterviews] = useState([]);
  const [firstId, setFirstId] = useState(firstIdParam || '');
  const [secondId, setSecondId] = useState(secondIdParam || '');
  const [comparison, setComparison] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  // 1. Fetch completed interviews for dropdown selection
  useEffect(() => {
    async function loadCompleted() {
      try {
        const data = await interviewService.getInterviews();
        const completed = (data.interviews || []).filter(i => i.status === 'completed' && i.overall_score !== null);
        setInterviews(completed);

        if (completed.length >= 2) {
          const fid = firstIdParam || completed[completed.length - 2].id;
          const sid = secondIdParam || completed[completed.length - 1].id;
          setFirstId(String(fid));
          setSecondId(String(sid));
          runComparison(fid, sid);
        } else if (completed.length === 1) {
          setFirstId(String(completed[0].id));
          setSecondId(String(completed[0].id));
        }
      } catch (e) {
        setError(e.message || 'Failed to load interviews list.');
      }
    }
    loadCompleted();
  }, []);

  const runComparison = async (fId, sId) => {
    if (!fId || !sId) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await interviewService.compareInterviews(fId, sId);
      setComparison(data);
    } catch (e) {
      setError(e.message || 'Failed to compare interview sessions.');
      setComparison(null);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectChange = (e, target) => {
    const val = e.target.value;
    if (target === 'first') {
      setFirstId(val);
      runComparison(val, secondId);
    } else {
      setSecondId(val);
      runComparison(firstId, val);
    }
  };

  return (
    <div className="report-container">
      {/* Top Navigation */}
      <div className="report-header-top" style={{ marginBottom: '1.5rem' }}>
        <Link to="/dashboard" className="back-link">
          ← Back to Dashboard
        </Link>
      </div>

      <div className="report-header-card">
        <span className="report-badge">Progress Analytics</span>
        <h1 className="report-main-title">Interview Performance Comparison</h1>
        <p className="report-meta-text">
          Compare two mock interview sessions side-by-side to evaluate placement competency improvements over time.
        </p>

        {/* Selection Bar */}
        <div className="comparison-selector-bar">
          <div className="selector-group">
            <label>Baseline Session (Interview 1):</label>
            <select value={firstId} onChange={(e) => handleSelectChange(e, 'first')}>
              {interviews.map(i => (
                <option key={i.id} value={i.id}>
                  #{i.id} - {i.company_name || 'General'} ({formatDate(i.created_at)}) [{i.overall_score}%]
                </option>
              ))}
            </select>
          </div>

          <div className="vs-badge">VS</div>

          <div className="selector-group">
            <label>Recent Session (Interview 2):</label>
            <select value={secondId} onChange={(e) => handleSelectChange(e, 'second')}>
              {interviews.map(i => (
                <option key={i.id} value={i.id}>
                  #{i.id} - {i.company_name || 'General'} ({formatDate(i.created_at)}) [{i.overall_score}%]
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <Alert type="error" message={error} onDismiss={() => setError(null)} />

      {isLoading ? (
        <div className="page-container py-5 text-center">
          <LoadingSpinner size="large" message="Computing dimension deltas and performance improvements..." />
        </div>
      ) : comparison ? (
        <div className="comparison-content">
          {/* Delta Banner */}
          <div className="comparison-delta-banner">
            <div className="delta-stat">
              <span className="delta-label">Baseline Score</span>
              <span className="delta-val">{comparison.first_overall_score}%</span>
            </div>
            <div className="delta-arrow">➔</div>
            <div className="delta-stat">
              <span className="delta-label">Recent Score</span>
              <span className="delta-val">{comparison.second_overall_score}%</span>
            </div>
            <div className="delta-badge-box">
              <span className={`overall-delta-pill ${comparison.overall_status.toLowerCase()}`}>
                {comparison.overall_delta >= 0 ? `+${comparison.overall_delta}%` : `${comparison.overall_delta}%`} Overall ({comparison.overall_status})
              </span>
            </div>
          </div>

          {/* Highlights Grid */}
          <div className="grid-3-col" style={{ marginBottom: '1.5rem' }}>
            <div className="highlight-card border-green">
              <h3 className="text-green">📈 Improved Competencies</h3>
              {comparison.improved_areas && comparison.improved_areas.length > 0 ? (
                <ul>
                  {comparison.improved_areas.map((a, idx) => <li key={idx}>✓ {a}</li>)}
                </ul>
              ) : (
                <p style={{ fontSize: '0.85rem', color: '#64748b' }}>No dimension registered positive delta.</p>
              )}
            </div>

            <div className="highlight-card border-amber">
              <h3 className="text-amber">📉 Focus Needed</h3>
              {comparison.declined_areas && comparison.declined_areas.length > 0 ? (
                <ul>
                  {comparison.declined_areas.map((a, idx) => <li key={idx}>⚠ {a}</li>)}
                </ul>
              ) : (
                <p style={{ fontSize: '0.85rem', color: '#166534' }}>✓ No dimension showed negative score delta!</p>
              )}
            </div>

            <div className="highlight-card border-blue">
              <h3 className="text-blue">⚖️ Stable Dimensions</h3>
              {comparison.unchanged_areas && comparison.unchanged_areas.length > 0 ? (
                <ul>
                  {comparison.unchanged_areas.map((a, idx) => <li key={idx}>• {a}</li>)}
                </ul>
              ) : (
                <p style={{ fontSize: '0.85rem', color: '#64748b' }}>All dimensions showed active delta.</p>
              )}
            </div>
          </div>

          {/* Dimension Comparison Table */}
          <div className="report-section-card">
            <h2 className="section-heading">📊 Dimension-by-Dimension Breakdown</h2>
            <div className="table-responsive">
              <table className="scoring-table">
                <thead>
                  <tr>
                    <th>Evaluation Dimension</th>
                    <th>Session #{comparison.first_interview_id}</th>
                    <th>Session #{comparison.second_interview_id}</th>
                    <th>Score Delta (Δ)</th>
                    <th>Trajectory Status</th>
                  </tr>
                </thead>
                <tbody>
                  {comparison.dimension_comparisons.map((dim, idx) => (
                    <tr key={idx}>
                      <td><strong>{dim.dimension_name}</strong></td>
                      <td>{dim.first_score}%</td>
                      <td>{dim.second_score}%</td>
                      <td>
                        <strong style={{ color: dim.delta > 0 ? '#16a34a' : (dim.delta < 0 ? '#dc2626' : '#64748b') }}>
                          {dim.delta > 0 ? `+${dim.delta}%` : `${dim.delta}%`}
                        </strong>
                      </td>
                      <td>
                        <span className={`status-pill ${dim.status.toLowerCase()}`}>{dim.status}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : (
        <div className="empty-state-card">
          <p>Please complete at least 2 interview sessions to view side-by-side performance trajectories.</p>
        </div>
      )}
    </div>
  );
}
