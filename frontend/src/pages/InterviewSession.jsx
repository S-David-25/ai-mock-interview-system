import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { interviewService } from '../services/interviewService';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { Alert } from '../components/Alert';
import { formatDuration } from '../utils/formatters';

const ANSWER_SILENCE_WINDOW_MS = 2000;

export function InterviewSession() {
  const { id } = useParams();
  const navigate = useNavigate();

  // State
  const [interview, setInterview] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [pendingQuestion, setPendingQuestion] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [sessionCompleted, setSessionCompleted] = useState(false);
  const [timeLeft, setTimeLeft] = useState(null);

  // Audio Recording State
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [transcript, setTranscript] = useState('');
  const [isProcessingAnswer, setIsProcessingAnswer] = useState(false);
  const [isFollowUpAlert, setIsFollowUpAlert] = useState(false);

  // TTS State
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [ttsSupported, setTtsSupported] = useState(true);

  // Webcam State
  const [cameraActive, setCameraActive] = useState(false);
  const [visionMetrics, setVisionMetrics] = useState(null);
  const [faceCount, setFaceCount] = useState(0);
  const [expressionLabel, setExpressionLabel] = useState('Not Detected');
  const [interviewStarted, setInterviewStarted] = useState(false);

  // Refs
  const mediaRecorderRef = useRef(null);
  const isRecordingRef = useRef(false);
  const audioChunksRef = useRef([]);
  const recordingTimerRef = useRef(null);
  const silenceTimerRef = useRef(null);
  const silenceCheckRef = useRef(null);
  const audioContextRef = useRef(null);
  const hasSpokenRef = useRef(false);
  const expressionLabelRef = useRef('Not Detected');
  const expressionHistoryRef = useRef([]);
  const ttsSequenceRef = useRef(0);
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
    isRecordingRef.current = false;
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
        if (intData.status === 'in_progress') {
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
          setPendingQuestion(qData.questions[pendingIdx]);
        } else if (qData.questions && qData.questions.length > 0) {
          setSessionCompleted(true);
        }

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

  const startCountdown = (interviewData) => {
    const targetTime = parseUtcExpiresAt(interviewData.expires_at);
    const initialRemaining = targetTime
      ? Math.max(0, Math.floor((targetTime - Date.now()) / 1000))
      : (interviewData.duration_minutes || 30) * 60;
    setTimeLeft(initialRemaining);

    if (initialRemaining <= 0) {
      handleExpireAndComplete();
      return;
    }

    if (countdownIntervalRef.current) clearInterval(countdownIntervalRef.current);
    countdownIntervalRef.current = setInterval(() => {
      if (targetTime) {
        const remaining = Math.max(0, Math.floor((targetTime - Date.now()) / 1000));
        setTimeLeft(remaining);
        if (remaining <= 0) {
          clearInterval(countdownIntervalRef.current);
          handleExpireAndComplete();
        }
      } else {
        setTimeLeft(previous => {
          if (previous === null || previous <= 1) {
            clearInterval(countdownIntervalRef.current);
            handleExpireAndComplete();
            return 0;
          }
          return previous - 1;
        });
      }
    }, 1000);
  };

  // 2. Speak question when question changes
  useEffect(() => {
    if (currentQuestion && interviewStarted && ttsSupported) {
      speakText(currentQuestion.question);
    } else if (currentQuestion && interviewStarted && !ttsSupported) {
      startRecording();
    }
  }, [currentQuestion, interviewStarted, ttsSupported]);

  const speakText = (text, autoRecord = true) => {
    if (!('speechSynthesis' in window)) return;
    const sequence = ++ttsSequenceRef.current;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.95;
    utterance.pitch = 1.0;
    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend = () => {
      if (sequence !== ttsSequenceRef.current) return;
      setIsSpeaking(false);
      if (autoRecord && interviewStarted && currentQuestion) startRecording();
    };
    utterance.onerror = () => {
      if (sequence !== ttsSequenceRef.current) return;
      setIsSpeaking(false);
      if (autoRecord && interviewStarted && currentQuestion) startRecording();
    };
    window.speechSynthesis.speak(utterance);
  };

  const stopSpeaking = () => {
    if ('speechSynthesis' in window) {
      ttsSequenceRef.current += 1;
      window.speechSynthesis.cancel();
      setIsSpeaking(false);
    }
  };

  // 3. Camera Controls
  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 480, height: 360 } });
      videoStreamRef.current = stream;
      setCameraActive(true);

      // Start periodic frame capture for vision evaluation
      visionIntervalRef.current = setInterval(captureAndSendFrame, 4000);
    } catch (err) {
      setError('Camera access was denied or unavailable. Please enable camera permissions to start the interview.');
    }
  };

  useEffect(() => {
    if (!isLoading && !sessionCompleted) {
      startCamera();
    }
  }, [isLoading, sessionCompleted]);

  useEffect(() => {
    const video = videoRef.current;
    const stream = videoStreamRef.current;
    if (!video || !stream || !cameraActive) return;

    video.srcObject = stream;
    const playVideo = () => {
      video.play().catch(() => {
        setError('The camera is enabled, but the live preview could not start.');
      });
    };

    video.onloadedmetadata = playVideo;
    if (video.readyState >= 1) playVideo();

    return () => {
      if (video.onloadedmetadata === playVideo) {
        video.onloadedmetadata = null;
      }
    };
  }, [cameraActive]);

  const stopCamera = () => {
    if (videoRef.current) {
      videoRef.current.pause();
      videoRef.current.srcObject = null;
    }
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
    if (!videoRef.current || !videoStreamRef.current) return;
    try {
      const canvas = document.createElement('canvas');
      canvas.width = 320;
      canvas.height = 240;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(videoRef.current, 0, 0, 320, 240);
      const b64 = canvas.toDataURL('image/jpeg', 0.6);

      const metrics = await interviewService.sendVisionFrame(id, {
        questionId: currentQuestion?.id || null,
        imageBase64: b64,
      });
      const detectedFaceCount = metrics.face_count || 0;
      let nextExpression = expressionLabelRef.current;
      if (detectedFaceCount === 0) {
        nextExpression = 'Not Detected';
        expressionHistoryRef.current = [];
      } else if (detectedFaceCount > 1) {
        nextExpression = 'Multiple Faces';
        expressionHistoryRef.current = [];
      } else if (metrics.expression_confidence >= 0.45 && metrics.dominant_emotion !== 'Unknown') {
        expressionHistoryRef.current = [
          ...expressionHistoryRef.current.slice(-4),
          metrics.dominant_emotion,
        ];
        const counts = expressionHistoryRef.current.reduce((result, label) => {
          result[label] = (result[label] || 0) + 1;
          return result;
        }, {});
        const stableExpression = Object.entries(counts).sort((left, right) => right[1] - left[1])[0];
        if (stableExpression && stableExpression[1] >= 2) {
          nextExpression = stableExpression[0];
        }
      }
      setVisionMetrics(metrics);
      setFaceCount(detectedFaceCount);
      expressionLabelRef.current = nextExpression;
      setExpressionLabel(nextExpression);
    } catch (e) {
      // Ignore background frame sync error
    }
  };

  const handleStartInterview = async () => {
    if (faceCount !== 1 || !pendingQuestion) return;
    try {
      const startedInterview = await interviewService.startInterview(id);
      setInterview(startedInterview);
      setInterviewStarted(true);
      setCurrentQuestion(pendingQuestion);
      setPendingQuestion(null);
      startCountdown(startedInterview);
    } catch (err) {
      setError(err.message || 'Failed to start the interview.');
    }
  };

  // 4. Audio Recording
  const startRecording = async () => {
    if (!interviewStarted || !currentQuestion || sessionCompleted || (timeLeft !== null && timeLeft <= 0) || isCompletingRef.current || isRecording || isProcessingAnswer) {
      return;
    }
    setError(null);
    stopSpeaking();
    setTranscript('');
    setIsFollowUpAlert(false);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunksRef.current = [];
      hasSpokenRef.current = false;
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        if (silenceCheckRef.current) clearInterval(silenceCheckRef.current);
        if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
        if (audioContextRef.current) {
          await audioContextRef.current.close().catch(() => {});
          audioContextRef.current = null;
        }
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        // Close audio track
        stream.getTracks().forEach(track => track.stop());
        await processSpokenAnswer(audioBlob);
      };

      mediaRecorder.start(250);
      setIsRecording(true);
      isRecordingRef.current = true;
      setRecordingSeconds(0);

      const audioContext = new AudioContext();
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 512;
      const source = audioContext.createMediaStreamSource(stream);
      source.connect(analyser);
      audioContextRef.current = audioContext;
      const samples = new Uint8Array(analyser.fftSize);
      silenceCheckRef.current = setInterval(() => {
        analyser.getByteTimeDomainData(samples);
        const volume = Math.sqrt(samples.reduce((sum, sample) => {
          const normalized = (sample - 128) / 128;
          return sum + normalized * normalized;
        }, 0) / samples.length);

        if (volume > 0.025) {
          hasSpokenRef.current = true;
          if (silenceTimerRef.current) {
            clearTimeout(silenceTimerRef.current);
            silenceTimerRef.current = null;
          }
        } else if (hasSpokenRef.current && !silenceTimerRef.current) {
          silenceTimerRef.current = setTimeout(() => stopRecording(), ANSWER_SILENCE_WINDOW_MS);
        }
      }, 200);

      recordingTimerRef.current = setInterval(() => {
        setRecordingSeconds(prev => prev + 1);
      }, 1000);
    } catch (err) {
      setError('Microphone access was denied or unavailable. Please enable microphone permissions to answer by voice.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecordingRef.current) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      isRecordingRef.current = false;
      if (recordingTimerRef.current) {
        clearInterval(recordingTimerRef.current);
        recordingTimerRef.current = null;
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
      const transData = await interviewService.transcribeAudio(id, audioBlob, '', currentQuestion?.question || '');
      const finalTranscript = (transData.transcript || '').trim();
      if (!finalTranscript) {
        throw new Error('The answer could not be transcribed. Please try answering again.');
      }
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
            ⏱️ {formatDuration(timeLeft !== null ? timeLeft : 0)}
          </span>
        </div>
        <div className="session-actions">
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
              {currentQuestion ? (
                <>
                  <div className="question-tags">
                    <span className="tag-category">{currentQuestion.category}</span>
                    <span className={`tag-difficulty ${currentQuestion.difficulty?.toLowerCase()}`}>
                      {currentQuestion.difficulty}
                    </span>
                    <span className="tag-source">Source: {currentQuestion.source}</span>
                  </div>

                  <h2 className="active-question-text">{currentQuestion.question}</h2>

                  {currentQuestion.expected_focus && currentQuestion.expected_focus.length > 0 && (
                    <div className="expected-focus-box">
                      <strong>Expected Focus:</strong> {currentQuestion.expected_focus.join(' • ')}
                    </div>
                  )}

                  <div className="tts-controls-row">
                    <button
                      onClick={() => {
                        if (isRecordingRef.current) stopRecording();
                        if (currentQuestion.question) speakText(currentQuestion.question);
                      }}
                      disabled={isRecording || isProcessingAnswer}
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
                </>
              ) : (
                <>
                  <h2 className="active-question-text">Ready to begin your interview</h2>
                  <p style={{ color: '#64748b' }}>
                    {faceCount === 0
                      ? 'No face detected. Please position yourself in front of the camera.'
                      : faceCount > 1
                        ? 'Multiple faces detected. Please ensure only one person is visible.'
                        : 'One face detected. You can start the interview.'}
                  </p>
                  {faceCount === 1 && (
                    <button onClick={handleStartInterview} className="btn btn-primary btn-lg" disabled={interviewStarted}>
                      Start Interview
                    </button>
                  )}
                </>
              )}
            </div>
          </div>

          {isRecording && (
            <div className="recording-badge pulse" style={{ marginTop: '1rem' }}>
              🔴 Listening for your answer ({recordingSeconds}s)
            </div>
          )}
          {isProcessingAnswer && <LoadingSpinner size="small" message="Evaluating your answer..." />}

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
                  <p>Waiting for camera access...</p>
                </div>
              )}
            </div>

            {cameraActive && (
              <div className="vision-metrics-box">
                <h4>Observable Vision Indicators</h4>
                <div className="metric-row">
                  <span>Face Presence:</span>
                  <strong>{faceCount === 1 ? '✅ Detected' : faceCount > 1 ? '⚠️ Multiple Faces' : '❌ Not Detected'}</strong>
                </div>
                <div className="metric-row">
                  <span>Eye-Contact Proxy Score:</span>
                  <strong>{visionMetrics?.eye_contact_proxy_score || 0}%</strong>
                </div>
                <div className="metric-row">
                  <span>Posture Score:</span>
                  <strong>{visionMetrics?.posture_score || 0}%</strong>
                </div>
                <div className="metric-row">
                  <span>Observable Facial Expression:</span>
                  <strong>{expressionLabel}</strong>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
