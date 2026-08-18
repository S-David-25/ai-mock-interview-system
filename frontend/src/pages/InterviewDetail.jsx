import React, { useState, useEffect, useRef } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { interviewService } from '../services/interviewService';
import { getStatusInfo, formatDate } from '../utils/formatters';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { Alert } from '../components/Alert';
import { FileUploader } from '../components/FileUploader';

export function InterviewDetail() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [interview, setInterview] = useState(null);
  const [statusData, setStatusData] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // Resume processing UI state
  const [processingMessage, setProcessingMessage] = useState('');
  const [processingActive, setProcessingActive] = useState(false);
  const [resumeValidation, setResumeValidation] = useState(null);
  const [jdValidation, setJdValidation] = useState(null);
  const [parsedProfile, setParsedProfile] = useState(null);
  const [atsAnalysis, setAtsAnalysis] = useState(null);
  const [reuploadLoading, setReuploadLoading] = useState(false);
  const progressIntervalRef = useRef(null);

  const fetchDetails = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [intData, statData] = await Promise.all([
        interviewService.getInterviewById(id),
        interviewService.getInterviewStatus(id),
      ]);
      setInterview(intData);
      setStatusData(statData);

      // If persisted analysis exists, surface it
      if (intData && intData.resume_analysis) {
        setParsedProfile(intData.resume_analysis);
      } else {
        setParsedProfile(null);
      }
      if (intData && intData.resume_analysis && intData.resume_analysis.validation) {
        setResumeValidation(intData.resume_analysis.validation);
      }
      if (intData && intData.jd_analysis && intData.jd_analysis.validation) {
        setJdValidation(intData.jd_analysis.validation);
      }
      if (intData && intData.ats_analysis) {
        setAtsAnalysis(intData.ats_analysis);
      } else {
        setAtsAnalysis(null);
      }
    } catch (err) {
      setError(err.message || 'Failed to load interview session details');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDetails();
  }, [id]);

  // Auto-trigger document processing if resume is uploaded but not yet analyzed
  useEffect(() => {
    if (!isLoading && interview && interview.is_resume_uploaded && !interview.resume_analysis && !processingActive) {
      // kick off processing automatically so user sees parsing result
      runProcessDocuments();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoading, interview]);

  const runProcessDocuments = async () => {
    setError(null);
    setProcessingActive(true);
    setParsedProfile(null);
    setResumeValidation(null);

    // simple UI progression while the single API call runs
    const steps = ['Extracting Resume...', 'Validating Resume...', 'Parsing Resume...'];
    let idx = 0;
    setProcessingMessage(steps[idx]);
    progressIntervalRef.current = setInterval(() => {
      idx = (idx + 1) % steps.length;
      setProcessingMessage(steps[idx]);
    }, 900);

    try {
      const resp = await interviewService.processDocuments(id);
      // resp is expected to contain resume_validation and resume_analysis per backend
      if (resp && resp.resume_validation) {
        setResumeValidation(resp.resume_validation);
      }
      if (resp && resp.resume_analysis) {
        setParsedProfile(resp.resume_analysis);
      }
      if (resp && resp.jd_validation) {
        setJdValidation(resp.jd_validation);
      }
      if (resp && resp.ats_analysis) {
        setAtsAnalysis(resp.ats_analysis);
      }

      // refresh persisted interview details
      await fetchDetails();

    } catch (err) {
      setError(err.message || 'Failed to process documents.');
    } finally {
      // stop progress UI
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
        progressIntervalRef.current = null;
      }
      setProcessingMessage('');
      setProcessingActive(false);
    }
  };

  const handleLaunchSession = async () => {
    setIsProcessing(true);
    setError(null);
    try {
      // 1. Ensure documents processed (server will validate)
      if (!interview.resume_analysis) {
        await runProcessDocuments();
      }
      // If validation failed, prevent proceeding
      if (resumeValidation && !resumeValidation.is_valid) {
        setError('Resume validation failed. Please upload a valid resume before launching the interview.');
        setIsProcessing(false);
        return;
      }

      // 2. Generate questions if needed
      await interviewService.generateQuestions(id);
      // 3. Start interview
      await interviewService.startInterview(id);
      // 4. Navigate to interactive interview session page
      navigate(`/interviews/${id}/session`);
    } catch (err) {
      setError(err.message || 'Failed to initialize AI Voice Interview session.');
      setIsProcessing(false);
    }
  };

  if (isLoading) {
    return (
      <div className="page-container py-5 text-center">
        <LoadingSpinner size="large" message="Loading interview details..." />
      </div>
    );
  }

  if (error && !interview) {
    return (
      <div className="page-container py-4">
        <Alert type="error" message={error || 'Interview session not found'} />
        <Link to="/dashboard" className="btn btn-secondary mt-3">
          ← Back to Dashboard
        </Link>
      </div>
    );
  }

  const isCompany = interview.interview_type === 'company';
  const statusInfo = getStatusInfo(interview.status);

  return (
    <div className="detail-container">
      <div className="detail-header-card">
        <div className="detail-header-top">
          <Link to="/dashboard" className="back-link">
            ← Back to Dashboard
          </Link>
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

        <h1 className="detail-title">
          {isCompany ? `${interview.company_name} — ${interview.job_role}` : 'General Placement Mock Interview'}
        </h1>
        <p className="detail-meta">
          Session #{interview.id} • Created on {formatDate(interview.created_at)} • Type: {isCompany ? 'Company Specific' : 'General'}
        </p>
      </div>

      <Alert type="error" message={error} onDismiss={() => setError(null)} />

      <div className="detail-grid">
        {/* Document Status Card */}
        <div className="detail-card">
          <h2 className="detail-card-title">📁 Document Verification</h2>
          <div className="doc-check-list">
            <div className="doc-check-item">
              <div className="doc-check-icon">{interview.is_resume_uploaded ? '✅' : '❌'}</div>
              <div className="doc-check-info">
                <strong>Candidate Resume</strong>
                <span>{interview.resume_original_name || (interview.is_resume_uploaded ? 'Uploaded' : 'Pending upload')}</span>
              </div>
            </div>

            {isCompany && (
              <div className="doc-check-item">
                <div className="doc-check-icon">{interview.is_jd_uploaded ? '✅' : '❌'}</div>
                <div className="doc-check-info">
                  <strong>Job Description (JD)</strong>
                  <span>{interview.jd_original_name || (interview.is_jd_uploaded ? 'Uploaded' : 'Pending upload')}</span>
                </div>
              </div>
            )}
          </div>

          <div className="status-callout" style={{ marginTop: '1.5rem' }}>
            <strong>Session Status:</strong> {statusData?.message || 'Ready for AI interview phase.'}
          </div>
        </div>

        {/* JD Validation & ATS Card (Company interviews) */}
        {isCompany && (
          <div className="detail-card">
            <h2 className="detail-card-title">📋 Job Description Validation</h2>
            {!interview.is_jd_uploaded && !jdValidation && (
              <p style={{ color: '#64748b' }}>No Job Description provided yet. Paste the JD or upload a PDF/DOCX in the setup page.</p>
            )}
            {jdValidation && !jdValidation.is_valid && (
              <div className="validation-error-box">
                <strong>❌ Invalid Job Description</strong>
                <p style={{ marginTop: '0.5rem' }}>{jdValidation.reasons?.join('; ')}</p>
                <p style={{ fontSize: '0.95rem', color: '#64748b' }}>
                  Document type: {jdValidation.document_type || 'unknown'} • Confidence: {jdValidation.confidence ?? 'N/A'}
                </p>
                <div style={{ marginTop: '0.75rem' }}>
                  <FileUploader
                    title="Upload Another JD"
                    description="Upload a valid Job Description (PDF or DOCX) or go back to Setup to paste JD text."
                    selectedFile={null}
                    onFileSelected={async (f) => {
                      setReuploadLoading(true);
                      try {
                        await interviewService.uploadJD(id, f);
                        await runProcessDocuments();
                      } catch (err) {
                        setError(err.message || 'Failed to upload JD');
                      } finally {
                        setReuploadLoading(false);
                      }
                    }}
                    isLoading={reuploadLoading}
                  />
                </div>
              </div>
            )}
            {jdValidation && jdValidation.is_valid && (
              <div className="validation-success-box">
                <strong>✅ Job Description Validated</strong>
                <p style={{ marginTop: '0.5rem', color: '#475569' }}>Document Type: Job Description • Confidence: {jdValidation.confidence}</p>
              </div>
            )}
          </div>
        )}

        {/* AI Voice Interview Readiness Card */}
        <div className="detail-card">
          <h2 className="detail-card-title">🤖 AI Interview Coach</h2>
          <p style={{ color: '#64748b', fontSize: '0.95rem', lineHeight: '1.5' }}>
            This session is configured with your uploaded documents. The AI Voice Engine will ask questions using Text-to-Speech (TTS), record your spoken responses, analyze speech fluency and technical correctness, and generate adaptive dynamic follow-ups.
          </p>

          <div className="action-box" style={{ marginTop: '1.5rem' }}>
            {/* Resume processing UI */}
            {processingActive ? (
              <div style={{ marginBottom: '1rem' }}>
                <LoadingSpinner size="small" message={processingMessage || 'Processing resume...'} />
                <div style={{ marginTop: '0.5rem', color: '#475569' }}>{processingMessage}</div>
              </div>
            ) : resumeValidation && !resumeValidation.is_valid ? (
              <div className="validation-error-box">
                <strong>❌ Invalid Resume</strong>
                <p style={{ marginTop: '0.5rem' }}>{resumeValidation.reasons?.join('; ')}</p>
                <p style={{ fontSize: '0.95rem', color: '#64748b' }}>
                  Document type: {resumeValidation.document_type || 'unknown'} • Confidence: {resumeValidation.confidence ?? 'N/A'}
                </p>
                <div style={{ marginTop: '0.75rem' }}>
                  <FileUploader
                    title="Upload Another Resume"
                    description="Upload a valid resume (PDF or DOCX)."
                    selectedFile={null}
                    onFileSelected={async (f) => {
                      setReuploadLoading(true);
                      try {
                        await interviewService.uploadResume(id, f);
                        // trigger processing again
                        await runProcessDocuments();
                      } catch (err) {
                        setError(err.message || 'Failed to upload resume');
                      } finally {
                        setReuploadLoading(false);
                      }
                    }}
                    isLoading={reuploadLoading}
                  />
                </div>
              </div>
            ) : parsedProfile ? (
              <div className="validation-success-box">
                <strong>✅ Resume Parsed Successfully</strong>
                <p style={{ marginTop: '0.5rem', color: '#475569' }}>Parsed resume is shown below. Data is persisted and will remain after refresh.</p>
              </div>
            ) : (
              <div style={{ marginBottom: '1rem' }}>
                <button
                  className="btn btn-outline"
                  onClick={runProcessDocuments}
                  disabled={processingActive || !interview.is_resume_uploaded}
                >
                  {processingActive ? 'Processing...' : 'Process Uploaded Documents'}
                </button>
              </div>
            )}

            <button
              className="btn btn-primary btn-block btn-lg shadow-glow"
              disabled={!statusData?.is_ready || isProcessing || (resumeValidation && !resumeValidation.is_valid) || (jdValidation && !jdValidation.is_valid)}
              onClick={handleLaunchSession}
            >
              {isProcessing ? (
                <LoadingSpinner size="small" message="Preparing Questions & AI Engine..." />
              ) : statusData?.is_ready ? (
                '🎙️ Launch AI Voice Interview Session ➔'
              ) : (
                '⚠️ Upload Required Documents First'
              )}
            </button>
          </div>
        </div>
        {/* ATS Analysis Card (Company only) */}
        {isCompany && atsAnalysis && (
          <div className="detail-card" style={{ gridColumn: '1 / -1' }}>
            <h2 className="detail-card-title">📊 ATS Resume Match</h2>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
              <div style={{ fontSize: '2.25rem', fontWeight: 700 }}>{atsAnalysis.ats_score} / 100</div>
              <div>
                <div style={{ fontWeight: 700 }}>{atsAnalysis.score_label}</div>
                <div style={{ color: '#64748b', fontSize: '0.95rem' }}>Resume → Job Description</div>
              </div>
            </div>

            <div style={{ marginTop: '1rem' }}>
              <strong>Matched Skills:</strong>
              <div style={{ marginTop: '0.5rem' }}>{(atsAnalysis.matched_skills && atsAnalysis.matched_skills.length) ? atsAnalysis.matched_skills.join(', ') : '—'}</div>
            </div>

            <div style={{ marginTop: '0.75rem' }}>
              <strong>Missing Skills:</strong>
              <div style={{ marginTop: '0.5rem', color: '#b45309' }}>{(atsAnalysis.missing_skills && atsAnalysis.missing_skills.length) ? atsAnalysis.missing_skills.join(', ') : '—'}</div>
            </div>

            <div style={{ marginTop: '0.75rem' }}>
              <strong>Keyword Coverage:</strong> {atsAnalysis.keyword_coverage}%
            </div>

            <div style={{ marginTop: '0.5rem' }}>
              <strong>Experience Match:</strong> {atsAnalysis.experience_match}%
            </div>
            <div style={{ marginTop: '0.5rem' }}>
              <strong>Education Match:</strong> {atsAnalysis.education_match}%
            </div>

            {atsAnalysis.recommendations && atsAnalysis.recommendations.length > 0 && (
              <div style={{ marginTop: '1rem' }}>
                <strong>Recommendations</strong>
                <ul>
                  {atsAnalysis.recommendations.map((r, idx) => <li key={idx}>{r}</li>)}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* Parsed Resume Display Card */}
        {parsedProfile && (
          <div className="detail-card" style={{ gridColumn: '1 / -1' }}>
            <h2 className="detail-card-title">📄 Resume Parsed Successfully</h2>
            <div className="parsed-resume-grid">
              {parsedProfile.candidate_name ? (
                <div className="parsed-field"><strong>Candidate:</strong> {parsedProfile.candidate_name}</div>
              ) : null}

              {parsedProfile.contact_information && (
                <div className="parsed-field">
                  <strong>Contact:</strong>
                  <div>
                    {parsedProfile.contact_information.email && parsedProfile.contact_information.email.length > 0 && (
                      <div>Email: {parsedProfile.contact_information.email.join(', ')}</div>
                    )}
                    {parsedProfile.contact_information.phone && parsedProfile.contact_information.phone.length > 0 && (
                      <div>Phone: {parsedProfile.contact_information.phone.join(', ')}</div>
                    )}
                    {parsedProfile.contact_information.links && parsedProfile.contact_information.links.length > 0 && (
                      <div>Links: {parsedProfile.contact_information.links.join(', ')}</div>
                    )}
                  </div>
                </div>
              )}

              {parsedProfile.technical_skills && parsedProfile.technical_skills.length > 0 && (
                <div className="parsed-field"><strong>Technical Skills:</strong> {parsedProfile.technical_skills.join(', ')}</div>
              )}

              {parsedProfile.programming_languages && parsedProfile.programming_languages.length > 0 && (
                <div className="parsed-field"><strong>Programming Languages:</strong> {parsedProfile.programming_languages.join(', ')}</div>
              )}

              {parsedProfile.frameworks && parsedProfile.frameworks.length > 0 && (
                <div className="parsed-field"><strong>Frameworks:</strong> {parsedProfile.frameworks.join(', ')}</div>
              )}

              {parsedProfile.databases && parsedProfile.databases.length > 0 && (
                <div className="parsed-field"><strong>Databases:</strong> {parsedProfile.databases.join(', ')}</div>
              )}

              {parsedProfile.tools && parsedProfile.tools.length > 0 && (
                <div className="parsed-field"><strong>Tools:</strong> {parsedProfile.tools.join(', ')}</div>
              )}

              {parsedProfile.projects && parsedProfile.projects.length > 0 && (
                <div className="parsed-field parsed-projects">
                  <strong>Projects:</strong>
                  <ul>
                    {parsedProfile.projects.map((p, idx) => (
                      <li key={idx}>
                        {p.name && <div style={{ fontWeight: 600 }}>{p.name}</div>}
                        {p.description && <div style={{ marginTop: '0.25rem' }}>{p.description}</div>}
                        {p.technologies && p.technologies.length > 0 && (
                          <div style={{ marginTop: '0.25rem', fontStyle: 'italic' }}>Technologies: {p.technologies.join(', ')}</div>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {parsedProfile.education && parsedProfile.education.length > 0 && (
                <div className="parsed-field"><strong>Education:</strong> {parsedProfile.education.join('; ')}</div>
              )}

              {parsedProfile.experience && parsedProfile.experience.length > 0 && (
                <div className="parsed-field parsed-experience">
                  <strong>Experience:</strong>
                  <ul>
                    {parsedProfile.experience.map((e, i) => (
                      <li key={i}>
                        <div style={{ fontWeight: 600 }}>{e.company || ''} {e.role ? `— ${e.role}` : ''}</div>
                        {e.duration && <div style={{ fontSize: '0.95rem', color: '#64748b' }}>{e.duration}</div>}
                        {e.responsibilities && e.responsibilities.length > 0 && (
                          <ul>
                            {e.responsibilities.map((r, ri) => <li key={ri}>{r}</li>)}
                          </ul>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {parsedProfile.internships && parsedProfile.internships.length > 0 && (
                <div className="parsed-field"><strong>Internships:</strong> {parsedProfile.internships.map(i => i.text || JSON.stringify(i)).join('; ')}</div>
              )}

              {parsedProfile.certifications && parsedProfile.certifications.length > 0 && (
                <div className="parsed-field"><strong>Certifications:</strong> {parsedProfile.certifications.join(', ')}</div>
              )}

              {parsedProfile.achievements && parsedProfile.achievements.length > 0 && (
                <div className="parsed-field"><strong>Achievements:</strong> {parsedProfile.achievements.join('; ')}</div>
              )}

              {parsedProfile.soft_skills && parsedProfile.soft_skills.length > 0 && (
                <div className="parsed-field"><strong>Soft Skills:</strong> {parsedProfile.soft_skills.join(', ')}</div>
              )}
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
