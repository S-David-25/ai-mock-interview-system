import React from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

const tooltipStyle = {
  background: 'var(--bg-surface)',
  borderColor: 'var(--border-color)',
  color: 'var(--text-primary)',
};

function ChartEmptyState({ loading }) {
  return <p className="chart-empty-state">{loading ? 'Loading analytics...' : 'No interview data available yet.'}</p>;
}

export function AdminDashboardCharts({ analytics, analyticsLoading, progressionData, selectedCandidateId, onCandidateChange }) {
  const hasInterviewData = Boolean(analytics?.score_progression?.length);

  return (
    <section className="admin-chart-grid" aria-label="Admin interview analytics">
      <article className="card-box admin-chart-card">
        <h2 className="section-title">Score Distribution</h2>
        <p className="section-subtitle">Completed interview scores by range.</p>
        {hasInterviewData ? (
          <div className="admin-chart-canvas" role="img" aria-label="Bar chart showing candidate score distribution">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={analytics.score_distribution} margin={{ top: 16, right: 8, left: -18, bottom: 0 }}>
                <CartesianGrid stroke="var(--border-color)" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="range" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} axisLine={{ stroke: 'var(--border-color)' }} tickLine={false} />
                <YAxis allowDecimals={false} tick={{ fill: 'var(--text-muted)', fontSize: 12 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: 'var(--text-primary)' }} itemStyle={{ color: 'var(--text-primary)' }} />
                <Bar dataKey="count" name="Interviews" fill="var(--primary)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : <ChartEmptyState loading={analyticsLoading} />}
      </article>

      <article className="card-box admin-chart-card">
        <h2 className="section-title">Interview Activity</h2>
        <p className="section-subtitle">Completed interviews by date.</p>
        {analytics?.interview_activity?.length ? (
          <div className="admin-chart-canvas" role="img" aria-label="Bar chart showing completed interviews by date">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={analytics.interview_activity} margin={{ top: 16, right: 8, left: -18, bottom: 28 }}>
                <CartesianGrid stroke="var(--border-color)" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="date" tickFormatter={(date) => date.slice(5)} interval="preserveStartEnd" angle={-25} textAnchor="end" height={48} tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} axisLine={{ stroke: 'var(--border-color)' }} tickLine={false} />
                <YAxis allowDecimals={false} tick={{ fill: 'var(--text-muted)', fontSize: 12 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: 'var(--text-primary)' }} itemStyle={{ color: 'var(--text-primary)' }} />
                <Bar dataKey="completed_interviews" name="Completed interviews" fill="var(--primary)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : <ChartEmptyState loading={analyticsLoading} />}
      </article>

      <article className="card-box admin-chart-card">
        <div className="admin-chart-heading">
          <div>
            <h2 className="section-title">Candidate Score Progression</h2>
            <p className="section-subtitle">Overall score across completed interviews.</p>
          </div>
          <label className="admin-chart-filter">
            <span>Candidate</span>
            <select value={selectedCandidateId} onChange={(event) => onCandidateChange(event.target.value)}>
              <option value="">All candidates</option>
              {(analytics?.candidates ?? []).map((candidate) => (
                <option key={candidate.id} value={String(candidate.id)}>{candidate.name}</option>
              ))}
            </select>
          </label>
        </div>
        {progressionData.length ? (
          <div className="admin-chart-canvas" role="img" aria-label="Line chart showing candidate score progression">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={progressionData} margin={{ top: 16, right: 12, left: -18, bottom: 0 }}>
                <CartesianGrid stroke="var(--border-color)" strokeDasharray="3 3" />
                <XAxis dataKey="label" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} axisLine={{ stroke: 'var(--border-color)' }} tickLine={false} />
                <YAxis domain={[0, 100]} tick={{ fill: 'var(--text-muted)', fontSize: 12 }} axisLine={false} tickLine={false} />
                <Tooltip formatter={(score) => [`${score}%`, 'Score']} contentStyle={tooltipStyle} labelStyle={{ color: 'var(--text-primary)' }} itemStyle={{ color: 'var(--text-primary)' }} />
                <Line type="monotone" dataKey="score" name="Score" stroke="var(--primary)" strokeWidth={2.5} dot={{ r: 4, fill: 'var(--primary)' }} activeDot={{ r: 6 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : <ChartEmptyState loading={analyticsLoading} />}
      </article>

      <article className="card-box admin-chart-card">
        <h2 className="section-title">Average Performance by Evaluation Dimension</h2>
        <p className="section-subtitle">Average stored scores from completed interviews.</p>
        {hasInterviewData ? (
          <div className="admin-chart-canvas" role="img" aria-label="Bar chart showing average evaluation dimension scores">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={analytics.category_performance} layout="vertical" margin={{ top: 8, right: 14, left: 4, bottom: 0 }}>
                <CartesianGrid stroke="var(--border-color)" strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" domain={[0, 100]} tick={{ fill: 'var(--text-muted)', fontSize: 12 }} axisLine={{ stroke: 'var(--border-color)' }} tickLine={false} />
                <YAxis type="category" dataKey="dimension" width={102} tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip formatter={(score) => [`${score}%`, 'Average score']} contentStyle={tooltipStyle} labelStyle={{ color: 'var(--text-primary)' }} itemStyle={{ color: 'var(--text-primary)' }} />
                <Bar dataKey="score" name="Average score" fill="var(--primary)" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : <ChartEmptyState loading={analyticsLoading} />}
      </article>
    </section>
  );
}