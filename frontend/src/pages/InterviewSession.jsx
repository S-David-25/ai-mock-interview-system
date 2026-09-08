import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { interviewService } from '../services/interviewService';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { Alert } from '../components/Alert';
import { formatDuration } from '../utils/formatters';

export function InterviewSession() {
  const { id } = useParams();
  const navigate = useNavigate();

  // State
  const [interview, setInterview] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [sessionCompleted, setSessionCompleted] = useState(false);
  const [timeLeft, setTimeLeft] = useState(null);

  // Audio Recording State
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [transcript, setTranscript] = useState('');
  const [isProcessingAnswer, setIsProcessingAnswer] = useState(false);
  const [lastFeedback, setLastFeedback] = useState(null);
  const [isFollowUpAlert, setIsFollowUpAlert] = useState(false);

  // TTS State
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [ttsSupported, setTtsSupported] = useState(true);

  // Webcam State
  const [cameraActive, setCameraActive] = useState(false);
  const [visionMetrics, setVisionMetrics] = useState(null);

  // Refs
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const recordingTimerRef = useRef(null);
  const videoRef = useRef(null);
  const videoStreamRef = useRef(null);
  const visionIntervalRef = useRef(null);
  const countdownIntervalRef = useRef(null);
  const isCompletingRef = useRef(false);

  const parseUtcExpiresAt = (expiresAtStr) => {
    if (!expiresAtStr) return null;
    const clean = String(expiresAtStr).trim().replace(' ', 'T') + (expiresAtStr.includes('Z') || expiresAtStr.includes('+') || (expiresAtStr.length > 10 && expiresAtStr.slice(10).includes('-')) ? '' : 'Z');
    const target = new Date(clean).getTime();
    if (isNaN(target)) return null;
    return target;
  };

  const handleExpireAndComplete = async () => {
    if (isCompletingRef.current) return;
    isCompletingRef.current = true;

    // 1. Cancel TTS
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      setIsSpeaking(false);
    }

    // 2. Stop audio recording
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      try {
        mediaRecorderRef.current.stop();
      } catch (e) {}
    }
    setIsRecording(false);
    if (recordingTimerRef.current) {
      clearInterval(recordingTimerRef.current);
      recordingTimerRef.current = null;
    }

    // 3. Stop camera
    stopCamera();

    // 4. Clear intervals
    if (countdownIntervalRef.current) {
      clearInterval(countdownIntervalRef.current);
      countdownIntervalRef.current = null;
    }
    if (visionIntervalRef.current) {
      clearInterval(visionIntervalRef.current);
      visionIntervalRef.current = null;
    }

    // 5. Complete session in backend
    try {
      await interviewService.completeInterview(id);
    } catch (e) {
      // Backend may already have expired it
    }

    // 6. Transition to completion UI
    setSessionCompleted(true);
  };

  // 1. Initialize Interview & Questions
  useEffect(() => {
    async function initSession() {
      setIsLoading(true);
      setError(null);
      try {
        let intData = await interviewService.getInterviewById(id);

        if (intData.status === 'setup') {
          navigate(`/interviews/${id}`);
          return;
        }

        if (intData.status === 'completed') {
          setInterview(intData);
          setSessionCompleted(true);
          setIsLoading(false);
          return;
        }

        // Start session if ready or in_progress to establish server-authoritative expires_at
        if (intData.status === 'ready' || intData.status === 'in_progress') {
          intData = await interviewService.startInterview(id);
        }
        setInterview(intData);

        // Generate or retrieve questions
        let qData = await interviewService.getQuestions(id);
        if (!qData.questions || qData.questions.length === 0) {
          qData = await interviewService.generateQuestions(id);
        }

        setQuestions(qData.questions || []);

        // Find first pending question
        const pendingIdx = (qData.questions || []).findIndex(q => q.status === 'pending');
        if (pendingIdx !== -1) {
          setCurrentIndex(pendingIdx);
          setCurrentQuestion(qData.questions[pendingIdx]);
        } else if (qData.questions && qData.questions.length > 0) {
          setSessionCompleted(true);
        }

        // Setup Countdown Timer
        const targetTime = parseUtcExpiresAt(intData.expires_at);
        let initialRemaining = 0;
        if (targetTime) {
          initialRemaining = Math.max(0, Math.floor((targetTime - Date.now()) / 1000));
        } else {
          initialRemaining = (intData.duration_minutes || 30) * 60;
        }
        setTimeLeft(initialRemaining);

        if (initialRemaining <= 0) {
          handleExpireAndComplete();
          return;
        }

        if (countdownIntervalRef.current) clearInterval(countdownIntervalRef.current);
        countdownIntervalRef.current = setInterval(() => {
          if (targetTime) {
            const rem = Math.max(0, Math.floor((targetTime - Date.now()) / 1000));
            setTimeLeft(rem);
            if (rem <= 0) {
              clearInterval(countdownIntervalRef.current);
              handleExpireAndComplete();
            }
          } else {
            setTimeLeft(prev => {
              if (prev === null || prev <= 1) {
                clearInterval(countdownIntervalRef.current);
                handleExpireAndComplete();
                return 0;
              }
              return prev - 1;
            });
          }
        }, 1000);

      } catch (err) {
        setError(err.message || 'Failed to initialize AI interview session.');
      } finally {
        setIsLoading(false);
      }
    }

    initSession();

    // Check TTS support
    if (!('speechSynthesis' in window)) {
      setTtsSupported(false);
    }

    return () => {
      stopCamera();
      if (window.speechSynthesis) window.speechSynthesis.cancel();
      if (recordingTimerRef.current) clearInterval(recordingTimerRef.current);
      if (visionIntervalRef.current) clearInterval(visionIntervalRef.current);
      if (countdownIntervalRef.current) clearInterval(countdownIntervalRef.current);
    };
  }, [id]);

  // 2. Speak question when question changes
  useEffect(() => {
    if (currentQuestion && ttsSupported) {
      speakText(currentQuestion.question);
    }
  }, [currentQuestion]);

  const speakText = (text) => {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.95;
    utterance.pitch = 1.0;
    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);
    window.speechSynthesis.speak(utterance);
  };

  const stopSpeaking = () => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      setIsSpeaking(false);
    }
  };

  // 3. Camera Controls
  const toggleCamera = async () => {
    if (cameraActive) {
      stopCamera();
    } else {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 480, height: 360 } });
        videoStreamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
        setCameraActive(true);

        // Start periodic frame capture for vision evaluation
        visionIntervalRef.current = setInterval(captureAndSendFrame, 4000);
      } catch (err) {
        alert('Camera access was denied or unavailable. You may proceed with voice-only interview.');
      }
    }
  };

  const stopCamera = () => {
    if (videoStreamRef.current) {
      videoStreamRef.current.getTracks().forEach(track => track.stop());
      videoStreamRef.current = null;
    }
    if (visionIntervalRef.current) {
      clearInterval(visionIntervalRef.current);
      visionIntervalRef.current = null;
    }
    setCameraActive(false);
  };

  const captureAndSendFrame = async () => {
    if (!videoRef.current || !cameraActive || !currentQuestion) return;
    try {
      const canvas = document.createElement('canvas');
      canvas.width = 320;
      canvas.height = 240;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(videoRef.current, 0, 0, 320, 240);
      const b64 = canvas.toDataURL('image/jpeg', 0.6);

      const metrics = await interviewService.sendVisionFrame(id, {
        questionId: currentQuestion.id,
        imageBase64: b64,
      });
      setVisionMetrics(metrics);
    } catch (e) {
      // Ignore background frame sync error
    }
  };

  // 4. Audio Recording
  const startRecording = async () => {
    if (sessionCompleted || (timeLeft !== null && timeLeft <= 0) || isCompletingRef.current) {
      return;
    }
    setError(null);
    stopSpeaking();
    setTranscript('');
    setLastFeedback(null);
    setIsFollowUpAlert(false);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunksRef.current = [];
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        // Close audio track
        stream.getTracks().forEach(track => track.stop());
        await processSpokenAnswer(audioBlob);
      };

      mediaRecorder.start(250);
      setIsRecording(true);
      setRecordingSeconds(0);

      recordingTimerRef.current = setInterval(() => {
        setRecordingSeconds(prev => prev + 1);
      }, 1000);
    } catch (err) {
      setError('Microphone access was denied or unavailable. Please enable microphone permissions or type your answer manually.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (recordingTimerRef.current) {
        clearInterval(recordingTimerRef.current);
      }
    }
  };

  // 5. Submit and Evaluate Spoken/Typed Answer
  const processSpokenAnswer = async (audioBlob) => {
    if (sessionCompleted || (timeLeft !== null && timeLeft <= 0) || isCompletingRef.current) {
      return;
    }
    setIsProcessingAnswer(true);
    try {
      // Step 1: Transcribe
      const transData = await interviewService.transcribeAudio(id, audioBlob, transcript);
      const finalTranscript = transData.transcript || transcript || 'Answer provided by candidate.';
      setTranscript(finalTranscript);

      // Step 2: Submit & Multi-modal Evaluate
      await submitAnswerToEngine(finalTranscript, transData.audio_filename, transData.duration_seconds || recordingSeconds);
    } catch (err) {
      if (err.message && err.message.toLowerCase().includes('expired')) {
        handleExpireAndComplete();
      } else {
        setError(err.message || 'Failed to process spoken answer.');
      }
    } finally {
      setIsProcessingAnswer(false);
    }
  };

  const handleManualSubmit = async () => {
    if (sessionCompleted || (timeLeft !== null && timeLeft <= 0) || isCompletingRef.current) {
      return;
    }
    if (!transcript.trim()) {
      setError('Please provide a spoken or typed answer before submitting.');
      return;
    }
    setIsProcessingAnswer(true);
    setError(null);
    try {
      await submitAnswerToEngine(transcript.trim(), null, 15.0);
    } catch (err) {
      if (err.message && err.message.toLowerCase().includes('expired')) {
        handleExpireAndComplete();
      } else {
        setError(err.message || 'Failed to evaluate answer.');
      }
    } finally {
      setIsProcessingAnswer(false);
    }
  };

  const submitAnswerToEngine = async (answerText, audioFilename, duration) => {
    if (!currentQuestion) return;
    try {
      const response = await interviewService.submitAnswer(id, {
        questionId: currentQuestion.id,
        transcript: answerText,
        speakingDuration: duration,
        audioFilename: audioFilename,
      });

      // Guard: Ignore response if session expired in background
      if (isCompletingRef.current || (timeLeft !== null && timeLeft <= 0)) {
        handleExpireAndComplete();
        return;
      }

      setLastFeedback({
        technical: response.technical_evaluation,
        communication: response.communication_evaluation,
        fluency: response.fluency_evaluation,
      });

      if (response.is_completed) {
        handleExpireAndComplete();
      } else if (response.next_question) {
        setQuestions(prev => {
          const exists = prev.some(q => q.id === response.next_question.id);
          return exists ? prev : [...prev, response.next_question];
        });
        setIsFollowUpAlert(Boolean(response.is_follow_up));
        setCurrentQuestion(response.next_question);
        setCurrentIndex(prev => prev + 1);
        setTranscript('');
      }
    } catch (err) {
      if (err.message && err.message.toLowerCase().includes('expired')) {
        handleExpireAndComplete();
      } else {
        throw err;
      }
    }
  };

  if (isLoading) {
    return (
      <div className="page-container py-5 text-center">
        <LoadingSpinner size="large" message="Preparing your AI Interview Session..." />
      </div>
    );
  }

  if (error && !currentQuestion) {
    return (
      <div className="page-container py-5">
        <div className="detail-card" style={{ maxWidth: '600px', margin: '0 auto', textAlign: 'center' }}>
          <h2 style={{ color: '#dc2626', marginBottom: '1rem' }}>⚠️ Unable to Load Interview Session</h2>
          <Alert type="error" message={error} />
          <div style={{ marginTop: '1.5rem', display: 'flex', gap: '1rem', justifyContent: 'center' }}>
            <button onClick={() => window.location.reload()} className="btn btn-secondary">
              🔄 Retry
            </button>
            <Link to={`/interviews/${id}`} className="btn btn-primary">
              ← Return to Session Setup
            </Link>
          </div>
        </div>
      </div>
    );
  }

  if (!currentQuestion && !sessionCompleted) {
    return (
      <div className="page-container py-5 text-center">
        <div className="detail-card" style={{ maxWidth: '600px', margin: '0 auto' }}>
          <h3>Preparing AI Interview Question...</h3>
          <p style={{ color: '#64748b', marginTop: '0.5rem' }}>The AI interviewer is retrieving or generating your dynamic question.</p>
          <div style={{ marginTop: '1.5rem', display: 'flex', gap: '1rem', justifyContent: 'center' }}>
            <button onClick={() => window.location.reload()} className="btn btn-primary">
              🔄 Refresh Session
            </button>
            <Link to={`/interviews/${id}`} className="btn btn-secondary">
              ← Back to Setup
            </Link>
          </div>
        </div>
      </div>
    );
  }

  if (sessionCompleted) {
    return (
      <div className="session-completed-card">
        <div className="completed-icon">🎉</div>
        <h1 className="completed-title">Mock Interview Completed!</h1>
        <p className="completed-subtitle">
          Great job! Your interview session has terminated and multi-modal evaluations are finalized.
        </p>

        <div className="completed-summary-box">
          <h3>Session Summary (Session #{id})</h3>
          <p><strong>Candidate:</strong> {interview?.resume_analysis?.candidate_name || 'Candidate'}</p>
          <p><strong>Interview Type:</strong> {interview?.interview_type === 'company' ? `${interview?.company_name || 'Target Company'} — ${interview?.job_role || 'Target Role'}` : 'General Placement Mock'}</p>
          <p><strong>Duration Selected:</strong> {interview?.duration_minutes || 30} minutes</p>
          <p><strong>Questions Evaluated:</strong> {questions.length} questions</p>
        </div>

        <div style={{ marginTop: '2rem', display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap' }}>
          <Link to="/dashboard" className="btn btn-primary btn-lg">
            Return to Dashboard
          </Link>
          <Link to={`/interviews/${id}`} className="btn btn-secondary btn-lg">
            View Session Details
          </Link>
          <Link to={`/interviews/${id}/report`} className="btn btn-primary btn-lg shadow-glow">
            📊 View Performance Report
          </Link>
        </div>
      </div>
    );
  }

  const isCompany = interview?.interview_type === 'company';

  return (
    <div className="interview-session-container">
      {/* Top Bar Header */}
      <div className="session-topbar">
        <div className="session-info">
          <span className="session-type-pill">
            {isCompany ? `🏢 ${interview?.company_name || 'Company'} • ${interview?.job_role || 'Role'}` : '🌐 General Placement Interview'}
          </span>
          <span className="question-counter-badge">
            Question {currentIndex + 1} {currentQuestion?.source === 'FOLLOW_UP' ? '(Dynamic Follow-up)' : ''}
          </span>
          <span className={`timer-badge ${timeLeft !== null && timeLeft <= 60 ? 'timer-warning pulse-fast' : ''}`}>
            ⏱️ {formatDuration(timeLeft !== null ? timeLeft : (interview?.duration_minutes || 30) * 60)}
          </span>
        </div>
        <div className="session-actions">
          <button
            onClick={toggleCamera}
            className={`btn btn-sm ${cameraActive ? 'btn-danger' : 'btn-secondary'}`}
          >
            {cameraActive ? '📷 Turn Off Camera' : '📷 Enable Camera'}
          </button>
          <button onClick={() => navigate('/dashboard')} className="btn btn-outline btn-sm">
            Exit Session
          </button>
        </div>
      </div>

      <Alert type="error" message={error} onDismiss={() => setError(null)} />

      {isFollowUpAlert && (
        <div className="followup-alert-banner">
          <span>⚡ <strong>Adaptive Follow-up:</strong> The AI interviewer is probing deeper based on your previous response!</span>
        </div>
      )}

      {/* Main Grid: AI Interviewer & Question Area */}
      <div className="session-grid">
        {/* Left Column: AI Persona & Current Question */}
        <div className="session-main-panel">
          <div className="ai-interviewer-card">
            <div className="ai-avatar-row">
              <div className={`ai-avatar ${isSpeaking ? 'speaking-pulse' : ''}`}>
                🤖
              </div>
              <div className="ai-avatar-meta">
                <h3>AI Technical Interviewer</h3>
                <span className="ai-status-indicator">
                  {isSpeaking ? '🔊 Speaking question...' : '👂 Listening to candidate'}
                </span>
              </div>
            </div>

            {/* Question Text */}
            <div className="question-display-box">
              <div className="question-tags">
                <span className="tag-category">{currentQuestion?.category}</span>
                <span className={`tag-difficulty ${currentQuestion?.difficulty?.toLowerCase()}`}>
                  {currentQuestion?.difficulty}
                </span>
                <span className="tag-source">Source: {currentQuestion?.source}</span>
              </div>

              <h2 className="active-question-text">{currentQuestion?.question}</h2>

              {currentQuestion?.expected_focus && currentQuestion.expected_focus.length > 0 && (
                <div className="expected-focus-box">
                  <strong>Expected Focus:</strong> {currentQuestion.expected_focus.join(' • ')}
                </div>
              )}

              {/* TTS Controls */}
              <div className="tts-controls-row">
                <button
                  onClick={() => currentQuestion?.question && speakText(currentQuestion.question)}
                  className="btn btn-outline btn-sm"
                  title="Replay Question Audio"
                >
                  🔊 Repeat Question
                </button>
                {isSpeaking && (
                  <button onClick={stopSpeaking} className="btn btn-outline btn-sm">
                    ⏹️ Stop Audio
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Answer Recording & Input Area */}
          <div className="answer-card">
            <div className="answer-header">
              <h3>Your Response</h3>
              {isRecording && (
                <span className="recording-badge pulse">
                  🔴 Recording ({recordingSeconds}s)
                </span>
              )}
            </div>

            <textarea
              className="answer-textarea"
              placeholder="Click 'Start Spoken Answer' to speak via microphone, or type your answer directly..."
              value={transcript}
              onChange={(e) => setTranscript(e.target.value)}
              disabled={isRecording || isProcessingAnswer}
              rows={4}
            />

            <div className="answer-controls-row">
              {!isRecording ? (
                <button
                  onClick={startRecording}
                  className="btn btn-primary btn-lg shadow-glow"
                  disabled={isProcessingAnswer}
                >
                  🎙️ Start Spoken Answer
                </button>
              ) : (
                <button
                  onClick={stopRecording}
                  className="btn btn-danger btn-lg pulse"
                >
                  ⏹️ Stop & Submit Spoken Answer
                </button>
              )}

              <button
                onClick={handleManualSubmit}
                className="btn btn-secondary btn-lg"
                disabled={isRecording || isProcessingAnswer || !transcript.trim()}
              >
                {isProcessingAnswer ? <LoadingSpinner size="small" message="Evaluating..." /> : 'Submit Text Answer ➔'}
              </button>
            </div>
          </div>

          {/* Previous Answer Real-Time Feedback Card */}
          {lastFeedback && (
            <div className="live-feedback-card">
              <h3 className="feedback-title">📊 Multi-Modal Analysis on Previous Answer</h3>
              <div className="feedback-scores-grid">
                <div className="score-badge-box">
                  <span className="score-label">Technical Score</span>
                  <span className="score-val">{lastFeedback.technical.technical_score}%</span>
                </div>
                <div className="score-badge-box">
                  <span className="score-label">Correctness</span>
                  <span className="score-val">{lastFeedback.technical.correctness}%</span>
                </div>
                <div className="score-badge-box">
                  <span className="score-label">Fluency Score</span>
                  <span className="score-val">{lastFeedback.fluency.fluency_score}%</span>
                </div>
                <div className="score-badge-box">
                  <span className="score-label">Pace (WPM)</span>
                  <span className="score-val">{lastFeedback.fluency.wpm}</span>
                </div>
                <div className="score-badge-box">
                  <span className="score-label">Communication</span>
                  <span className="score-val">{lastFeedback.communication.communication_score}%</span>
                </div>
                <div className="score-badge-box">
                  <span className="score-label">Filler Words</span>
                  <span className="score-val">{lastFeedback.fluency.filler_word_count}</span>
                </div>
              </div>
              <p className="feedback-text">
                <strong>Technical Assessment:</strong> {lastFeedback.technical.feedback}
              </p>
              <p className="feedback-text">
                <strong>Communication Assessment:</strong> {lastFeedback.communication.feedback}
              </p>
            </div>
          )}
        </div>

        {/* Right Column: Webcam & Vision Feedback */}
        <div className="session-side-panel">
          <div className="webcam-card">
            <h3>Candidate Camera Feed</h3>
            <div className="webcam-viewfinder">
              {cameraActive ? (
                <video ref={videoRef} autoPlay playsInline muted className="webcam-video" />
              ) : (
                <div className="webcam-placeholder">
                  <span className="camera-icon">📷</span>
                  <p>Webcam is currently disabled.</p>
                  <button onClick={toggleCamera} className="btn btn-secondary btn-sm" style={{ marginTop: '0.5rem' }}>
                    Enable Camera
                  </button>
                </div>
              )}
            </div>

            {cameraActive && visionMetrics && (
              <div className="vision-metrics-box">
                <h4>Observable Vision Indicators</h4>
                <div className="metric-row">
                  <span>Face Presence:</span>
                  <strong>{visionMetrics.face_detected ? '✅ Detected' : '❌ Not Detected'}</strong>
                </div>
                <div className="metric-row">
                  <span>Eye-Contact Proxy Score:</span>
                  <strong>{visionMetrics.eye_contact_proxy_score}%</strong>
                </div>
                <div className="metric-row">
                  <span>Posture Score:</span>
                  <strong>{visionMetrics.posture_score}%</strong>
                </div>
                <div className="metric-row">
                  <span>Observable Facial Expression:</span>
                  <strong>{visionMetrics.dominant_emotion}</strong>
                </div>
              </div>
            )}
          </div>

          <div className="guidance-card">
            <h3>Placement Interview Tips</h3>
            <ul className="tips-list">
              <li>Structure answers using <strong>STAR</strong> (Situation, Task, Action, Result).</li>
              <li>State technical trade-offs explicitly (e.g. time vs space complexity).</li>
              <li>Maintain steady vocal pacing around 120–150 words per minute.</li>
              <li>Face the camera directly to ensure optimal posture evaluation.</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
