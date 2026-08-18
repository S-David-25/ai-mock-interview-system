import React from 'react';
import { Link } from 'react-router-dom';
import { formatDate, formatScore, getStatusInfo } from '../utils/formatters';

export function InterviewCard({ interview }) {
  const statusInfo = getStatusInfo(interview.status);
  const isCompany = interview.interview_type === 'company';

  let targetUrl = `/interviews/${interview.id}`;
  let actionLabel = '⚙️ Continue Setup';

  if (interview.status === 'completed') {
    targetUrl = `/interviews/${interview.id}/report`;
    actionLabel = '📊 View Performance Report';
  } else if (interview.status === 'ready' || interview.status === 'in_progress') {
    targetUrl = `/interviews/${interview.id}/session`;
    actionLabel = interview.status === 'ready' ? '🚀 Launch Voice Interview' : '🎙️ Resume Voice Interview';
  }

  return (
    <div className="interview-card">
      <div className="interview-card-header">
        <div className="interview-card-type">
          <span className={`badge-type ${isCompany ? 'badge-company' : 'badge-general'}`}>
            {isCompany ? '🏢 Company Mock' : '🌐 General Mock'}
          </span>
          <span
            className="badge-status"
            style={{
              backgroundColor: statusInfo.bg,
              color: statusInfo.color,
              borderColor: statusInfo.border
            }}
          >
            {statusInfo.label}
          </span>
        </div>
        <div className="interview-card-date">{formatDate(interview.created_at)}</div>
      </div>

      <div className="interview-card-body">
        <h3 className="interview-card-title">
          {isCompany ? (
            <>
              <span className="company-name">{interview.company_name}</span>
              <span className="role-title"> • {interview.job_role}</span>
            </>
          ) : (
            'Comprehensive Placement Mock Interview'
          )}
        </h3>

        <div className="interview-docs-indicators">
          <span className={`doc-indicator ${interview.is_resume_uploaded ? 'uploaded' : 'missing'}`}>
            📄 Resume: {interview.resume_original_name || (interview.is_resume_uploaded ? 'Uploaded' : 'Missing')}
          </span>
          {isCompany && (
            <span className={`doc-indicator ${interview.is_jd_uploaded ? 'uploaded' : 'missing'}`}>
              📋 JD: {interview.jd_original_name || (interview.is_jd_uploaded ? 'Uploaded' : 'Missing')}
            </span>
          )}
        </div>

        {interview.overall_score !== null && interview.overall_score !== undefined && (
          <div className="interview-score-box">
            <div className="score-main">
              <span className="score-label">Overall Evaluation:</span>
              <span className="score-value">{formatScore(interview.overall_score)}</span>
            </div>
            <div className="score-sub-metrics">
              {interview.technical_score !== null && (
                <span>Tech: {formatScore(interview.technical_score)}</span>
              )}
              {interview.communication_score !== null && (
                <span>Comm: {formatScore(interview.communication_score)}</span>
              )}
              {interview.facial_score !== null && (
                <span>Vision: {formatScore(interview.facial_score)}</span>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="interview-card-footer">
        <Link to={targetUrl} className="btn btn-outline btn-block">
          {actionLabel}
        </Link>
      </div>
    </div>
  );
}
