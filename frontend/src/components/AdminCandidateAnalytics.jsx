import React, { useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

const dimensions = [
  { label: 'Technical', key: 'technical_score' },
  { label: 'Communication', key: 'communication_score' },
  { label: 'Fluency', key: 'fluency_score' },
  { label: 'Eye Contact', key: 'eye_contact_score' },
  { label: 'Posture', key: 'posture_score' },
  { label: 'Expression', key: 'expression_score' },
];

const tooltipStyle = {
  background: 'var(--bg-surface)',
  borderColor: 'var(--border-color)',
  color: 'var(--text-primary)',
};

const hasScore = (value) => value !== null && value !== undefined && Number.isFinite(Number(value));

function EmptyChart({ children = 'No completed interviews yet.' }) {
  return <p className="chart-empty-state">{children}</p>;
}

export function AdminCandidateAnalytics({ interviews }) {
  const scoredInterviews = interviews.filter((item) => hasScore(item.overall_score));
  const progression = scoredInterviews.map((item) => ({
    label: `Interview ${item.interview_number}`,
    interview_number: item.interview_number,
    date: item.date,
    score: Number(item.overall_score),
  }));
  const comparison = interviews.map((item) => ({
    label: `Interview ${item.interview_number}`,
    overall_score: hasScore(item.overall_score) ? Number(item.overall_score) : null,
    technical_score: hasScore(item.technical_score) ? Number(item.technical_score) : null,
    communication_score: hasScore(item.communication_score) ? Number(item.communication_score) : null,
    fluency_score: hasScore(item.fluency_score) ? Number(item.fluency_score) : null,
  }));
  const dimensionAverages = dimensions.map(({ label, key }) => {
    const values = interviews.filter((item) => hasScore(item[key])).map((item) => Number(item[key]));
    return values.length ? { dimension: label, score: values.reduce((sum, value) => sum + value, 0) / values.length } : null;
  }).filter(Boolean);
  const latestInterview = interviews.length ? interviews[interviews.length - 1] : null;
  const latestDimensions = [
    { dimension: 'Overall', key: 'overall_score' },
    ...dimensions.map(({ label, key }) => ({ dimension: label, key })),
  ].filter(({ key }) => hasScore(latestInterview?.[key]))
    .map(({ dimension, key }) => ({ dimension, score: Number(latestInterview[key]) }));
  const initialQuestionInterviewId = interviews.length
    ? String(interviews[interviews.length - 1].interview_id)
    : '';
  const [selectedQuestionInterviewId, setSelectedQuestionInterviewId] = useState(initialQuestionInterviewId);
  const selectedQuestionInterview = interviews.find((item) => String(item.interview_id) === selectedQuestionInterviewId);
  const questionData = (selectedQuestionInterview?.question_scores || []).map((item) => ({
    label: `Question ${item.order_num}`,
    technical_score: hasScore(item.technical_score) ? Number(item.technical_score) : null,
    communication_score: hasScore(item.communication_score) ? Number(item.communication_score) : null,
    fluency_score: hasScore(item.fluency_score) ? Number(item.fluency_score) : null,
  }));
  const firstInterview = interviews.length ? interviews[0] : null;
  const lastInterview = interviews.length ? interviews[interviews.length - 1] : null;
  const scoreChange = hasScore(firstInterview?.overall_score) && hasScore(lastInterview?.overall_score)
    ? Number((Number(lastInterview.overall_score) - Number(firstInterview.overall_score)).toFixed(1))
    : null;

  return (
    <section className="admin-analytics-section candidate-analytics-section" aria-label="Candidate performance analytics">
      <div className="section-header">
        <div>
          <h2 className="section-title">Performance Analytics</h2>
          <p className="section-subtitle">Read-only analysis of completed interview evaluations.</p>
        </div>
      </div>

      <div className="admin-chart-grid">
        <article className="card-box admin-chart-card">
          <h3 className="section-title">Performance Progression</h3>
          {progression.length ? (
            <>
              <div className="admin-chart-canvas" role="img" aria-label="Line chart of candidate overall interview scores">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={progression} margin={{ top: 16, right: 12, left: -18, bottom: 0 }}>
                    <CartesianGrid stroke="var(--border-color)" strokeDasharray="3 3" />
                    <XAxis dataKey="label" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} axisLine={{ stroke: 'var(--border-color)' }} tickLine={false} />
                    <YAxis domain={[0, 100]} tick={{ fill: 'var(--text-muted)', fontSize: 12 }} axisLine={false} tickLine={false} />
                    <Tooltip formatter={(score) => [`${score}%`, 'Overall score']} labelFormatter={(label, payload) => payload?.[0]?.payload?.date ? `${label} · ${payload[0].payload.date}` : label} contentStyle={tooltipStyle} labelStyle={{ color: 'var(--text-primary)' }} itemStyle={{ color: 'var(--text-primary)' }} />
                    <Line type="monotone" dataKey="score" name="Overall score" stroke="var(--primary)" strokeWidth={2.5} dot={{ r: 4, fill: 'var(--primary)' }} activeDot={{ r: 6 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              {interviews.length === 1 && progression.length === 1 && <p className="section-subtitle">Complete more interviews to see your performance progression.</p>}
            </>
          ) : <EmptyChart />}
        </article>

        <article className="card-box admin-chart-card">
          <h3 className="section-title">Performance Dimension Breakdown</h3>
          <p className="section-subtitle">Average stored scores across completed interviews.</p>
          {dimensionAverages.length ? (
            <div className="admin-chart-canvas" role="img" aria-label="Bar chart of candidate performance dimensions">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={dimensionAverages} layout="vertical" margin={{ top: 8, right: 14, left: 4, bottom: 0 }}>
                  <CartesianGrid stroke="var(--border-color)" strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" domain={[0, 100]} tick={{ fill: 'var(--text-muted)', fontSize: 12 }} axisLine={{ stroke: 'var(--border-color)' }} tickLine={false} />
                  <YAxis type="category" dataKey="dimension" width={106} tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip formatter={(score) => [`${Number(score).toFixed(1)}%`, 'Average score']} contentStyle={tooltipStyle} labelStyle={{ color: 'var(--text-primary)' }} itemStyle={{ color: 'var(--text-primary)' }} />
                  <Bar dataKey="score" name="Average score" fill="var(--primary)" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : <EmptyChart>Performance dimension data is not available.</EmptyChart>}
        </article>

        <article className="card-box admin-chart-card">
          <h3 className="section-title">Interview-by-Interview Comparison</h3>
          {comparison.length ? (
            <div className="admin-chart-scroll">
            <div className="admin-chart-canvas" style={{ minWidth: `${Math.max(520, comparison.length * 72)}px` }} role="img" aria-label="Grouped bar chart comparing candidate interviews">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={comparison} margin={{ top: 16, right: 8, left: -18, bottom: 0 }}>
                  <CartesianGrid stroke="var(--border-color)" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="label" interval="preserveStartEnd" tick={{ fill: 'var(--text-secondary)', fontSize: 10 }} axisLine={{ stroke: 'var(--border-color)' }} tickLine={false} />
                  <YAxis domain={[0, 100]} tick={{ fill: 'var(--text-muted)', fontSize: 12 }} axisLine={false} tickLine={false} />
                  <Tooltip formatter={(score) => [`${score}%`, 'Score']} contentStyle={tooltipStyle} labelStyle={{ color: 'var(--text-primary)' }} itemStyle={{ color: 'var(--text-primary)' }} />
                  <Legend wrapperStyle={{ color: 'var(--text-primary)' }} />
                  <Bar dataKey="overall_score" name="Overall" fill="var(--primary)" />
                  <Bar dataKey="technical_score" name="Technical" fill="#16a34a" />
                  <Bar dataKey="communication_score" name="Communication" fill="#d97706" />
                  <Bar dataKey="fluency_score" name="Fluency" fill="#0891b2" />
                </BarChart>
              </ResponsiveContainer>
            </div>
            </div>
          ) : <EmptyChart />}
        </article>

        <article className="card-box admin-chart-card">
          <div className="admin-chart-heading">
            <h3 className="section-title">Question Performance</h3>
            {interviews.length > 1 && (
              <label className="admin-chart-filter">
                <span>Interview</span>
                <select value={selectedQuestionInterviewId} onChange={(event) => setSelectedQuestionInterviewId(event.target.value)}>
                  {interviews.slice().reverse().map((item) => (
                    <option key={item.interview_id} value={String(item.interview_id)}>Interview {item.interview_number}</option>
                  ))}
                </select>
              </label>
            )}
          </div>
          {questionData.length ? (
            <div className="admin-chart-scroll">
            <div className="admin-chart-canvas" style={{ minWidth: `${Math.max(520, questionData.length * 72)}px` }} role="img" aria-label="Grouped bar chart showing question evaluation scores">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={questionData} margin={{ top: 16, right: 8, left: -18, bottom: 0 }}>
                  <CartesianGrid stroke="var(--border-color)" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="label" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} axisLine={{ stroke: 'var(--border-color)' }} tickLine={false} />
                  <YAxis domain={[0, 100]} tick={{ fill: 'var(--text-muted)', fontSize: 12 }} axisLine={false} tickLine={false} />
                  <Tooltip formatter={(score) => [`${score}%`, 'Score']} contentStyle={tooltipStyle} labelStyle={{ color: 'var(--text-primary)' }} itemStyle={{ color: 'var(--text-primary)' }} />
                  <Legend wrapperStyle={{ color: 'var(--text-primary)' }} />
                  <Bar dataKey="technical_score" name="Technical" fill="var(--primary)" />
                  <Bar dataKey="communication_score" name="Communication" fill="#16a34a" />
                  <Bar dataKey="fluency_score" name="Fluency" fill="#d97706" />
                </BarChart>
              </ResponsiveContainer>
            </div>
            </div>
          ) : <EmptyChart>Question-level scoring is not available for this interview.</EmptyChart>}
        </article>

        <article className="card-box admin-chart-card">
          <h3 className="section-title">Latest Interview Overview</h3>
          {latestDimensions.length ? (
            <div className="admin-chart-canvas" role="img" aria-label="Bar chart of the latest completed interview scores">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={latestDimensions} layout="vertical" margin={{ top: 8, right: 14, left: 4, bottom: 0 }}>
                  <CartesianGrid stroke="var(--border-color)" strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" domain={[0, 100]} tick={{ fill: 'var(--text-muted)', fontSize: 12 }} axisLine={{ stroke: 'var(--border-color)' }} tickLine={false} />
                  <YAxis type="category" dataKey="dimension" width={106} tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip formatter={(score) => [`${score}%`, 'Score']} contentStyle={tooltipStyle} labelStyle={{ color: 'var(--text-primary)' }} itemStyle={{ color: 'var(--text-primary)' }} />
                  <Bar dataKey="score" name="Score" fill="var(--primary)" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : <EmptyChart>Performance data is not available for the latest interview.</EmptyChart>}
        </article>

        <article className="card-box admin-chart-card performance-change-card">
          <h3 className="section-title">Performance Change</h3>
          <div className="performance-change-values">
            <div><span>First interview</span><strong>{hasScore(firstInterview?.overall_score) ? `${firstInterview.overall_score}%` : 'N/A'}</strong></div>
            <div><span>Latest interview</span><strong>{hasScore(lastInterview?.overall_score) ? `${lastInterview.overall_score}%` : 'N/A'}</strong></div>
            <div><span>Change</span><strong>{scoreChange === null ? 'N/A' : scoredInterviews.length < 2 ? 'No previous interview' : `${scoreChange > 0 ? '+' : ''}${scoreChange} percentage points`}</strong></div>
          </div>
        </article>
      </div>
    </section>
  );
}