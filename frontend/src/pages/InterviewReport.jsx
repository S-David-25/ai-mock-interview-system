import React, { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { interviewService } from '../services/interviewService';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { Alert } from '../components/Alert';
import { formatDate, formatScore } from '../utils/formatters';

export function InterviewReport() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [report, setReport] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('overview'); // overview, questions, roadmap

  useEffect(() => {
    async function loadReport() {
      setIsLoading(true);
      setError(null);
      try {
        const data = await interviewService.getReport(id);
        setReport(data);
      } catch (err) {
        setError(err.message || 'Failed to load performance report.');
      } finally {
        setIsLoading(false);
      }
    }
    loadReport();
  }, [id]);

  if (isLoading) {
    return (
      <div className="page-container py-5 text-center">
        <LoadingSpinner size="large" message="Generating comprehensive multi-modal performance report..." />
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="page-container py-4">
        <Alert type="error" message={error || 'Performance report not found.'} />
        <Link to="/dashboard" className="btn btn-secondary mt-3">
          ← Back to Dashboard
        </Link>
      </div>
    );
  }

  const isCompany = report.interview_type === 'company';
  const sb = report.score_breakdown;
  const dims = sb?.dimensions || {};

  return (
    <div className="report-container">
      {/* Report Header Card */}
      <div className="report-header-card">
        <div className="report-header-top">
          <Link to="/dashboard" className="back-link">
            ← Back to Dashboard
          </Link>
          <div className="header-actions-row">
            <Link to={`/interviews/compare?second_id=${id}`} className="btn btn-outline btn-sm">
              📊 Compare With Previous
            </Link>
            <button onClick={() => window.print()} className="btn btn-secondary btn-sm">
              🖨️ Print / Save PDF
            </button>
          </div>
        </div>

        <div className="report-title-row">
          <div>
            <span className="report-badge">Official Assessment</span>
            <h1 className="report-main-title">
              {isCompany ? `${report.company_name} — ${report.job_role}` : 'General Placement Mock Interview'}
            </h1>
            <p className="report-meta-text">
              Candidate Performance Evaluation • Session #{report.interview_id} • Evaluated via Weighted Multi-Modal Scoring Algorithm
            </p>
          </div>

          <div className="overall-score-display">
            <span className="score-number">{report.overall_score}</span>
            <span className="score-max">/ 100</span>
            <div className="readiness-badge-main">{report.readiness_level}</div>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="report-tabs-bar">
          <button
            className={`report-tab-btn ${activeTab === 'overview' ? 'active' : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            📊 Performance Overview
          </button>
          <button
            className={`report-tab-btn ${activeTab === 'questions' ? 'active' : ''}`}
            onClick={() => setActiveTab('questions')}
          >
            💬 Question Breakdown ({report.question_breakdowns?.length || 0})
          </button>
          <button
            className={`report-tab-btn ${activeTab === 'roadmap' ? 'active' : ''}`}
            onClick={() => setActiveTab('roadmap')}
          >
            🎯 5-Phase Roadmap ({report.roadmap?.phases?.length || 0} Phases)
          </button>
        </div>
      </div>

      <Alert type="error" message={error} onDismiss={() => setError(null)} />

      {/* TAB 1: OVERVIEW */}
      {activeTab === 'overview' && (
        <div className="report-tab-content">
          {/* Executive Summary */}
          <div className="report-section-card">
            <h2 className="section-heading">📝 Executive Summary</h2>
            <p className="summary-paragraph">{report.summary_text}</p>
          </div>

          {/* Transparent Scoring Contributions Table */}
          <div className="report-section-card">
            <h2 className="section-heading">⚖️ Transparent Multi-Modal Scoring Matrix</h2>
            <p className="section-subtext">
              The Weighted Multi-Modal Interview Scoring Algorithm mathematically normalizes independent speech, conceptual, and vision dimensions into a unified score.
            </p>

            <div className="table-responsive">
              <table className="scoring-table">
                <thead>
                  <tr>
                    <th>Evaluation Dimension</th>
                    <th>Measured Score</th>
                    <th>Standard Weight</th>
                    <th>Normalized Contribution</th>
                    <th>Modality Status & Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(dims).map(([key, d]) => (
                    <tr key={key} className={!d.is_available ? 'row-unavailable' : ''}>
                      <td><strong>{key.replace('_', ' ').toUpperCase()}</strong></td>
                      <td>
                        {d.is_available ? (
                          <span className="badge-score-pill">{d.raw_score}%</span>
                        ) : (
                          <span className="badge-unavailable">Unavailable</span>
                        )}
                      </td>
                      <td>{intPercent(d.weight)}%</td>
                      <td>
                        <strong>{d.is_available ? `+${d.contribution} pts` : '—'}</strong>
                      </td>
                      <td className="note-cell">{d.status_note || 'Measured successfully.'}</td>
                    </tr>
                  ))}
                  <tr className="table-summary-row">
                    <td><strong>FINAL OVERALL SCORE</strong></td>
                    <td colSpan="2"><strong>Sum of Available Weights: {intPercent(sb?.available_weights_sum || 1.0)}%</strong></td>
                    <td><strong>{report.overall_score} / 100</strong></td>
                    <td><strong>{report.readiness_level}</strong></td>
                  </tr>
                </tbody>
              </table>
            </div>

            {sb?.unavailable_modalities && sb.unavailable_modalities.length > 0 && (
              <div className="missing-modality-callout">
                ℹ️ <strong>Missing-Modality Normalization Active:</strong> {sb.unavailable_modalities.join(', ')} were unavailable in this testing session. The scoring algorithm dynamically normalized remaining weights to prevent unfair candidate penalty.
              </div>
            )}
          </div>

          {/* Strengths & Weaknesses Grid */}
          <div className="grid-2-col">
            <div className="report-section-card border-green">
              <h2 className="section-heading text-green">✅ Verified Strengths</h2>
              <ul className="strengths-list">
                {report.strengths.map((s, idx) => (
                  <li key={idx}><strong>✓</strong> {s}</li>
                ))}
              </ul>
            </div>

            <div className="report-section-card border-amber">
              <h2 className="section-heading text-amber">⚠️ Areas for Growth</h2>
              <ul className="weaknesses-list">
                {report.weaknesses.map((w, idx) => (
                  <li key={idx}><strong>⚠</strong> {w}</li>
                ))}
              </ul>
            </div>
          </div>

          {/* Frequently Observed Mistakes */}
          {report.frequently_observed_mistakes && report.frequently_observed_mistakes.length > 0 && (
            <div className="report-section-card">
              <h2 className="section-heading">🔍 Frequently Observed Mistakes</h2>
              <div className="mistakes-grid">
                {report.frequently_observed_mistakes.map((m, idx) => (
                  <div key={idx} className="mistake-card">
                    <div className="mistake-header">
                      <span className="mistake-title">{m.mistake_type}</span>
                      <span className={`severity-badge ${m.severity.toLowerCase()}`}>{m.severity} Severity</span>
                    </div>
                    <p className="mistake-desc">{m.description}</p>
                    <div className="mistake-remediation">
                      <strong>💡 Recommended Fix:</strong> {m.remediation_tip}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Resume & Job Description Match */}
          {isCompany && (
            <div className="report-section-card">
              <h2 className="section-heading">📋 Resume-to-Job Alignment Analysis</h2>
              <div className="jd-match-header">
                <span>Match Score: <strong>{report.match_percentage}%</strong></span>
                <div className="progress-bar-track">
                  <div className="progress-bar-fill" style={{ width: `${report.match_percentage}%` }}></div>
                </div>
              </div>

              <div className="grid-2-col" style={{ marginTop: '1rem' }}>
                <div>
                  <h4 style={{ fontSize: '0.9rem', marginBottom: '0.5rem', color: '#166534' }}>Matched Competencies:</h4>
                  <div className="tags-cluster">
                    {report.matched_skills && report.matched_skills.length > 0 ? (
                      report.matched_skills.map((s, idx) => <span key={idx} className="tag-matched">✓ {s}</span>)
                    ) : (
                      <span className="tag-neutral">Foundational Tech Stack</span>
                    )}
                  </div>
                </div>

                <div>
                  <h4 style={{ fontSize: '0.9rem', marginBottom: '0.5rem', color: '#b91c1c' }}>Identified Skill Gaps:</h4>
                  <div className="tags-cluster">
                    {report.skill_gaps && report.skill_gaps.length > 0 ? (
                      report.skill_gaps.map((s, idx) => <span key={idx} className="tag-gap">⚠ {s}</span>)
                    ) : (
                      <span className="tag-matched">No Critical Skill Gaps</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 2: QUESTIONS BREAKDOWN */}
      {activeTab === 'questions' && (
        <div className="report-tab-content">
          <div className="report-section-card">
            <h2 className="section-heading">💬 Detailed Question & Answer Analysis</h2>
            <p className="section-subtext">Review specific scores, candidate transcripts, and technical feedback for each interview question.</p>

            <div className="questions-review-list">
              {report.question_breakdowns.map((q, idx) => (
                <div key={idx} className="question-review-card">
                  <div className="question-review-header">
                    <span className="question-number-tag">Q{q.order_number}</span>
                    <span className="tag-category">{q.category}</span>
                    <span className={`tag-difficulty ${q.difficulty.toLowerCase()}`}>{q.difficulty}</span>
                    <div className="question-scores-badges">
                      <span className="badge-metric">Tech: {q.technical_score}%</span>
                      <span className="badge-metric">Comm: {q.communication_score}%</span>
                      <span className="badge-metric">Fluency: {q.fluency_score}%</span>
                    </div>
                  </div>

                  <h3 className="review-question-text">{q.question}</h3>

                  <div className="candidate-answer-box">
                    <strong>Spoken Response:</strong>
                    <p>"{q.candidate_answer}"</p>
                  </div>

                  <div className="assessor-feedback-box">
                    <strong>💡 AI Evaluation & Feedback:</strong>
                    <p>{q.feedback}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: PERSONALIZED ROADMAP */}
      {activeTab === 'roadmap' && (
        <div className="report-tab-content">
          <div className="report-section-card">
            <h2 className="section-heading">🎯 5-Phase Personalized Improvement Roadmap</h2>
            <p className="section-subtext">
              Actionable, measurable milestones tailored to close your identified skill gaps and elevate placement drive performance.
            </p>

            <div className="roadmap-timeline">
              {report.roadmap.phases.map((phase) => (
                <div key={phase.phase_number} className="roadmap-phase-card">
                  <div className="phase-header">
                    <span className="phase-pill">Phase {phase.phase_number}</span>
                    <h3 className="phase-title">{phase.phase_title}</h3>
                  </div>
                  <p className="phase-objective"><strong>Focus Objective:</strong> {phase.focus_objective}</p>

                  <div className="phase-items-list">
                    {phase.items.map((item, itemIdx) => (
                      <div key={itemIdx} className="roadmap-item-card">
                        <div className="item-header-row">
                          <h4 className="item-area">{item.area}</h4>
                          <span className={`priority-badge ${item.priority.toLowerCase()}`}>{item.priority} Priority</span>
                        </div>
                        <p><strong>Identified Gap:</strong> {item.problem}</p>
                        <p><strong>Recommended Action:</strong> {item.recommended_action}</p>
                        <div className="practice-task-box">
                          <strong>🛠️ Practice Task ({item.estimated_duration}):</strong> {item.practice_task}
                        </div>
                        <div className="measurable-target-box">
                          <strong>🎯 Target Milestone:</strong> {item.measurable_target}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Bottom Actions */}
      <div className="report-bottom-actions">
        <Link to="/setup" className="btn btn-primary btn-lg shadow-glow">
          ⚡ Practice Another Mock Interview
        </Link>
        <Link to="/dashboard" className="btn btn-secondary btn-lg">
          Return to Dashboard
        </Link>
      </div>
    </div>
  );
}

function intPercent(val) {
  return Math.round(Number(val) * 100);
}
