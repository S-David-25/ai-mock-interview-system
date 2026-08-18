import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { interviewService } from '../services/interviewService';
import { StatCard } from '../components/StatCard';
import { InterviewCard } from '../components/InterviewCard';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { Alert } from '../components/Alert';
import { formatDate } from '../utils/formatters';

export function Dashboard() {
  const { user } = useAuth();
  const [interviews, setInterviews] = useState([]);
  const [stats, setStats] = useState(null);
  const [progress, setProgress] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchDashboardData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [intData, progData] = await Promise.all([
        interviewService.getInterviews(),
        interviewService.getProgress(),
      ]);
      setInterviews(intData.interviews || []);
      setStats(intData.stats || null);
      setProgress(progData || null);
    } catch (err) {
      setError(err.message || 'Failed to fetch placement dashboard metrics.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const averageScoreText = stats?.average_score !== null && stats?.average_score !== undefined
    ? `${stats.average_score}%`
    : 'N/A';

  const latestScoreText = stats?.latest_score !== null && stats?.latest_score !== undefined
    ? `${stats.latest_score}%`
    : 'N/A';

  const bestScoreText = progress?.best_score !== null && progress?.best_score !== undefined
    ? `${progress.best_score}%`
    : 'N/A';

  const totalImprovementText = progress?.total_score_improvement !== null && progress?.total_score_improvement !== undefined
    ? (progress.total_score_improvement >= 0 ? `+${progress.total_score_improvement}%` : `${progress.total_score_improvement}%`)
    : '—';

  return (
    <div className="dashboard-container">
      {/* Welcome Banner */}
      <section className="welcome-banner">
        <div className="welcome-content">
          <h1 className="welcome-title">
            Welcome, <span className="highlight-text">{user?.name || 'Student'}</span> 👋
          </h1>
          <p className="welcome-subtitle">
            Practice AI voice placement interviews, review multi-modal performance analytics, and follow your personalized roadmap.
          </p>
        </div>
        <div className="welcome-actions">
          <Link to="/setup" className="btn btn-primary btn-lg shadow-glow">
            <span style={{ fontSize: '1.2rem' }}>⚡</span> Start New Interview
          </Link>
        </div>
      </section>

      <Alert type="error" message={error} onDismiss={() => setError(null)} />

      {/* Metrics Row */}
      <section className="stats-grid">
        <StatCard
          title="Total Interviews"
          value={stats?.total_interviews ?? 0}
          subtitle="All created practice sessions"
          icon="📊"
          highlightColor="#2563eb"
        />
        <StatCard
          title="Average Score"
          value={averageScoreText}
          subtitle="Across completed sessions"
          icon="🎯"
          highlightColor="#16a34a"
        />
        <StatCard
          title="Best Score"
          value={bestScoreText}
          subtitle="Highest evaluation achieved"
          icon="🏆"
          highlightColor="#d97706"
        />
        <StatCard
          title="Score Improvement"
          value={totalImprovementText}
          subtitle="Longitudinal progress delta"
          icon="📈"
          highlightColor="#9333ea"
        />
      </section>

      {/* Longitudinal Progress Trends Section (Master Prompt 3) */}
      {progress && progress.trend_data && progress.trend_data.length > 0 && (
        <section className="progress-trends-card" style={{ marginBottom: '2.5rem' }}>
          <div className="section-header">
            <div>
              <h2 className="section-title">📈 Longitudinal Progress Trends</h2>
              <p className="section-subtitle">Score improvement trajectories across completed mock interviews</p>
            </div>
            {progress.trend_data.length >= 2 && (
              <Link to="/interviews/compare" className="btn btn-secondary btn-sm">
                🔍 Compare Sessions Side-by-Side
              </Link>
            )}
          </div>

          <div className="progress-trajectory-grid">
            {progress.trend_data.map((item, idx) => (
              <div key={item.interview_id} className="trend-point-card">
                <div className="trend-card-top">
                  <span className="session-index-pill">Session #{item.interview_id}</span>
                  <span className="trend-date">{formatDate(item.date)}</span>
                </div>
                <div className="trend-score-large">{item.overall_score}%</div>
                <div className="trend-company-name">
                  {item.company_name ? `🏢 ${item.company_name}` : '🌐 General Mock'}
                </div>

                <div className="sub-scores-mini-row">
                  <span>Tech: {item.technical_score}%</span>
                  <span>Comm: {item.communication_score}%</span>
                  <span>Fluency: {item.fluency_score}%</span>
                </div>

                <Link to={`/interviews/${item.interview_id}/report`} className="btn btn-outline btn-sm btn-block" style={{ marginTop: '0.75rem' }}>
                  📊 View Full Report
                </Link>
              </div>
            ))}
          </div>

          {progress.category_trends && progress.category_trends.length > 0 && (
            <div className="category-trends-row">
              {progress.category_trends.map((cat, idx) => (
                <div key={idx} className="category-delta-box">
                  <span className="cat-name">{cat.category_name}</span>
                  <span className="cat-scores">{cat.initial_score}% ➔ {cat.latest_score}%</span>
                  <span className={`cat-delta ${cat.delta >= 0 ? 'pos' : 'neg'}`}>
                    {cat.delta >= 0 ? `+${cat.delta}%` : `${cat.delta}%`}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {/* Interviews Section */}
      <section className="interviews-section">
        <div className="section-header">
          <div>
            <h2 className="section-title">Interview History & Sessions</h2>
            <p className="section-subtitle">Manage your active and completed mock interviews</p>
          </div>
          <button
            onClick={fetchDashboardData}
            className="btn btn-secondary btn-sm"
            disabled={isLoading}
            title="Refresh list"
          >
            🔄 Refresh
          </button>
        </div>

        {isLoading ? (
          <div className="card-box text-center py-5">
            <LoadingSpinner size="medium" message="Loading your interview sessions..." />
          </div>
        ) : interviews.length === 0 ? (
          <div className="empty-state-card">
            <div className="empty-icon">📁</div>
            <h3>No Mock Interviews Found</h3>
            <p>You haven't initiated any interview sessions yet. Start your first session by choosing a company or general mock interview.</p>
            <Link to="/setup" className="btn btn-primary btn-md" style={{ marginTop: '1rem' }}>
              Create Your First Interview
            </Link>
          </div>
        ) : (
          <div className="interviews-grid">
            {interviews.map((item) => (
              <InterviewCard key={item.id} interview={item} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
