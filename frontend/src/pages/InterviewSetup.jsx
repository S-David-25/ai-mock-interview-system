import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { interviewService } from '../services/interviewService';
import { FileUploader } from '../components/FileUploader';
import { Alert } from '../components/Alert';
import { LoadingSpinner } from '../components/LoadingSpinner';

export function InterviewSetup() {
  const navigate = useNavigate();

  // State
  const [interviewType, setInterviewType] = useState('company'); // 'company' or 'general'
  const [durationMinutes, setDurationMinutes] = useState(30);
  const [companyName, setCompanyName] = useState('');
  const [jobRole, setJobRole] = useState('');
  const [resumeFile, setResumeFile] = useState(null);
  const [jdFile, setJdFile] = useState(null);
  const [jdText, setJdText] = useState('');

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [uploadProgressMsg, setUploadProgressMsg] = useState('');
  const [error, setError] = useState('');

  const handleCreateAndUpload = async (e) => {
    e.preventDefault();
    setError('');

    // Form Validations
    if (interviewType === 'company') {
      if (!companyName.trim()) {
        setError('Please enter the target company name (e.g. Google, TCS, Amazon).');
        return;
      }
      if (!jobRole.trim()) {
        setError('Please enter the target job role (e.g. Frontend Developer, SDE 1).');
        return;
      }
      const hasJdText = Boolean(jdText && jdText.trim());
      const hasJdFile = Boolean(jdFile);
      if (!hasJdText && !hasJdFile) {
        setError('Please provide a Job Description by pasting text or uploading a PDF/DOCX file.');
        return;
      }
      if (!resumeFile) {
        setError('Please upload your Resume (PDF or DOCX).');
        return;
      }
    } else {
      if (!resumeFile) {
        setError('Please upload your Resume (PDF or DOCX) for General Mock Interview.');
        return;
      }
    }

    setIsSubmitting(true);
    try {
      setUploadProgressMsg('Step 1/3: Initializing interview session in database...');
      const interview = await interviewService.createInterview({
        interview_type: interviewType,
        company_name: companyName.trim(),
        job_role: jobRole.trim(),
        duration_minutes: durationMinutes,
      });

      const interviewId = interview.id;

      if (interviewType === 'company') {
        const hasJdText = Boolean(jdText && jdText.trim());
        const hasJdFile = Boolean(jdFile);

        if (hasJdText && hasJdFile) {
          setUploadProgressMsg('Step 2/4: Saving pasted Job Description and uploading JD file...');
          await interviewService.submitJDText(interviewId, jdText.trim());
          await interviewService.uploadJD(interviewId, jdFile);
        } else if (hasJdText) {
          setUploadProgressMsg('Step 2/4: Saving pasted Job Description...');
          await interviewService.submitJDText(interviewId, jdText.trim());
        } else if (hasJdFile) {
          setUploadProgressMsg('Step 2/4: Uploading & extracting text from Job Description...');
          await interviewService.uploadJD(interviewId, jdFile);
        }
      }

      setUploadProgressMsg('Step 3/4: Uploading & extracting text from Candidate Resume...');
      await interviewService.uploadResume(interviewId, resumeFile);

      setUploadProgressMsg('Step 4/4: Finalizing session...');

      setUploadProgressMsg('Completed! Redirecting to interview workspace...');
      setTimeout(() => {
        navigate(`/interviews/${interviewId}`);
      }, 500);

    } catch (err) {
      setError(err.message || 'An error occurred during interview setup. Please try again.');
      setIsSubmitting(false);
      setUploadProgressMsg('');
    }
  };

  return (
    <div className="setup-container">
      <div className="setup-header">
        <span className="setup-badge">Step 1: Configuration</span>
        <h1 className="setup-title">Setup New Mock Interview</h1>
        <p className="setup-subtitle">
          Configure your interview parameters and provide required documentation to tailor the AI questions.
        </p>
      </div>

      <Alert type="error" message={error} onDismiss={() => setError('')} />

      <form onSubmit={handleCreateAndUpload} className="setup-form">
        {/* Step 1: Choose Interview Type */}
        <div className="form-section">
          <label className="section-label">Choose Interview Type</label>
          <div className="interview-type-selector">
            <div
              className={`type-option-card ${interviewType === 'company' ? 'selected' : ''}`}
              onClick={() => !isSubmitting && setInterviewType('company')}
            >
              <div className="type-card-radio">
                <input
                  type="radio"
                  name="interview_type"
                  checked={interviewType === 'company'}
                  onChange={() => setInterviewType('company')}
                  disabled={isSubmitting}
                />
              </div>
              <div className="type-card-content">
                <div className="type-card-icon">🏢</div>
                <h3 className="type-card-title">Company Mock Interview</h3>
                <p className="type-card-desc">
                  Tailored to a specific hiring company and job description. Aligns questions with target role requirements, tech stack, and evaluation criteria.
                </p>
                <div className="type-card-tags">
                  <span className="pill">Requires Company & Role</span>
                  <span className="pill">Requires JD + Resume</span>
                </div>
              </div>
            </div>

            <div
              className={`type-option-card ${interviewType === 'general' ? 'selected' : ''}`}
              onClick={() => !isSubmitting && setInterviewType('general')}
            >
              <div className="type-card-radio">
                <input
                  type="radio"
                  name="interview_type"
                  checked={interviewType === 'general'}
                  onChange={() => setInterviewType('general')}
                  disabled={isSubmitting}
                />
              </div>
              <div className="type-card-content">
                <div className="type-card-icon">🌐</div>
                <h3 className="type-card-title">General Mock Interview</h3>
                <p className="type-card-desc">
                  Comprehensive assessment across standard placement topics: core Computer Science, problem-solving, behavioral competencies, and resume projects.
                </p>
                <div className="type-card-tags">
                  <span className="pill">Quick Start</span>
                  <span className="pill">Requires Resume only</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Step: Choose Interview Duration */}
        <div className="form-section">
          <label className="section-label">Choose Interview Duration</label>
          <div className="duration-selector-grid">
            {[
              { val: 1, label: '1 min', desc: '1 minute — TESTING' },
              { val: 20, label: '20 mins', desc: '20 minutes' },
              { val: 30, label: '30 mins', desc: '30 minutes (Standard)' },
              { val: 45, label: '45 mins', desc: '45 minutes' },
              { val: 60, label: '60 mins', desc: '60 minutes' },
              { val: 90, label: '90 mins', desc: '90 minutes' },
            ].map(opt => (
              <div
                key={opt.val}
                className={`duration-card ${durationMinutes === opt.val ? 'selected' : ''}`}
                onClick={() => !isSubmitting && setDurationMinutes(opt.val)}
              >
                <div className="duration-card-radio">
                  <input
                    type="radio"
                    name="duration_minutes"
                    checked={durationMinutes === opt.val}
                    onChange={() => setDurationMinutes(opt.val)}
                    disabled={isSubmitting}
                  />
                </div>
                <div className="duration-card-content">
                  <span className="duration-tag">{opt.label}</span>
                  <span className="duration-name">{opt.desc}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Step 2: Target Info (Company Specific) */}
        {interviewType === 'company' && (
          <div className="form-section company-fields-box">
            <h3 className="sub-section-title">Company & Target Role Details</h3>
            <div className="form-grid-2">
              <div className="form-group">
                <label htmlFor="companyName">Target Company Name *</label>
                <input
                  id="companyName"
                  type="text"
                  placeholder="e.g. Google, Amazon, Microsoft, Infosys"
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  disabled={isSubmitting}
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="jobRole">Job Role / Designation *</label>
                <input
                  id="jobRole"
                  type="text"
                  placeholder="e.g. Software Development Engineer (SDE 1)"
                  value={jobRole}
                  onChange={(e) => setJobRole(e.target.value)}
                  disabled={isSubmitting}
                  required
                />
              </div>
            </div>

            <div style={{ marginTop: '1.25rem' }}>
              <label className="section-label">Job Description (Paste or Upload)</label>
              <textarea
                placeholder="Paste the full Job Description text here (preferred)"
                rows={8}
                value={jdText}
                onChange={(e) => setJdText(e.target.value)}
                disabled={isSubmitting}
                style={{ width: '100%', padding: '0.75rem', borderRadius: '6px', border: '1px solid #e2e8f0', marginBottom: '0.75rem' }}
              />
              <div style={{ marginTop: '0.5rem' }}>
                <FileUploader
                  title="Or upload Job Description (PDF/DOCX)"
                  description="Upload the official job post or description in PDF or DOCX format (Max 10MB)"
                  selectedFile={jdFile}
                  onFileSelected={setJdFile}
                  isLoading={isSubmitting}
                />
              </div>
            </div>
          </div>
        )}

        {/* Step 3: Resume Upload (Common) */}
        <div className="form-section">
          <FileUploader
            title="Upload Candidate Resume *"
            description="Upload your latest resume in PDF or DOCX format (Max 10MB)"
            selectedFile={resumeFile}
            onFileSelected={setResumeFile}
            isLoading={isSubmitting}
          />
        </div>

        {/* Progress & Submit */}
        {isSubmitting && uploadProgressMsg && (
          <div className="submission-progress-box">
            <LoadingSpinner size="small" message={uploadProgressMsg} />
          </div>
        )}

        <div className="form-actions-row">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => navigate('/dashboard')}
            disabled={isSubmitting}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="btn btn-primary btn-lg shadow-glow"
            disabled={isSubmitting}
          >
            {isSubmitting ? 'Processing Session...' : 'Create Session & Upload Documents 🚀'}
          </button>
        </div>
      </form>
    </div>
  );
}
