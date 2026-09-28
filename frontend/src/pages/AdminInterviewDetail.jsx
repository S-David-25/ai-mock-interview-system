import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Alert } from '../components/Alert';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { adminService } from '../services/adminService';

export function AdminInterviewDetail() {
  const { interviewId } = useParams();
  const [detail, setDetail] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    async function load() {
      setIsLoading(true);
      setError('');
      try {
        const [interviewData, questionData] = await Promise.all([
          adminService.getInterviewDetail(interviewId),
          adminService.getInterviewQuestions(interviewId),
        ]);
        setDetail(interviewData);
        setQuestions(questionData.items || []);
      } catch (err) {
        setError(err.message || 'Interview details unavailable.');
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, [interviewId]);

  if (isLoading) return <div className="dashboard-container"><div className="card-box text-center py-5"><LoadingSpinner size="medium" message="Loading interview report..." /></div></div>;
  if (!detail) return <div className="dashboard-container"><Alert type="error" message={error || 'Interview not found.'} /></div>;

  const interview = detail.interview;

  return (
    <div className="dashboard-container">
      <section className="welcome-banner">
        <div className="welcome-content">
          <h1 className="welcome-title">Interview Performance</h1>
          <p className="welcome-subtitle">Read-only review of scored interview data.</p>
        </div>
        <div className="welcome-actions">
          <Link to="/admin/dashboard" className="btn btn-secondary">Back to Dashboard</Link>
        </div>
      </section>

      <section className="card-box" style={{ marginTop: '1rem' }}>
        <h2 className="section-title">Session Overview</h2>
        <div className="stats-grid">
          <div className="stat-card"><span className="stat-title">Date: </span><strong className="stat-value">{new Date(interview.created_at).toLocaleDateString()}</strong></div>
          <div className="stat-card"><span className="stat-title">Type: </span><strong className="stat-value">{interview.interview_type}</strong></div>
          <div className="stat-card"><span className="stat-title">Company: </span><strong className="stat-value">{interview.company_name || 'General'}</strong></div>
          <div className="stat-card"><span className="stat-title">Role: </span><strong className="stat-value">{interview.job_role || 'N/A'}</strong></div>
          <div className="stat-card"><span className="stat-title">Overall Score: </span><strong className="stat-value">{interview.overall_score ?? 0}%</strong></div>
          <div className="stat-card"><span className="stat-title">Questions: </span><strong className="stat-value">{detail.question_count}</strong></div>
        </div>
      </section>

      <section className="card-box" style={{ marginTop: '1.5rem' }}>
        <h2 className="section-title">Question Breakdown</h2>
        {questions.length ? (
          questions.map((question, index) => (
            <div key={question.id || index} style={{ border: '1px solid #e2e8f0', borderRadius: '12px', padding: '1rem', marginTop: '1rem' }}>
              <h3>Question {index + 1}</h3>
              <p><strong>Question:</strong> {question.question_text}</p>
              <p><strong>Candidate Response:</strong> {question.transcript_text || 'No transcript saved.'}</p>
              <p><strong>Technical Score:</strong> {question.technical_score ?? 0}%</p>
              <p><strong>Communication:</strong> {question.communication_score ?? 0}%</p>
              <p><strong>Fluency:</strong> {question.fluency_score ?? 0}%</p>
            </div>
          ))
        ) : (
          <p>No evaluated questions found for this session.</p>
        )}
      </section>
    </div>
  );
}
