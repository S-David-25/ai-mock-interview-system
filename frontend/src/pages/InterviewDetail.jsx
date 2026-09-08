import React, { useState, useEffect, useRef } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { interviewService } from '../services/interviewService';
import { getStatusInfo, formatDate } from '../utils/formatters';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { Alert } from '../components/Alert';
import { FileUploader } from '../components/FileUploader';

// Safe helper to render strings, arrays, or objects without throwing .join() / .map() TypeErrors
function renderListOrString(val, separator = ', ') {
  if (val === null || val === undefined) return null;
  if (Array.isArray(val)) {
    return val
      .map(item => (typeof item === 'object' && item !== null ? (item.name || item.title || item.text || JSON.stringify(item)) : String(item)))
      .filter(Boolean)
      .join(separator);
  }
  if (typeof val === 'object') {
    return val.name || val.title || val.text || JSON.stringify(val);
  }
  return String(val);
}

export function InterviewDetail() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [interview, setInterview] = useState(null);
  const [statusData, setStatusData] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [error, setError] = useState(null);

  // Resume / JD processing UI state
  const [processingMessage, setProcessingMessage] = useState('');
  const [processingActive, setProcessingActive] = useState(false);
  const [resumeValidation, setResumeValidation] = useState(null);
  const [jdValidation, setJdValidation] = useState(null);
  const [parsedProfile, setParsedProfile] = useState(null);
  const [atsAnalysis, setAtsAnalysis] = useState(null);
  const [reuploadLoading, setReuploadLoading] = useState(false);
  const progressIntervalRef = useRef(null);

  const fetchDetails = async (silent = false) => {
    if (!silent) setIsInitialLoading(true);
    setError(null);
    try {
      const [intData, statData] = await Promise.all([
        interviewService.getInterviewById(id),
        interviewService.getInterviewStatus(id),
      ]);
      setInterview(intData);
      setStatusData(statData);

      // If persisted analysis exists, surface it safely
      if (intData && intData.resume_analysis) {
        setParsedProfile(intData.resume_analysis);
      }
      if (intData && intData.resume_analysis && intData.resume_analysis.validation) {
        setResumeValidation(intData.resume_analysis.validation);
      }
      if (intData && intData.jd_analysis && intData.jd_analysis.validation) {
        setJdValidation(intData.jd_analysis.validation);
      }
      if (intData && intData.ats_analysis) {
        setAtsAnalysis(intData.ats_analysis);
      }
    } catch (err) {
      setError(err.message || 'Failed to load interview session details');
    } finally {
      if (!silent) setIsInitialLoading(false);
    }
  };

  useEffect(() => {
    fetchDetails();
  }, [id]);

  // Auto-trigger document processing if resume is uploaded but not yet analyzed
  useEffect(() => {
    if (
      !isInitialLoading &&
      interview &&
      interview.is_resume_uploaded &&
      !interview.resume_analysis &&
      !processingActive
    ) {
      runProcessDocuments();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isInitialLoading, interview]);

  const runProcessDocuments = async () => {
    setError(null);
    setProcessingActive(true);

    const steps = [
      'Extracting Resume & JD text...',
      'Validating documents & checking heuristics...',
      'Parsing skills, technologies & projects with AI...',
      'Computing ATS Match & Role Alignment Score...'
    ];
    let idx = 0;
    setProcessingMessage(steps[idx]);
    if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
    progressIntervalRef.current = setInterval(() => {
      idx = (idx + 1) % steps.length;
      setProcessingMessage(steps[idx]);
    }, 1200);

    try {
      const resp = await interviewService.processDocuments(id);
      if (resp) {
        if (resp.resume_validation) setResumeValidation(resp.resume_validation);
        if (resp.resume_analysis) setParsedProfile(resp.resume_analysis);
        if (resp.jd_validation) setJdValidation(resp.jd_validation);
        if (resp.ats_analysis) setAtsAnalysis(resp.ats_analysis);
      }

      // refresh persisted interview details silently without page unmounting
      await fetchDetails(true);
    } catch (err) {
      setError(err.message || 'Failed to process uploaded documents.');
    } finally {
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
        progressIntervalRef.current = null;
      }
      setProcessingMessage('');
      setProcessingActive(false);
    }
  };

  const handleLaunchSession = async () => {
    if (isProcessing) return;
    setIsProcessing(true);
    setError(null);
    try {
      // 1. Ensure documents are processed if needed
      if (!interview?.resume_analysis) {
        await runProcessDocuments();
      }
      if (resumeValidation && !resumeValidation.is_valid) {
        setError('Resume validation failed. Please upload a valid resume before launching the interview.');
        setIsProcessing(false);
        return;
      }
      if (jdValidation && !jdValidation.is_valid) {
        setError('Job Description validation failed. Please upload a valid Job Description.');
        setIsProcessing(false);
        return;
      }

      // 2. Pre-generate or retrieve Question 1 before navigating
      const qResp = await interviewService.getQuestions(id);
      if (!qResp.questions || qResp.questions.length === 0) {
        await interviewService.generateQuestions(id);
      }

      // 3. Start interview session if needed
      if (interview?.status !== 'in_progress' && interview?.status !== 'completed') {
        await interviewService.startInterview(id);
      }

      // 4. Navigate directly to interactive interview session page
      navigate(`/interviews/${id}/session`);
    } catch (err) {
      setError(err.message || 'Failed to initialize AI Voice Interview session.');
      setIsProcessing(false);
    }
  };

  if (isInitialLoading) {
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
        <div style={{ marginTop: '1.5rem', display: 'flex', gap: '1rem' }}>
          <button onClick={() => fetchDetails()} className="btn btn-primary">
            🔄 Retry
          </button>
          <Link to="/dashboard" className="btn btn-secondary">
            ← Back to Dashboard
          </Link>
        </div>
      </div>
    );
  }

  const isCompany = interview?.interview_type === 'company';
  const statusInfo = getStatusInfo(interview?.status || 'setup');

  return (
    <div className="detail-container">
      {/* Header */}
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
          {isCompany
            ? `${interview?.company_name || 'Target Company'} — ${interview?.job_role || 'Target Role'}`
            : 'General Placement Mock Interview'}
        </h1>
        <p className="detail-meta">
          Session #{interview?.id} • Created on {formatDate(interview?.created_at)} • Type: {isCompany ? 'Company Specific' : 'General Placement'}
        </p>
      </div>

      <Alert type="error" message={error} onDismiss={() => setError(null)} />

      <div className="detail-grid">
        {/* Document Verification Card */}
        <div className="detail-card">
          <h2 className="detail-card-title">📁 Document Verification</h2>
          <div className="doc-check-list">
            <div className="doc-check-item">
              <div className="doc-check-icon">{interview?.is_resume_uploaded ? '✅' : '❌'}</div>
              <div className="doc-check-info">
                <strong>Candidate Resume</strong>
                <span>{interview?.resume_original_name || (interview?.is_resume_uploaded ? 'Uploaded' : 'Pending upload')}</span>
              </div>
            </div>

            {isCompany && (
              <div className="doc-check-item">
                <div className="doc-check-icon">{interview?.is_jd_uploaded ? '✅' : '❌'}</div>
                <div className="doc-check-info">
                  <strong>Job Description (JD)</strong>
                  <span>{interview?.jd_original_name || (interview?.is_jd_uploaded ? 'Uploaded' : 'Pending upload')}</span>
                </div>
              </div>
            )}
          </div>

          <div className="status-callout" style={{ marginTop: '1.5rem' }}>
            <strong>Session Status:</strong> {statusData?.message || (statusData?.is_ready ? 'Ready for AI interview phase.' : 'Document upload/processing in progress.')}
          </div>
        </div>

        {/* JD Validation Card (Company interviews) */}
        {isCompany && (
          <div className="detail-card">
            <h2 className="detail-card-title">📋 Job Description Validation</h2>
            {!interview?.is_jd_uploaded && !jdValidation && (
              <p style={{ color: '#64748b' }}>No Job Description provided yet. Paste the JD or upload a PDF/DOCX in the setup page.</p>
            )}

            {jdValidation && !jdValidation.is_valid && (
              <div className="validation-error-box">
                <strong>❌ Invalid Job Description</strong>
                <p style={{ marginTop: '0.5rem' }}>{renderListOrString(jdValidation.reasons, '; ')}</p>
                <p style={{ fontSize: '0.95rem', color: '#64748b' }}>
                  Document type: {jdValidation.document_type || 'unknown'} • Confidence: {jdValidation.confidence ?? 'N/A'}
                </p>
                <div style={{ marginTop: '0.75rem' }}>
                  <FileUploader
                    title="Upload Another JD"
                    description="Upload a valid Job Description (PDF or DOCX)."
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
                <p style={{ marginTop: '0.5rem', color: '#475569' }}>
                  Document Type: Job Description • Confidence: {jdValidation.confidence ?? 'High'}
                </p>
              </div>
            )}

            {!jdValidation && interview?.is_jd_uploaded && (
              <div className="validation-success-box">
                <strong>📄 Job Description Uploaded</strong>
                <p style={{ marginTop: '0.5rem', color: '#475569' }}>
                  {interview?.jd_original_name || 'Job Description file'} ready for analysis.
                </p>
              </div>
            )}
          </div>
        )}

        {/* AI Voice Interview Coach & Launch Card */}
        <div className="detail-card">
          <h2 className="detail-card-title">🤖 AI Interview Coach</h2>
          <p style={{ color: '#64748b', fontSize: '0.95rem', lineHeight: '1.5' }}>
            This session uses dynamic Gemini question generation. The AI interviewer will ask personalized questions based on your resume and JD, analyze your speech correctness and fluency, and ask adaptive follow-ups in real time.
          </p>

          <div className="action-box" style={{ marginTop: '1.5rem' }}>
            {interview?.status === 'completed' ? (
              <div className="completed-session-box" style={{ textAlign: 'center', padding: '1rem 0' }}>
                <div style={{ color: '#16a34a', fontWeight: 600, fontSize: '1.1rem', marginBottom: '0.75rem' }}>
                  ✅ This interview session is completed.
                </div>
                <p style={{ color: '#64748b', fontSize: '0.95rem', marginBottom: '1.25rem' }}>
                  All multi-modal evaluations are finalized.
                </p>
                <Link to={`/interviews/${id}/report`} className="btn btn-primary btn-block btn-lg shadow-glow">
                  📊 View Full Performance Report ➔
                </Link>
              </div>
            ) : (
              <>
                {/* Document processing state banner */}
                {processingActive ? (
                  <div style={{ marginBottom: '1rem', background: '#f8fafc', padding: '1rem', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                    <LoadingSpinner size="small" message={processingMessage || 'Analyzing documents...'} />
                    <div style={{ marginTop: '0.5rem', color: '#334155', fontSize: '0.9rem', fontWeight: 500 }}>
                      {processingMessage}
                    </div>
                  </div>
                ) : resumeValidation && !resumeValidation.is_valid ? (
                  <div className="validation-error-box">
                    <strong>❌ Invalid Resume</strong>
                    <p style={{ marginTop: '0.5rem' }}>{renderListOrString(resumeValidation.reasons, '; ')}</p>
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
                  <div className="validation-success-box" style={{ marginBottom: '1rem' }}>
                    <strong>✅ Resume Parsed Successfully</strong>
                    <p style={{ marginTop: '0.5rem', color: '#475569' }}>
                      Candidate profile and skills extracted. Ready to start interview.
                    </p>
                  </div>
                ) : (
                  <div style={{ marginBottom: '1rem' }}>
                    <button
                      className="btn btn-outline"
                      onClick={runProcessDocuments}
                      disabled={processingActive || !interview?.is_resume_uploaded}
                    >
                      {processingActive ? 'Processing...' : '⚡ Process Uploaded Documents'}
                    </button>
                  </div>
                )}

                {/* Launch Button */}
                <button
                  className="btn btn-primary btn-block btn-lg shadow-glow"
                  disabled={
                    !statusData?.is_ready ||
                    isProcessing ||
                    processingActive ||
                    (resumeValidation && !resumeValidation.is_valid) ||
                    (jdValidation && !jdValidation.is_valid)
                  }
                  onClick={handleLaunchSession}
                >
                  {isProcessing ? (
                    <LoadingSpinner size="small" message="Preparing Questions & AI Engine..." />
                  ) : processingActive ? (
                    '⏳ Processing Documents...'
                  ) : interview?.status === 'in_progress' ? (
                    '🎙️ Resume AI Voice Interview Session ➔'
                  ) : statusData?.is_ready ? (
                    '🎙️ Launch AI Voice Interview Session ➔'
                  ) : (
                    '⚠️ Upload & Process Required Documents First'
                  )}
                </button>
              </>
            )}
          </div>
        </div>

        {/* ATS Analysis Card (Company only) */}
        {isCompany && (
          <div className="detail-card" style={{ gridColumn: '1 / -1' }}>
            <h2 className="detail-card-title">📊 ATS Resume Match</h2>
            {processingActive && !atsAnalysis ? (
              <div style={{ padding: '1.5rem 0', textAlign: 'center' }}>
                <LoadingSpinner size="small" message="Calculating ATS match against Job Description..." />
              </div>
            ) : atsAnalysis ? (
              <>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem', flexWrap: 'wrap' }}>
                  <div style={{ fontSize: '2.5rem', fontWeight: 800, color: atsAnalysis.ats_score >= 70 ? '#16a34a' : atsAnalysis.ats_score >= 50 ? '#d97706' : '#dc2626' }}>
                    {atsAnalysis.ats_score ?? 0} / 100
                  </div>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: '1.2rem' }}>{atsAnalysis.score_label || 'Match Score'}</div>
                    <div style={{ color: '#64748b', fontSize: '0.95rem' }}>Resume ➔ Job Description Compatibility</div>
                  </div>
                </div>

                <div style={{ marginTop: '1.25rem' }}>
                  <strong>Matched Skills:</strong>
                  <div style={{ marginTop: '0.5rem', color: '#16a34a', fontWeight: 500 }}>
                    {renderListOrString(atsAnalysis.matched_skills) || '—'}
                  </div>
                </div>

                <div style={{ marginTop: '0.75rem' }}>
                  <strong>Missing Skills:</strong>
                  <div style={{ marginTop: '0.5rem', color: '#b45309', fontWeight: 500 }}>
                    {renderListOrString(atsAnalysis.missing_skills) || '—'}
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', marginTop: '1.25rem' }}>
                  <div style={{ background: '#f8fafc', padding: '0.75rem', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                    <div style={{ fontSize: '0.85rem', color: '#64748b' }}>Keyword Coverage</div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 700, marginTop: '0.25rem' }}>{atsAnalysis.keyword_coverage ?? 0}%</div>
                  </div>
                  <div style={{ background: '#f8fafc', padding: '0.75rem', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                    <div style={{ fontSize: '0.85rem', color: '#64748b' }}>Experience Match</div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 700, marginTop: '0.25rem' }}>{atsAnalysis.experience_match ?? 0}%</div>
                  </div>
                  <div style={{ background: '#f8fafc', padding: '0.75rem', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                    <div style={{ fontSize: '0.85rem', color: '#64748b' }}>Education Match</div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 700, marginTop: '0.25rem' }}>{atsAnalysis.education_match ?? 0}%</div>
                  </div>
                  <div style={{ background: '#f8fafc', padding: '0.75rem', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                    <div style={{ fontSize: '0.85rem', color: '#64748b' }}>Role Alignment</div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 700, marginTop: '0.25rem' }}>{atsAnalysis.role_alignment ?? 0}%</div>
                  </div>
                </div>

                {Array.isArray(atsAnalysis.recommendations) && atsAnalysis.recommendations.length > 0 && (
                  <div style={{ marginTop: '1.25rem' }}>
                    <strong>ATS Recommendations:</strong>
                    <ul style={{ marginTop: '0.5rem', paddingLeft: '1.25rem' }}>
                      {atsAnalysis.recommendations.map((r, idx) => (
                        <li key={idx} style={{ marginTop: '0.25rem', color: '#334155' }}>
                          {typeof r === 'string' ? r : JSON.stringify(r)}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            ) : (
              <p style={{ color: '#64748b', marginTop: '0.5rem' }}>
                {interview?.is_jd_uploaded
                  ? 'ATS calculation will appear once documents are processed.'
                  : 'Upload a Job Description to calculate ATS match.'}
              </p>
            )}
          </div>
        )}

        {/* Parsed Resume Display Card */}
        {parsedProfile && (
          <div className="detail-card" style={{ gridColumn: '1 / -1' }}>
            <h2 className="detail-card-title">📄 Candidate Profile & Extracted Resume</h2>
            <div className="parsed-resume-grid">
              {parsedProfile.candidate_name && (
                <div className="parsed-field">
                  <strong>Candidate Name:</strong> {parsedProfile.candidate_name}
                </div>
              )}

              {parsedProfile.contact_information && (
                <div className="parsed-field">
                  <strong>Contact Information:</strong>
                  <div style={{ marginTop: '0.25rem' }}>
                    {parsedProfile.contact_information.email && (
                      <div>Email: {renderListOrString(parsedProfile.contact_information.email)}</div>
                    )}
                    {parsedProfile.contact_information.phone && (
                      <div>Phone: {renderListOrString(parsedProfile.contact_information.phone)}</div>
                    )}
                    {parsedProfile.contact_information.links && (
                      <div>Links: {renderListOrString(parsedProfile.contact_information.links)}</div>
                    )}
                  </div>
                </div>
              )}

              {parsedProfile.technical_skills && (
                <div className="parsed-field">
                  <strong>Technical Skills:</strong> {renderListOrString(parsedProfile.technical_skills)}
                </div>
              )}

              {parsedProfile.programming_languages && (
                <div className="parsed-field">
                  <strong>Programming Languages:</strong> {renderListOrString(parsedProfile.programming_languages)}
                </div>
              )}

              {parsedProfile.frameworks && (
                <div className="parsed-field">
                  <strong>Frameworks & Libraries:</strong> {renderListOrString(parsedProfile.frameworks)}
                </div>
              )}

              {parsedProfile.databases && (
                <div className="parsed-field">
                  <strong>Databases:</strong> {renderListOrString(parsedProfile.databases)}
                </div>
              )}

              {parsedProfile.tools && (
                <div className="parsed-field">
                  <strong>Tools & Platforms:</strong> {renderListOrString(parsedProfile.tools)}
                </div>
              )}

              {Array.isArray(parsedProfile.projects) && parsedProfile.projects.length > 0 && (
                <div className="parsed-field parsed-projects">
                  <strong>Projects:</strong>
                  <ul>
                    {parsedProfile.projects.map((p, idx) => (
                      <li key={idx} style={{ marginTop: '0.5rem' }}>
                        {p.name && <div style={{ fontWeight: 600 }}>{p.name}</div>}
                        {p.description && <div style={{ marginTop: '0.25rem' }}>{p.description}</div>}
                        {p.technologies && (
                          <div style={{ marginTop: '0.25rem', fontStyle: 'italic', color: '#475569' }}>
                            Technologies: {renderListOrString(p.technologies)}
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {parsedProfile.education && (
                <div className="parsed-field">
                  <strong>Education:</strong> {renderListOrString(parsedProfile.education, '; ')}
                </div>
              )}

              {Array.isArray(parsedProfile.experience) && parsedProfile.experience.length > 0 && (
                <div className="parsed-field parsed-experience">
                  <strong>Experience:</strong>
                  <ul>
                    {parsedProfile.experience.map((e, i) => (
                      <li key={i} style={{ marginTop: '0.5rem' }}>
                        <div style={{ fontWeight: 600 }}>
                          {e.company || ''} {e.role ? `— ${e.role}` : ''}
                        </div>
                        {e.duration && <div style={{ fontSize: '0.95rem', color: '#64748b' }}>{e.duration}</div>}
                        {e.responsibilities && (
                          <div style={{ marginTop: '0.25rem' }}>
                            {renderListOrString(e.responsibilities, ' • ')}
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {parsedProfile.certifications && (
                <div className="parsed-field">
                  <strong>Certifications:</strong> {renderListOrString(parsedProfile.certifications)}
                </div>
              )}

              {parsedProfile.achievements && (
                <div className="parsed-field">
                  <strong>Achievements:</strong> {renderListOrString(parsedProfile.achievements)}
                </div>
              )}

              {parsedProfile.soft_skills && (
                <div className="parsed-field">
                  <strong>Soft Skills:</strong> {renderListOrString(parsedProfile.soft_skills)}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
