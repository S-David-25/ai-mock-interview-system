/**
 * AI Mock Interview System - Interactive Client SPA (Master Prompts 1, 2 & 3 Complete)
 */

const API_BASE = '';

// Auth & Session State
let state = {
  user: JSON.parse(localStorage.getItem('ai_mock_user') || 'null'),
  token: localStorage.getItem('ai_mock_token') || null,
  route: window.location.hash.slice(1) || 'dashboard',
  interviews: [],
  stats: null,
  progress: null,
  activeInterview: null,
  activeReport: null,
  activeComparison: null,
  questions: [],
  currentQuestionIndex: 0,
  currentQuestion: null,
  isRecording: false,
  recordingSeconds: 0,
  transcript: '',
  lastFeedback: null,
  isFollowUpAlert: false,
  isSpeaking: false,
  cameraActive: false,
  visionMetrics: null,
  sessionCompleted: false,
  timeLeft: null,
  reportTab: 'overview',
  compareFirstId: '',
  compareSecondId: '',
  loading: false,
  error: null,
  successMsg: null,
};

let recordingInterval = null;
let mediaRecorder = null;
let audioChunks = [];
let videoStream = null;
let visionInterval = null;
let countdownInterval = null;
let isCompleting = false;

// API Helpers
async function apiRequest(endpoint, options = {}) {
  const headers = { ...options.headers };
  if (state.token) {
    headers['Authorization'] = `Bearer ${state.token}`;
  }
  if (options.body && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
    options.body = typeof options.body === 'string' ? options.body : JSON.stringify(options.body);
  }

  const res = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });
  let data;
  const cType = res.headers.get('content-type');
  if (cType && cType.includes('application/json')) {
    data = await res.json();
  } else {
    data = await res.text();
  }

  if (!res.ok) {
    if (res.status === 401) {
      logout();
    }
    let errorMsg = 'An error occurred.';
    if (data && typeof data === 'object') {
      errorMsg = data.detail || (data.errors && data.errors.join(', ')) || data.message || errorMsg;
    }
    throw new Error(errorMsg);
  }
  return data;
}

// Router & Navigation
function navigate(route) {
  state.route = route;
  window.location.hash = route;
  state.error = null;
  state.successMsg = null;
  render();
}

window.addEventListener('hashchange', () => {
  state.route = window.location.hash.slice(1) || 'dashboard';
  state.error = null;
  render();
});

function logout() {
  state.user = null;
  state.token = null;
  localStorage.removeItem('ai_mock_token');
  localStorage.removeItem('ai_mock_user');
  stopCamera();
  stopSpeaking();
  navigate('login');
}

// Data Fetchers
async function fetchDashboardData() {
  if (!state.token) return;
  state.loading = true;
  render();
  try {
    const [intData, progData] = await Promise.all([
      apiRequest('/api/interviews'),
      apiRequest('/api/progress'),
    ]);
    state.interviews = intData.interviews || [];
    state.stats = intData.stats || null;
    state.progress = progData || null;
  } catch (err) {
    state.error = err.message;
  } finally {
    state.loading = false;
    render();
  }
}

async function fetchInterviewDetail(id) {
  if (!state.token) return;
  state.loading = true;
  render();
  try {
    const [intData, statData] = await Promise.all([
      apiRequest(`/api/interviews/${id}`),
      apiRequest(`/api/interviews/${id}/status`),
    ]);
    state.activeInterview = { ...intData, statusData: statData };
  } catch (err) {
    state.error = err.message;
  } finally {
    state.loading = false;
    render();
  }
}

async function fetchReport(id) {
  if (!state.token) return;
  state.loading = true;
  render();
  try {
    const repData = await apiRequest(`/api/interviews/${id}/report`);
    state.activeReport = repData;
  } catch (err) {
    state.error = err.message;
  } finally {
    state.loading = false;
    render();
  }
}

async function fetchComparison(fId, sId) {
  if (!state.token || !fId || !sId) return;
  state.loading = true;
  render();
  try {
    const compData = await apiRequest(`/api/interviews/compare?first_id=${fId}&second_id=${sId}`);
    state.activeComparison = compData;
  } catch (err) {
    state.error = err.message;
  } finally {
    state.loading = false;
    render();
  }
}

function parseUtcExpiresAt(expiresAtStr) {
  if (!expiresAtStr) return null;
  const clean = String(expiresAtStr).trim().replace(' ', 'T') + (expiresAtStr.includes('Z') || expiresAtStr.includes('+') || (expiresAtStr.length > 10 && expiresAtStr.slice(10).includes('-')) ? '' : 'Z');
  const target = new Date(clean).getTime();
  if (isNaN(target)) return null;
  return target;
}

async function handleSessionExpiry() {
  if (isCompleting) return;
  isCompleting = true;

  // 1. Cancel TTS
  stopSpeaking();

  // 2. Stop audio recording
  stopRecording();

  // 3. Stop camera
  stopCamera();

  // 4. Clear intervals
  if (countdownInterval) {
    clearInterval(countdownInterval);
    countdownInterval = null;
  }
  if (recordingInterval) {
    clearInterval(recordingInterval);
    recordingInterval = null;
  }
  if (visionInterval) {
    clearInterval(visionInterval);
    visionInterval = null;
  }

  // 5. Complete session in backend
  try {
    if (state.activeInterview) {
      await apiRequest(`/api/interviews/${state.activeInterview.id}/complete`, { method: 'POST' });
    }
  } catch (e) {}

  // 6. Transition to completion UI
  state.sessionCompleted = true;
  render();
}

async function initInterviewSession(id) {
  if (!state.token) return;
  state.loading = true;
  state.sessionCompleted = false;
  state.lastFeedback = null;
  state.isFollowUpAlert = false;
  isCompleting = false;
  render();

  try {
    let intData = await apiRequest(`/api/interviews/${id}`);

    if (intData.status === 'completed') {
      state.activeInterview = intData;
      state.sessionCompleted = true;
      state.loading = false;
      render();
      return;
    }

    if (intData.status === 'ready' || intData.status === 'in_progress') {
      intData = await apiRequest(`/api/interviews/${id}/start`, { method: 'POST' });
    }
    state.activeInterview = intData;

    if (!intData.resume_analysis) {
      await apiRequest(`/api/interviews/${id}/process`, { method: 'POST' });
    }

    let qData = await apiRequest(`/api/interviews/${id}/questions`);
    if (!qData.questions || qData.questions.length === 0) {
      qData = await apiRequest(`/api/interviews/${id}/generate-questions`, { method: 'POST' });
    }
    state.questions = qData.questions || [];

    const pendingIdx = state.questions.findIndex(q => q.status === 'pending');
    if (pendingIdx !== -1) {
      state.currentQuestionIndex = pendingIdx;
      state.currentQuestion = state.questions[pendingIdx];
    } else if (state.questions.length > 0) {
      state.sessionCompleted = true;
    }

    // Countdown Timer Setup
    const targetTime = parseUtcExpiresAt(intData.expires_at);
    let initialRemaining = 0;
    if (targetTime) {
      initialRemaining = Math.max(0, Math.floor((targetTime - Date.now()) / 1000));
    } else {
      initialRemaining = (intData.duration_minutes || 30) * 60;
    }
    state.timeLeft = initialRemaining;

    if (initialRemaining <= 0) {
      handleSessionExpiry();
      return;
    }

    if (countdownInterval) clearInterval(countdownInterval);
    countdownInterval = setInterval(() => {
      if (targetTime) {
        const rem = Math.max(0, Math.floor((targetTime - Date.now()) / 1000));
        state.timeLeft = rem;
        const timerEl = document.getElementById('sessionTimerBadge');
        if (timerEl) {
          timerEl.innerHTML = `⏱️ ${formatDuration(rem)}`;
          if (rem <= 60) timerEl.classList.add('timer-warning', 'pulse-fast');
        }
        if (rem <= 0) {
          clearInterval(countdownInterval);
          handleSessionExpiry();
        }
      } else {
        if (state.timeLeft <= 1) {
          clearInterval(countdownInterval);
          handleSessionExpiry();
        } else {
          state.timeLeft -= 1;
          const timerEl = document.getElementById('sessionTimerBadge');
          if (timerEl) {
            timerEl.innerHTML = `⏱️ ${formatDuration(state.timeLeft)}`;
            if (state.timeLeft <= 60) timerEl.classList.add('timer-warning', 'pulse-fast');
          }
        }
      }
    }, 1000);

  } catch (err) {
    state.error = err.message;
  } finally {
    state.loading = false;
    render();
    if (state.currentQuestion && !state.sessionCompleted) {
      speakQuestion(state.currentQuestion.question);
    }
  }
}

// Text-to-Speech
function speakQuestion(text) {
  if (!('speechSynthesis' in window) || !text) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 0.95;
  utterance.pitch = 1.0;
  utterance.onstart = () => { state.isSpeaking = true; render(); };
  utterance.onend = () => { state.isSpeaking = false; render(); };
  utterance.onerror = () => { state.isSpeaking = false; render(); };
  window.speechSynthesis.speak(utterance);
}

function stopSpeaking() {
  if ('speechSynthesis' in window) {
    window.speechSynthesis.cancel();
    state.isSpeaking = false;
  }
}

// Camera Controls
async function toggleCamera() {
  if (state.cameraActive) {
    stopCamera();
    render();
  } else {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 480, height: 360 } });
      videoStream = stream;
      state.cameraActive = true;
      render();

      const videoEl = document.getElementById('webcamVideo');
      if (videoEl) videoEl.srcObject = stream;

      visionInterval = setInterval(captureAndSendFrame, 4000);
    } catch (e) {
      alert('Camera access denied or unavailable. Voice interview remains fully functional.');
    }
  }
}

function stopCamera() {
  if (videoStream) {
    videoStream.getTracks().forEach(t => t.stop());
    videoStream = null;
  }
  if (visionInterval) {
    clearInterval(visionInterval);
    visionInterval = null;
  }
  state.cameraActive = false;
}

async function captureAndSendFrame() {
  const videoEl = document.getElementById('webcamVideo');
  if (!videoEl || !state.cameraActive || !state.currentQuestion || !state.activeInterview) return;
  try {
    const canvas = document.createElement('canvas');
    canvas.width = 320;
    canvas.height = 240;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(videoEl, 0, 0, 320, 240);
    const b64 = canvas.toDataURL('image/jpeg', 0.6);

    const metrics = await apiRequest(`/api/interviews/${state.activeInterview.id}/vision-frame`, {
      method: 'POST',
      body: {
        question_id: state.currentQuestion.id,
        image_base64: b64
      }
    });
    state.visionMetrics = metrics;
    const vBox = document.getElementById('visionMetricsDisplay');
    if (vBox) {
      vBox.innerHTML = `
        <div class="metric-row"><span>Face Presence:</span><strong>${metrics.face_detected ? '✅ Detected' : '❌ None'}</strong></div>
        <div class="metric-row"><span>Eye-Contact Proxy:</span><strong>${metrics.eye_contact_proxy_score}%</strong></div>
        <div class="metric-row"><span>Posture Score:</span><strong>${metrics.posture_score}%</strong></div>
        <div class="metric-row"><span>Expression:</span><strong>${metrics.dominant_emotion}</strong></div>
      `;
    }
  } catch (e) {}
}

// Audio Recording
async function startRecording() {
  state.error = null;
  stopSpeaking();
  state.transcript = '';
  state.lastFeedback = null;
  state.isFollowUpAlert = false;

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioChunks = [];
    mediaRecorder = new MediaRecorder(stream);

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunks.push(e.data);
    };

    mediaRecorder.onstop = async () => {
      const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
      stream.getTracks().forEach(t => t.stop());
      await handleAudioRecorded(audioBlob);
    };

    mediaRecorder.start(250);
    state.isRecording = true;
    state.recordingSeconds = 0;
    render();

    recordingInterval = setInterval(() => {
      state.recordingSeconds += 1;
      const b = document.getElementById('recordingTimerText');
      if (b) b.innerText = `🔴 Recording (${state.recordingSeconds}s)`;
    }, 1000);
  } catch (e) {
    state.error = 'Microphone access denied. You may type your response manually below.';
    render();
  }
}

function stopRecording() {
  if (mediaRecorder && state.isRecording) {
    mediaRecorder.stop();
    state.isRecording = false;
    if (recordingInterval) clearInterval(recordingInterval);
    render();
  }
}

async function handleAudioRecorded(audioBlob) {
  state.loading = true;
  render();
  try {
    const intId = state.activeInterview.id;
    const formData = new FormData();
    formData.append('file', audioBlob, 'recording.webm');
    if (state.transcript) formData.append('fallback_text', state.transcript);

    const transData = await apiRequest(`/api/interviews/${intId}/transcribe`, {
      method: 'POST',
      body: formData
    });

    const finalTranscript = transData.transcript || state.transcript || 'Spoken answer submitted.';
    state.transcript = finalTranscript;
    await submitAnswerPayload(finalTranscript, transData.audio_filename, transData.duration_seconds || state.recordingSeconds);
  } catch (err) {
    state.error = err.message;
  } finally {
    state.loading = false;
    render();
  }
}

async function handleManualSubmit() {
  const textInput = document.getElementById('answerTextInput')?.value || state.transcript;
  if (!textInput.trim()) {
    state.error = 'Please provide a response before submitting.';
    render();
    return;
  }
  state.loading = true;
  render();
  try {
    await submitAnswerPayload(textInput.trim(), null, 15.0);
  } catch (err) {
    state.error = err.message;
  } finally {
    state.loading = false;
    render();
  }
}

async function submitAnswerPayload(ansText, audioFile, duration) {
  const intId = state.activeInterview.id;
  const qId = state.currentQuestion.id;

  try {
    const res = await apiRequest(`/api/interviews/${intId}/answer`, {
      method: 'POST',
      body: {
        question_id: qId,
        transcript: ansText,
        speaking_duration: duration,
        audio_filename: audioFile
      }
    });

    state.lastFeedback = {
      technical: res.technical_evaluation,
      communication: res.communication_evaluation,
      fluency: res.fluency_evaluation,
    };

    if (res.is_completed) {
      handleSessionExpiry();
    } else if (res.next_question) {
      if (!state.questions) state.questions = [];
      if (!state.questions.some(q => q.id === res.next_question.id)) {
        state.questions.push(res.next_question);
      }
      state.isFollowUpAlert = Boolean(res.is_follow_up);
      state.currentQuestion = res.next_question;
      state.currentQuestionIndex = (state.currentQuestionIndex || 0) + 1;
      state.transcript = '';
      speakQuestion(res.next_question.question);
    }
  } catch (err) {
    if (err.message && err.message.toLowerCase().includes('expired')) {
      handleSessionExpiry();
    } else {
      throw err;
    }
  }
}

// Formatters
function formatDate(dStr) {
  if (!dStr) return 'N/A';
  try {
    let clean = String(dStr).trim().replace(' ', 'T');
    if (!clean.endsWith('Z') && !clean.includes('+') && !clean.slice(10).includes('-')) {
      clean += 'Z';
    }
    const d = new Date(clean);
    if (isNaN(d.getTime())) return dStr;
    return d.toLocaleDateString(undefined, {
      month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit'
    });
  } catch(e) { return dStr; }
}

function formatDuration(seconds) {
  if (seconds === null || seconds === undefined || isNaN(seconds) || seconds < 0) return '00:00';
  const totalSec = Math.floor(seconds);
  const mins = Math.floor(totalSec / 60);
  const secs = totalSec % 60;
  if (mins >= 60) {
    const hrs = Math.floor(mins / 60);
    const remMins = mins % 60;
    return `${String(hrs).padStart(2, '0')}:${String(remMins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  }
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

function getStatusBadge(status) {
  switch (status) {
    case 'ready':
      return `<span class="badge-status" style="background:#dcfce7;color:#15803d;border-color:#86efac">Ready to Start</span>`;
    case 'in_progress':
      return `<span class="badge-status" style="background:#fef3c7;color:#b45309;border-color:#fde68a">In Progress</span>`;
    case 'completed':
      return `<span class="badge-status" style="background:#e0e7ff;color:#4338ca;border-color:#c7d2fe">Completed</span>`;
    case 'failed':
      return `<span class="badge-status" style="background:#fee2e2;color:#b91c1c;border-color:#fca5a5">Failed</span>`;
    default:
      return `<span class="badge-status" style="background:#f1f5f9;color:#475569;border-color:#cbd5e1">Setup Incomplete</span>`;
  }
}

// Navigation Bar
function renderNavbar() {
  if (!state.token || !state.user) {
    return `
      <header class="navbar">
        <div class="navbar-container">
          <a href="#login" class="navbar-brand">
            <div class="logo-icon">🎯</div>
            <span class="brand-title">AI Mock Interview</span>
            <span class="brand-badge">Coach</span>
          </a>
          <div class="navbar-links">
            <button onclick="navigate('login')" class="btn btn-secondary btn-sm">Login</button>
            <button onclick="navigate('register')" class="btn btn-primary btn-sm">Get Started</button>
          </div>
        </div>
      </header>
    `;
  }

  const isDashboard = state.route === 'dashboard';
  const isSetup = state.route === 'setup';
  const isCompare = state.route === 'interviews/compare';

  return `
    <header class="navbar">
      <div class="navbar-container">
        <a href="#dashboard" class="navbar-brand">
          <div class="logo-icon">🎯</div>
          <span class="brand-title">AI Mock Interview</span>
          <span class="brand-badge">Student Coach</span>
        </a>
        <div class="navbar-links">
          <button onclick="navigate('dashboard')" class="nav-link ${isDashboard ? 'active' : ''}" style="background:none;border:none;cursor:pointer;">
            Dashboard
          </button>
          <button onclick="navigate('interviews/compare')" class="nav-link ${isCompare ? 'active' : ''}" style="background:none;border:none;cursor:pointer;">
            Compare Sessions
          </button>
          <button onclick="navigate('setup')" class="btn btn-primary btn-sm ${isSetup ? 'active' : ''}">
            + Start Interview
          </button>
          <div class="user-profile-badge">
            <span class="user-avatar">${(state.user.name || 'S').charAt(0).toUpperCase()}</span>
            <span class="user-name">${state.user.name}</span>
          </div>
          <button onclick="logout()" class="btn btn-outline btn-sm">Logout</button>
        </div>
      </div>
    </header>
  `;
}

// Login View
function renderLogin() {
  return `
    <div class="auth-container">
      <div class="auth-card">
        <div class="auth-header">
          <div class="auth-icon">🎯</div>
          <h2>Welcome Back</h2>
          <p>Sign in to continue your placement interview preparation.</p>
        </div>

        ${state.error ? `<div class="upload-error-text" style="padding:0.75rem;background:#fef2f2;border:1px solid #fecaca;border-radius:6px;margin-bottom:1rem;">⚠️ ${state.error}</div>` : ''}

        <form id="loginForm" class="auth-form" onsubmit="handleLoginSubmit(event)">
          <div class="form-group">
            <label>Email Address</label>
            <input id="loginEmail" type="email" placeholder="student@university.edu" required />
          </div>

          <div class="form-group">
            <label>Password</label>
            <input id="loginPassword" type="password" placeholder="••••••••" required />
          </div>

          <button type="submit" class="btn btn-primary btn-block btn-lg" id="loginBtn">
            Sign In to Dashboard
          </button>
        </form>

        <div class="auth-footer">
          <p>Don't have an account yet? <a href="#register" class="auth-link">Create Student Account</a></p>
        </div>
      </div>
    </div>
  `;
}

// Register View
function renderRegister() {
  return `
    <div class="auth-container">
      <div class="auth-card">
        <div class="auth-header">
          <div class="auth-icon">🚀</div>
          <h2>Create Student Account</h2>
          <p>Master placement interviews with an AI-driven multi-modal coach.</p>
        </div>

        ${state.error ? `<div class="upload-error-text" style="padding:0.75rem;background:#fef2f2;border:1px solid #fecaca;border-radius:6px;margin-bottom:1rem;">⚠️ ${state.error}</div>` : ''}

        <form id="registerForm" class="auth-form" onsubmit="handleRegisterSubmit(event)">
          <div class="form-group">
            <label>Full Name</label>
            <input id="regName" type="text" placeholder="e.g. Alex Johnson" required />
          </div>

          <div class="form-group">
            <label>Email Address</label>
            <input id="regEmail" type="email" placeholder="student@university.edu" required />
          </div>

          <div class="form-group">
            <label>Password (min 6 characters)</label>
            <input id="regPassword" type="password" placeholder="••••••••" required />
          </div>

          <div class="form-group">
            <label>Confirm Password</label>
            <input id="regConfirmPassword" type="password" placeholder="••••••••" required />
          </div>

          <button type="submit" class="btn btn-primary btn-block btn-lg" id="registerBtn">
            Register & Start Preparing
          </button>
        </form>

        <div class="auth-footer">
          <p>Already registered? <a href="#login" class="auth-link">Sign In here</a></p>
        </div>
      </div>
    </div>
  `;
}

// Dashboard View
function renderDashboard() {
  const stats = state.stats;
  const prog = state.progress;
  const avg = stats && stats.average_score !== null ? `${stats.average_score}%` : 'N/A';
  const latest = stats && stats.latest_score !== null ? `${stats.latest_score}%` : 'N/A';
  const best = prog && prog.best_score !== null ? `${prog.best_score}%` : 'N/A';
  const imp = prog && prog.total_score_improvement !== null ? (prog.total_score_improvement >= 0 ? `+${prog.total_score_improvement}%` : `${prog.total_score_improvement}%`) : '—';

  return `
    <div class="dashboard-container">
      <section class="welcome-banner">
        <div class="welcome-content">
          <h1 class="welcome-title">Welcome, <span class="highlight-text">${state.user?.name || 'Student'}</span> 👋</h1>
          <p class="welcome-subtitle">Practice AI voice placement interviews, review multi-modal performance analytics, and follow your personalized roadmap.</p>
        </div>
        <div class="welcome-actions">
          <button onclick="navigate('setup')" class="btn btn-primary btn-lg shadow-glow">
            <span style="font-size:1.2rem;">⚡</span> Start New Interview
          </button>
        </div>
      </section>

      ${state.error ? `<div class="upload-error-text" style="padding:0.75rem;background:#fef2f2;border:1px solid #fecaca;border-radius:6px;margin-bottom:1.5rem;">⚠️ ${state.error}</div>` : ''}

      <section class="stats-grid">
        <div class="stat-card">
          <div class="stat-card-header">
            <span class="stat-card-title">Total Interviews</span>
            <div class="stat-card-icon" style="color:#2563eb;background:#2563eb15;">📊</div>
          </div>
          <div class="stat-card-value">${stats?.total_interviews ?? 0}</div>
          <div class="stat-card-subtitle">All created practice sessions</div>
        </div>

        <div class="stat-card">
          <div class="stat-card-header">
            <span class="stat-card-title">Average Score</span>
            <div class="stat-card-icon" style="color:#16a34a;background:#16a34a15;">🎯</div>
          </div>
          <div class="stat-card-value">${avg}</div>
          <div class="stat-card-subtitle">Across completed assessments</div>
        </div>

        <div class="stat-card">
          <div class="stat-card-header">
            <span class="stat-card-title">Best Score</span>
            <div class="stat-card-icon" style="color:#d97706;background:#d9770615;">🏆</div>
          </div>
          <div class="stat-card-value">${best}</div>
          <div class="stat-card-subtitle">Highest evaluation achieved</div>
        </div>

        <div class="stat-card">
          <div class="stat-card-header">
            <span class="stat-card-title">Score Improvement</span>
            <div class="stat-card-icon" style="color:#9333ea;background:#9333ea15;">📈</div>
          </div>
          <div class="stat-card-value">${imp}</div>
          <div class="stat-card-subtitle">Longitudinal progress trajectory</div>
        </div>
      </section>

      ${prog && prog.trend_data && prog.trend_data.length > 0 ? `
        <section class="progress-trends-card" style="margin-bottom:2.5rem;">
          <div class="section-header">
            <div>
              <h2 class="section-title">📈 Longitudinal Progress Trends</h2>
              <p class="section-subtitle">Score improvement trajectories across completed mock interviews</p>
            </div>
            ${prog.trend_data.length >= 2 ? `
              <button onclick="navigate('interviews/compare')" class="btn btn-secondary btn-sm">
                🔍 Compare Sessions Side-by-Side
              </button>
            ` : ''}
          </div>

          <div class="progress-trajectory-grid">
            ${prog.trend_data.map(item => `
              <div class="trend-point-card">
                <div class="trend-card-top">
                  <span class="session-index-pill">Session #${item.interview_id}</span>
                  <span class="trend-date">${formatDate(item.date)}</span>
                </div>
                <div class="trend-score-large">${item.overall_score}%</div>
                <div class="trend-company-name">${item.company_name ? `🏢 ${item.company_name}` : '🌐 General Mock'}</div>
                <div class="sub-scores-mini-row">
                  <span>Tech: ${item.technical_score}%</span>
                  <span>Comm: ${item.communication_score}%</span>
                  <span>Fluency: ${item.fluency_score}%</span>
                </div>
                <button onclick="navigate('interviews/${item.interview_id}/report')" class="btn btn-outline btn-sm btn-block" style="margin-top:0.75rem;">
                  📊 View Full Report
                </button>
              </div>
            `).join('')}
          </div>

          ${prog.category_trends && prog.category_trends.length > 0 ? `
            <div class="category-trends-row">
              ${prog.category_trends.map(c => `
                <div class="category-delta-box">
                  <span class="cat-name">${c.category_name}</span>
                  <span class="cat-scores">${c.initial_score}% ➔ ${c.latest_score}%</span>
                  <span class="cat-delta ${c.delta >= 0 ? 'pos' : 'neg'}">${c.delta >= 0 ? `+${c.delta}%` : `${c.delta}%`}</span>
                </div>
              `).join('')}
            </div>
          ` : ''}
        </section>
      ` : ''}

      <section class="interviews-section">
        <div class="section-header">
          <div>
            <h2 class="section-title">Interview History & Sessions</h2>
            <p className="section-subtitle">Manage your active and completed mock interviews</p>
          </div>
          <button onclick="fetchDashboardData()" class="btn btn-secondary btn-sm">🔄 Refresh</button>
        </div>

        ${state.loading ? `
          <div style="text-align:center;padding:3rem;">
            <div class="spinner" style="width:2rem;height:2rem;margin:0 auto 1rem;"></div>
            <p style="color:#64748b;">Loading your interview sessions...</p>
          </div>
        ` : state.interviews.length === 0 ? `
          <div class="empty-state-card">
            <div class="empty-icon">📁</div>
            <h3>No Mock Interviews Found</h3>
            <p>You haven't initiated any interview sessions yet. Start your first session by choosing a company or general mock interview.</p>
            <button onclick="navigate('setup')" class="btn btn-primary btn-md" style="margin-top:1rem;">
              Create Your First Interview
            </button>
          </div>
        ` : `
          <div class="interviews-grid">
            ${state.interviews.map(i => {
              const isCompany = i.interview_type === 'company';
              const targetAction = i.status === 'completed' 
                ? `<button onclick="navigate('interviews/${i.id}/report')" class="btn btn-outline btn-block">📊 View Performance Report</button>`
                : (i.status === 'ready' || i.status === 'in_progress'
                  ? `<button onclick="navigate('interviews/${i.id}/session')" class="btn btn-outline btn-block">${i.status === 'ready' ? '🚀 Launch Voice Session' : '🎙️ Resume Voice Interview'}</button>`
                  : `<button onclick="navigate('interviews/${i.id}')" class="btn btn-outline btn-block">⚙️ Continue Setup</button>`);

              return `
                <div class="interview-card">
                  <div>
                    <div class="interview-card-header">
                      <div class="interview-card-type">
                        <span class="badge-type ${isCompany ? 'badge-company' : 'badge-general'}">
                          ${isCompany ? '🏢 Company Mock' : '🌐 General Mock'}
                        </span>
                        ${getStatusBadge(i.status)}
                      </div>
                      <div class="interview-card-date">${formatDate(i.created_at)}</div>
                    </div>
                    <div class="interview-card-body">
                      <h3 class="interview-card-title">
                        ${isCompany ? `<span class="company-name">${i.company_name}</span> • <span>${i.job_role}</span>` : 'Comprehensive Placement Mock Interview'}
                      </h3>
                      <div class="interview-docs-indicators">
                        <span class="doc-indicator ${i.is_resume_uploaded ? 'uploaded' : 'missing'}">
                          📄 Resume: ${i.resume_original_name || (i.is_resume_uploaded ? 'Uploaded' : 'Missing')}
                        </span>
                        ${isCompany ? `
                          <span class="doc-indicator ${i.is_jd_uploaded ? 'uploaded' : 'missing'}">
                            📋 JD: ${i.jd_original_name || (i.is_jd_uploaded ? 'Uploaded' : 'Missing')}
                          </span>
                        ` : ''}
                      </div>

                      ${i.overall_score !== null ? `
                        <div class="interview-score-box">
                          <div class="score-main">
                            <span class="score-label">Overall Evaluation:</span>
                            <span class="score-value">${i.overall_score}%</span>
                          </div>
                          <div class="score-sub-metrics">
                            ${i.technical_score !== null ? `<span>Tech: ${i.technical_score}%</span>` : ''}
                            ${i.communication_score !== null ? `<span>Comm: ${i.communication_score}%</span>` : ''}
                          </div>
                        </div>
                      ` : ''}
                    </div>
                  </div>
                  <div class="interview-card-footer">
                    ${targetAction}
                  </div>
                </div>
              `;
            }).join('')}
          </div>
        `}
      </section>
    </div>
  `;
}

// Setup View
function renderSetup() {
  return `
    <div class="setup-container">
      <div class="setup-header">
        <span class="setup-badge">Step 1: Configuration</span>
        <h1 class="setup-title">Setup New Mock Interview</h1>
        <p class="setup-subtitle">Configure your interview parameters and provide required documentation to tailor the AI questions.</p>
      </div>

      ${state.error ? `<div class="upload-error-text" style="padding:0.75rem;background:#fef2f2;border:1px solid #fecaca;border-radius:6px;margin-bottom:1.5rem;">⚠️ ${state.error}</div>` : ''}

      <form id="setupForm" class="setup-form" onsubmit="handleSetupSubmit(event)">
        <div class="form-section">
          <label class="section-label">Choose Interview Type</label>
          <div class="interview-type-selector">
            <div id="typeCompanyCard" class="type-option-card selected" onclick="selectType('company')">
              <div class="type-card-radio">
                <input type="radio" name="setup_type" id="typeCompany" checked />
              </div>
              <div class="type-card-content">
                <div class="type-card-icon">🏢</div>
                <h3 class="type-card-title">Company Mock Interview</h3>
                <p class="type-card-desc">Tailored to a specific hiring company and job description. Aligns questions with target role requirements.</p>
                <div class="type-card-tags">
                  <span class="pill">Requires Company & Role</span>
                  <span class="pill">Requires JD + Resume</span>
                </div>
              </div>
            </div>

            <div id="typeGeneralCard" class="type-option-card" onclick="selectType('general')">
              <div class="type-card-radio">
                <input type="radio" name="setup_type" id="typeGeneral" />
              </div>
              <div class="type-card-content">
                <div class="type-card-icon">🌐</div>
                <h3 class="type-card-title">General Mock Interview</h3>
                <p class="type-card-desc">Comprehensive assessment across core Computer Science, problem-solving, and resume projects.</p>
                <div class="type-card-tags">
                  <span class="pill">Quick Start</span>
                  <span class="pill">Requires Resume only</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="form-section">
          <label class="section-label">Choose Interview Duration</label>
          <div class="duration-selector-grid">
            ${[
              { val: 1, label: '1 min', desc: '1 minute — TESTING' },
              { val: 20, label: '20 mins', desc: '20 minutes' },
              { val: 30, label: '30 mins', desc: '30 minutes (Standard)' },
              { val: 45, label: '45 mins', desc: '45 minutes' },
              { val: 60, label: '60 mins', desc: '60 minutes' },
              { val: 90, label: '90 mins', desc: '90 minutes' },
            ].map(opt => `
              <div class="duration-card ${selectedDuration === opt.val ? 'selected' : ''}" data-duration="${opt.val}" onclick="selectDuration(${opt.val})">
                <div class="duration-card-radio">
                  <input type="radio" name="setup_duration" ${selectedDuration === opt.val ? 'checked' : ''} />
                </div>
                <div class="duration-card-content">
                  <span class="duration-tag">${opt.label}</span>
                  <span class="duration-name">${opt.desc}</span>
                </div>
              </div>
            `).join('')}
          </div>
        </div>

        <div id="companyFields" class="form-section company-fields-box">
          <h3 class="sub-section-title">Company & Target Role Details</h3>
          <div class="form-grid-2">
            <div class="form-group">
              <label>Target Company Name *</label>
              <input id="setupCompany" type="text" placeholder="e.g. Google, TCS, Amazon" />
            </div>
            <div class="form-group">
              <label>Job Role / Designation *</label>
              <input id="setupRole" type="text" placeholder="e.g. Software Engineer (SDE 1)" />
            </div>
          </div>

          <div style="margin-top:1.25rem;">
            <label class="section-label">Job Description (Paste or Upload)</label>
            <textarea
              id="setupJdText"
              placeholder="Paste the full Job Description text here (preferred)"
              rows="6"
              style="width:100%;padding:0.75rem;border-radius:6px;border:1px solid #e2e8f0;margin-bottom:0.75rem;"
            ></textarea>
            <div class="file-dropzone" onclick="document.getElementById('jdFileInput').click()">
              <input id="jdFileInput" type="file" accept=".pdf,.docx" style="display:none" onchange="handleFileChange(this, 'jd')" />
              <div class="dropzone-icon">📋</div>
              <p class="dropzone-primary-text" id="jdFileLabel"><strong>Or upload Job Description</strong> (PDF or DOCX, max 10MB)</p>
            </div>
          </div>
        </div>

        <div class="form-section">
          <label class="file-uploader-label">Upload Candidate Resume *</label>
          <div class="file-dropzone" onclick="document.getElementById('resumeFileInput').click()">
            <input id="resumeFileInput" type="file" accept=".pdf,.docx" style="display:none" onchange="handleFileChange(this, 'resume')" />
            <div class="dropzone-icon">📄</div>
            <p class="dropzone-primary-text" id="resumeFileLabel"><strong>Click to upload Resume</strong> (PDF or DOCX, max 10MB)</p>
          </div>
        </div>

        <div id="setupProgress" class="submission-progress-box" style="display:none;">
          <div style="display:flex;align-items:center;gap:0.75rem;">
            <div class="spinner" style="width:1.2rem;height:1.2rem;"></div>
            <span id="setupProgressText" style="font-size:0.9rem;font-weight:600;color:#1e40af;">Creating interview session...</span>
          </div>
        </div>

        <div class="form-actions-row">
          <button type="button" class="btn btn-secondary" onclick="navigate('dashboard')">Cancel</button>
          <button type="submit" class="btn btn-primary btn-lg shadow-glow" id="setupSubmitBtn">
            Create Session & Upload Documents 🚀
          </button>
        </div>
      </form>
    </div>
  `;
}

// Interview Detail View
function renderInterviewDetail() {
  const i = state.activeInterview;
  if (!i) {
    return `<div style="padding:3rem;text-align:center;"><div class="spinner" style="width:2rem;height:2rem;margin:auto;"></div></div>`;
  }
  const isCompany = i.interview_type === 'company';
  const statusData = i.statusData;

  return `
    <div class="detail-container">
      <div class="detail-header-card">
        <div class="detail-header-top">
          <a href="#dashboard" class="back-link">← Back to Dashboard</a>
          ${getStatusBadge(i.status)}
        </div>
        <h1 class="detail-title">
          ${isCompany ? `${i.company_name} — ${i.job_role}` : 'General Placement Mock Interview'}
        </h1>
        <p class="detail-meta">
          Session #${i.id} • Created on ${formatDate(i.created_at)} • Type: ${isCompany ? 'Company Specific' : 'General'}
        </p>
      </div>

      <div class="detail-grid">
        <div class="detail-card">
          <h2 class="detail-card-title">📁 Document Verification</h2>
          <div class="doc-check-list">
            <div class="doc-check-item">
              <div class="doc-check-icon">${i.is_resume_uploaded ? '✅' : '❌'}</div>
              <div class="doc-check-info">
                <strong>Candidate Resume</strong>
                <span>${i.resume_original_name || (i.is_resume_uploaded ? 'Uploaded' : 'Pending upload')}</span>
              </div>
            </div>

            ${isCompany ? `
              <div class="doc-check-item">
                <div class="doc-check-icon">${i.is_jd_uploaded ? '✅' : '❌'}</div>
                <div class="doc-check-info">
                  <strong>Job Description (JD)</strong>
                  <span>${i.jd_original_name || (i.is_jd_uploaded ? 'Uploaded' : 'Pending upload')}</span>
                </div>
              </div>
            ` : ''}
          </div>

          <div class="status-callout" style="margin-top:1.5rem;">
            <strong>Session Status:</strong> ${i.status === 'completed' ? 'Interview Completed. Performance report ready.' : (statusData?.message || 'Ready for AI interview phase.')}
          </div>
        </div>

        <div class="detail-card">
          <h2 class="detail-card-title">🤖 AI Interview Coach</h2>
          <p style="color:#64748b;font-size:0.95rem;line-height:1.5;">
            This session is configured with your uploaded documents. The AI Voice Engine will ask questions using Text-to-Speech (TTS), record your spoken responses, analyze speech fluency and technical correctness, and generate adaptive dynamic follow-ups.
          </p>

          <div style="margin-top:1.5rem;">
            ${i.status === 'completed' ? `
              <button class="btn btn-primary btn-block btn-lg shadow-glow" onclick="navigate('interviews/${i.id}/report')">
                📊 View Full Performance Report ➔
              </button>
            ` : `
              <button class="btn btn-primary btn-block btn-lg shadow-glow" ${!statusData?.is_ready ? 'disabled' : ''} onclick="navigate('interviews/${i.id}/session')">
                ${i.status === 'in_progress' ? '🎙️ Resume AI Voice Interview Session ➔' : (statusData?.is_ready ? '🎙️ Launch AI Voice Interview Session ➔' : '⚠️ Upload Required Documents First')}
              </button>
            `}
          </div>
        </div>
      </div>
    </div>
  `;
}

// AI Voice Interview Session View
function renderInterviewSession() {
  const i = state.activeInterview;
  if (!i || state.loading) {
    return `<div style="padding:4rem;text-align:center;"><div class="spinner" style="width:2.5rem;height:2.5rem;margin:auto 1rem;"></div><p style="margin-top:1rem;color:#64748b;">Preparing AI Interview Session...</p></div>`;
  }

  if (state.sessionCompleted) {
    return `
      <div class="session-completed-card">
        <div class="completed-icon">🎉</div>
        <h1 class="completed-title">Mock Interview Completed!</h1>
        <p class="completed-subtitle">Great job! Your interview session has terminated and multi-modal evaluations are finalized.</p>
        <div class="completed-summary-box">
          <h3>Session Summary (Session #${i.id})</h3>
          <p><strong>Candidate:</strong> ${state.user?.name || 'Candidate'}</p>
          <p><strong>Interview Type:</strong> ${i.interview_type === 'company' ? `${i.company_name} — ${i.job_role}` : 'General Placement Mock'}</p>
          <p><strong>Duration Selected:</strong> ${i.duration_minutes || 30} minutes</p>
          <p><strong>Questions Evaluated:</strong> ${state.questions.length} questions</p>
        </div>
        <div style="margin-top:2rem;display:flex;gap:1rem;justify-content:center;flex-wrap:wrap;">
          <button onclick="navigate('dashboard')" class="btn btn-primary btn-lg">Return to Dashboard</button>
          <button onclick="navigate('interviews/${i.id}')" class="btn btn-secondary btn-lg">View Session Details</button>
          <button onclick="navigate('interviews/${i.id}/report')" class="btn btn-primary btn-lg shadow-glow">📊 View Performance Report</button>
        </div>
      </div>
    `;
  }

  const isCompany = i.interview_type === 'company';
  const q = state.currentQuestion;

  return `
    <div class="interview-session-container">
      <div class="session-topbar">
        <div class="session-info">
          <span class="session-type-pill">${isCompany ? `🏢 ${i.company_name} • ${i.job_role}` : '🌐 General Placement Interview'}</span>
          <span class="question-counter-badge">Question ${state.currentQuestionIndex + 1} ${q?.source === 'FOLLOW_UP' ? '(Dynamic Follow-up)' : `of ${state.questions.length}`}</span>
          <span id="sessionTimerBadge" class="timer-badge ${state.timeLeft !== null && state.timeLeft <= 60 ? 'timer-warning pulse-fast' : ''}">
            ⏱️ ${formatDuration(state.timeLeft !== null ? state.timeLeft : (i.duration_minutes || 30) * 60)}
          </span>
        </div>
        <div class="session-actions">
          <button onclick="toggleCamera()" class="btn btn-sm ${state.cameraActive ? 'btn-danger' : 'btn-secondary'}">
            ${state.cameraActive ? '📷 Turn Off Camera' : '📷 Enable Camera'}
          </button>
          <button onclick="navigate('dashboard')" class="btn btn-outline btn-sm">Exit Session</button>
        </div>
      </div>

      ${state.error ? `<div class="upload-error-text" style="padding:0.75rem;background:#fef2f2;border:1px solid #fecaca;border-radius:6px;margin-bottom:1.25rem;">⚠️ ${state.error}</div>` : ''}

      ${state.isFollowUpAlert ? `
        <div class="followup-alert-banner">
          <span>⚡ <strong>Adaptive Follow-up:</strong> The AI interviewer is probing deeper based on your previous response!</span>
        </div>
      ` : ''}

      <div class="session-grid">
        <div class="session-main-panel">
          <div class="ai-interviewer-card">
            <div class="ai-avatar-row">
              <div class="ai-avatar ${state.isSpeaking ? 'speaking-pulse' : ''}">🤖</div>
              <div class="ai-avatar-meta">
                <h3>AI Technical Interviewer</h3>
                <span class="ai-status-indicator">${state.isSpeaking ? '🔊 Speaking question...' : '👂 Listening to candidate'}</span>
              </div>
            </div>

            <div class="question-display-box">
              <div class="question-tags">
                <span class="tag-category">${q?.category || 'TECHNICAL'}</span>
                <span class="tag-difficulty ${(q?.difficulty || 'medium').toLowerCase()}">${q?.difficulty || 'MEDIUM'}</span>
                <span class="tag-source">Source: ${q?.source || 'GENERAL'}</span>
              </div>

              <h2 class="active-question-text">${q?.question || 'Please describe your background.'}</h2>

              ${q?.expected_focus && q.expected_focus.length > 0 ? `
                <div class="expected-focus-box"><strong>Expected Focus:</strong> ${q.expected_focus.join(' • ')}</div>
              ` : ''}

              <div class="tts-controls-row">
                <button onclick="speakQuestion('${(q?.question || '').replace(/'/g, "\\'")}')" class="btn btn-outline btn-sm">🔊 Repeat Question</button>
                ${state.isSpeaking ? `<button onclick="stopSpeaking()" class="btn btn-outline btn-sm">⏹️ Stop Audio</button>` : ''}
              </div>
            </div>
          </div>

          <div class="answer-card">
            <div class="answer-header">
              <h3>Your Response</h3>
              ${state.isRecording ? `<span class="recording-badge pulse" id="recordingTimerText">🔴 Recording (${state.recordingSeconds}s)</span>` : ''}
            </div>

            <textarea
              id="answerTextInput"
              class="answer-textarea"
              placeholder="Click 'Start Spoken Answer' to speak via microphone, or type your answer directly..."
              rows="4"
            >${state.transcript}</textarea>

            <div class="answer-controls-row">
              ${!state.isRecording ? `
                <button onclick="startRecording()" class="btn btn-primary btn-lg shadow-glow" ${state.loading ? 'disabled' : ''}>
                  🎙️ Start Spoken Answer
                </button>
              ` : `
                <button onclick="stopRecording()" class="btn btn-danger btn-lg pulse">
                  ⏹️ Stop & Submit Spoken Answer
                </button>
              `}

              <button onclick="handleManualSubmit()" class="btn btn-secondary btn-lg" ${state.isRecording || state.loading ? 'disabled' : ''}>
                ${state.loading ? 'Evaluating...' : 'Submit Text Answer ➔'}
              </button>
            </div>
          </div>

          ${state.lastFeedback ? `
            <div class="live-feedback-card">
              <h3 class="feedback-title">📊 Multi-Modal Analysis on Previous Answer</h3>
              <div class="feedback-scores-grid">
                <div class="score-badge-box"><span class="score-label">Technical</span><span class="score-val">${state.lastFeedback.technical.technical_score}%</span></div>
                <div class="score-badge-box"><span class="score-label">Correctness</span><span class="score-val">${state.lastFeedback.technical.correctness}%</span></div>
                <div class="score-badge-box"><span class="score-label">Fluency</span><span class="score-val">${state.lastFeedback.fluency.fluency_score}%</span></div>
                <div class="score-badge-box"><span class="score-label">WPM</span><span class="score-val">${state.lastFeedback.fluency.wpm}</span></div>
                <div class="score-badge-box"><span class="score-label">Communication</span><span class="score-val">${state.lastFeedback.communication.communication_score}%</span></div>
                <div class="score-badge-box"><span class="score-label">Filler Words</span><span class="score-val">${state.lastFeedback.fluency.filler_word_count}</span></div>
              </div>
              <p class="feedback-text"><strong>Technical Assessment:</strong> ${state.lastFeedback.technical.feedback}</p>
              <p class="feedback-text"><strong>Communication Assessment:</strong> ${state.lastFeedback.communication.feedback}</p>
            </div>
          ` : ''}
        </div>

        <div class="session-side-panel">
          <div class="webcam-card">
            <h3>Candidate Camera Feed</h3>
            <div class="webcam-viewfinder">
              ${state.cameraActive ? `
                <video id="webcamVideo" autoplay playsinline muted class="webcam-video"></video>
              ` : `
                <div class="webcam-placeholder">
                  <span class="camera-icon">📷</span>
                  <p>Webcam is currently disabled.</p>
                  <button onclick="toggleCamera()" class="btn btn-secondary btn-sm" style="margin-top:0.5rem;">Enable Camera</button>
                </div>
              `}
            </div>

            ${state.cameraActive ? `
              <div class="vision-metrics-box">
                <h4>Observable Vision Indicators</h4>
                <div id="visionMetricsDisplay">
                  <div class="metric-row"><span>Face Presence:</span><strong>Syncing...</strong></div>
                  <div class="metric-row"><span>Eye-Contact Proxy:</span><strong>--</strong></div>
                  <div class="metric-row"><span>Posture Score:</span><strong>--</strong></div>
                  <div class="metric-row"><span>Expression:</span><strong>Neutral</strong></div>
                </div>
              </div>
            ` : ''}
          </div>

          <div class="guidance-card">
            <h3>Placement Interview Tips</h3>
            <ul class="tips-list">
              <li>Structure answers using <strong>STAR</strong> (Situation, Task, Action, Result).</li>
              <li>State technical trade-offs explicitly (e.g. time vs space complexity).</li>
              <li>Maintain steady vocal pacing around 120–150 words per minute.</li>
              <li>Face the camera directly to ensure optimal posture evaluation.</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  `;
}

// Master Prompt 3: Performance Report View
function renderInterviewReport() {
  const r = state.activeReport;
  if (!r || state.loading) {
    return `<div style="padding:4rem;text-align:center;"><div class="spinner" style="width:2.5rem;height:2.5rem;margin:auto 1rem;"></div><p style="margin-top:1rem;color:#64748b;">Loading performance report...</p></div>`;
  }

  const isCompany = r.interview_type === 'company';
  const sb = r.score_breakdown;
  const dims = sb?.dimensions || {};
  const tab = state.reportTab || 'overview';

  return `
    <div class="report-container">
      <div class="report-header-card">
        <div class="report-header-top">
          <a href="#dashboard" class="back-link">← Back to Dashboard</a>
          <div class="header-actions-row">
            <button onclick="navigate('interviews/compare?second_id=${r.interview_id}')" class="btn btn-outline btn-sm">📊 Compare With Previous</button>
            <button onclick="window.print()" class="btn btn-secondary btn-sm">🖨️ Print / Save PDF</button>
          </div>
        </div>

        <div class="report-title-row">
          <div>
            <span class="report-badge">Official Assessment</span>
            <h1 class="report-main-title">${isCompany ? `${r.company_name} — ${r.job_role}` : 'General Placement Mock Interview'}</h1>
            <p class="report-meta-text">Candidate Performance Evaluation • Session #${r.interview_id} • Evaluated via Weighted Multi-Modal Scoring Algorithm</p>
          </div>
          <div class="overall-score-display">
            <span class="score-number">${r.overall_score}</span>
            <span class="score-max">/ 100</span>
            <div class="readiness-badge-main">${r.readiness_level}</div>
          </div>
        </div>

        <div class="report-tabs-bar">
          <button class="report-tab-btn ${tab === 'overview' ? 'active' : ''}" onclick="state.reportTab='overview';render();">
            📊 Performance Overview
          </button>
          <button class="report-tab-btn ${tab === 'questions' ? 'active' : ''}" onclick="state.reportTab='questions';render();">
            💬 Question Breakdown (${r.question_breakdowns?.length || 0})
          </button>
          <button class="report-tab-btn ${tab === 'roadmap' ? 'active' : ''}" onclick="state.reportTab='roadmap';render();">
            🎯 5-Phase Roadmap (${r.roadmap?.phases?.length || 0} Phases)
          </button>
        </div>
      </div>

      ${tab === 'overview' ? `
        <div class="report-tab-content">
          <div class="report-section-card">
            <h2 class="section-heading">📝 Executive Summary</h2>
            <p class="summary-paragraph">${r.summary_text}</p>
          </div>

          <div class="report-section-card">
            <h2 class="section-heading">⚖️ Transparent Multi-Modal Scoring Matrix</h2>
            <p class="section-subtext">The Weighted Multi-Modal Interview Scoring Algorithm mathematically normalizes independent speech, conceptual, and vision dimensions into a unified score.</p>
            <div class="table-responsive">
              <table class="scoring-table">
                <thead>
                  <tr>
                    <th>Evaluation Dimension</th>
                    <th>Measured Score</th>
                    <th>Standard Weight</th>
                    <th>Contribution</th>
                    <th>Modality Status & Notes</th>
                  </tr>
                </thead>
                <tbody>
                  ${Object.entries(dims).map(([k, d]) => `
                    <tr class="${!d.is_available ? 'row-unavailable' : ''}">
                      <td><strong>${k.replace('_', ' ').toUpperCase()}</strong></td>
                      <td>${d.is_available ? `<span class="badge-score-pill">${d.raw_score}%</span>` : `<span class="badge-unavailable">Unavailable</span>`}</td>
                      <td>${Math.round(d.weight * 100)}%</td>
                      <td><strong>${d.is_available ? `+${d.contribution} pts` : '—'}</strong></td>
                      <td class="note-cell">${d.status_note || 'Measured successfully.'}</td>
                    </tr>
                  `).join('')}
                  <tr class="table-summary-row">
                    <td><strong>FINAL OVERALL SCORE</strong></td>
                    <td colspan="2"><strong>Sum of Available Weights: ${Math.round((sb?.available_weights_sum || 1) * 100)}%</strong></td>
                    <td><strong>${r.overall_score} / 100</strong></td>
                    <td><strong>${r.readiness_level}</strong></td>
                  </tr>
                </tbody>
              </table>
            </div>

            ${sb?.unavailable_modalities && sb.unavailable_modalities.length > 0 ? `
              <div class="missing-modality-callout">
                ℹ️ <strong>Missing-Modality Normalization Active:</strong> ${sb.unavailable_modalities.join(', ')} were unavailable in this testing session. The scoring algorithm dynamically normalized remaining weights to prevent unfair candidate penalty.
              </div>
            ` : ''}
          </div>

          <div class="grid-2-col">
            <div class="report-section-card border-green">
              <h2 class="section-heading text-green">✅ Verified Strengths</h2>
              <ul class="strengths-list">
                ${(r.strengths || []).map(s => `<li><strong>✓</strong> ${s}</li>`).join('')}
              </ul>
            </div>

            <div class="report-section-card border-amber">
              <h2 class="section-heading text-amber">⚠️ Areas for Growth</h2>
              <ul class="weaknesses-list">
                ${(r.weaknesses || []).map(w => `<li><strong>⚠</strong> ${w}</li>`).join('')}
              </ul>
            </div>
          </div>

          ${r.frequently_observed_mistakes && r.frequently_observed_mistakes.length > 0 ? `
            <div class="report-section-card">
              <h2 class="section-heading">🔍 Frequently Observed Mistakes</h2>
              <div class="mistakes-grid">
                ${r.frequently_observed_mistakes.map(m => `
                  <div class="mistake-card">
                    <div class="mistake-header">
                      <span class="mistake-title">${m.mistake_type}</span>
                      <span class="severity-badge ${(m.severity || 'medium').toLowerCase()}">${m.severity} Severity</span>
                    </div>
                    <p class="mistake-desc">${m.description}</p>
                    <div class="mistake-remediation"><strong>💡 Recommended Fix:</strong> ${m.remediation_tip}</div>
                  </div>
                `).join('')}
              </div>
            </div>
          ` : ''}
        </div>
      ` : ''}

      ${tab === 'questions' ? `
        <div class="report-tab-content">
          <div class="report-section-card">
            <h2 class="section-heading">💬 Detailed Question & Answer Analysis</h2>
            <p class="section-subtext">Review specific scores, candidate transcripts, and technical feedback for each interview question.</p>
            <div class="questions-review-list">
              ${(r.question_breakdowns || []).map(q => `
                <div class="question-review-card">
                  <div class="question-review-header">
                    <span class="question-number-tag">Q${q.order_number}</span>
                    <span class="tag-category">${q.category}</span>
                    <span class="tag-difficulty ${(q.difficulty || 'medium').toLowerCase()}">${q.difficulty}</span>
                    <div class="question-scores-badges">
                      <span class="badge-metric">Tech: ${q.technical_score}%</span>
                      <span class="badge-metric">Comm: ${q.communication_score}%</span>
                      <span class="badge-metric">Fluency: ${q.fluency_score}%</span>
                    </div>
                  </div>
                  <h3 class="review-question-text">${q.question}</h3>
                  <div class="candidate-answer-box">
                    <strong>Spoken Response:</strong>
                    <p>"${q.candidate_answer}"</p>
                  </div>
                  <div class="assessor-feedback-box">
                    <strong>💡 AI Evaluation & Feedback:</strong>
                    <p>${q.feedback}</p>
                  </div>
                </div>
              `).join('')}
            </div>
          </div>
        </div>
      ` : ''}

      ${tab === 'roadmap' ? `
        <div class="report-tab-content">
          <div class="report-section-card">
            <h2 class="section-heading">🎯 5-Phase Personalized Improvement Roadmap</h2>
            <p class="section-subtext">Actionable, measurable milestones tailored to close your identified skill gaps and elevate placement drive performance.</p>
            <div class="roadmap-timeline">
              ${(r.roadmap?.phases || []).map(p => `
                <div class="roadmap-phase-card">
                  <div class="phase-header">
                    <span class="phase-pill">Phase ${p.phase_number}</span>
                    <h3 class="phase-title">${p.phase_title}</h3>
                  </div>
                  <p class="phase-objective"><strong>Focus Objective:</strong> ${p.focus_objective}</p>
                  <div class="phase-items-list">
                    ${(p.items || []).map(item => `
                      <div class="roadmap-item-card">
                        <div class="item-header-row">
                          <h4 class="item-area">${item.area}</h4>
                          <span class="priority-badge ${(item.priority || 'medium').toLowerCase()}">${item.priority} Priority</span>
                        </div>
                        <p><strong>Identified Gap:</strong> ${item.problem}</p>
                        <p><strong>Recommended Action:</strong> ${item.recommended_action}</p>
                        <div class="practice-task-box"><strong>🛠️ Practice Task (${item.estimated_duration}):</strong> ${item.practice_task}</div>
                        <div class="measurable-target-box"><strong>🎯 Target Milestone:</strong> ${item.measurable_target}</div>
                      </div>
                    `).join('')}
                  </div>
                </div>
              `).join('')}
            </div>
          </div>
        </div>
      ` : ''}

      <div class="report-bottom-actions">
        <button onclick="navigate('setup')" class="btn btn-primary btn-lg shadow-glow">⚡ Practice Another Mock Interview</button>
        <button onclick="navigate('dashboard')" class="btn btn-secondary btn-lg">Return to Dashboard</button>
      </div>
    </div>
  `;
}

// Master Prompt 3: Interview Comparison View
function renderInterviewCompare() {
  const completed = (state.interviews || []).filter(i => i.status === 'completed' && i.overall_score !== null);
  const comp = state.activeComparison;

  return `
    <div class="report-container">
      <div class="report-header-top" style="margin-bottom:1.5rem;">
        <a href="#dashboard" class="back-link">← Back to Dashboard</a>
      </div>

      <div class="report-header-card">
        <span class="report-badge">Progress Analytics</span>
        <h1 class="report-main-title">Interview Performance Comparison</h1>
        <p class="report-meta-text">Compare two mock interview sessions side-by-side to evaluate placement competency improvements over time.</p>

        <div class="comparison-selector-bar">
          <div class="selector-group">
            <label>Baseline Session (Interview 1):</label>
            <select id="compareSelectFirst" onchange="state.compareFirstId=this.value;fetchComparison(this.value, state.compareSecondId);">
              ${completed.map(i => `<option value="${i.id}" ${state.compareFirstId == i.id ? 'selected' : ''}>#${i.id} - ${i.company_name || 'General'} (${formatDate(i.created_at)}) [${i.overall_score}%]</option>`).join('')}
            </select>
          </div>
          <div class="vs-badge">VS</div>
          <div class="selector-group">
            <label>Recent Session (Interview 2):</label>
            <select id="compareSelectSecond" onchange="state.compareSecondId=this.value;fetchComparison(state.compareFirstId, this.value);">
              ${completed.map(i => `<option value="${i.id}" ${state.compareSecondId == i.id ? 'selected' : ''}>#${i.id} - ${i.company_name || 'General'} (${formatDate(i.created_at)}) [${i.overall_score}%]</option>`).join('')}
            </select>
          </div>
        </div>
      </div>

      ${state.loading ? `
        <div style="padding:3rem;text-align:center;"><div class="spinner" style="width:2rem;height:2rem;margin:auto;"></div></div>
      ` : comp ? `
        <div class="comparison-content">
          <div class="comparison-delta-banner">
            <div class="delta-stat">
              <span class="delta-label">Baseline Score</span>
              <span class="delta-val">${comp.first_overall_score}%</span>
            </div>
            <div class="delta-arrow">➔</div>
            <div class="delta-stat">
              <span class="delta-label">Recent Score</span>
              <span class="delta-val">${comp.second_overall_score}%</span>
            </div>
            <div class="delta-badge-box">
              <span class="overall-delta-pill ${(comp.overall_status || 'unchanged').toLowerCase()}">
                ${comp.overall_delta >= 0 ? `+${comp.overall_delta}%` : `${comp.overall_delta}%`} Overall (${comp.overall_status})
              </span>
            </div>
          </div>

          <div class="grid-3-col" style="margin-bottom:1.5rem;">
            <div class="highlight-card border-green">
              <h3 class="text-green">📈 Improved Competencies</h3>
              <ul>
                ${(comp.improved_areas || []).map(a => `<li>✓ ${a}</li>`).join('')}
              </ul>
            </div>
            <div class="highlight-card border-amber">
              <h3 class="text-amber">📉 Focus Needed</h3>
              <ul>
                ${(comp.declined_areas || []).map(a => `<li>⚠ ${a}</li>`).join('')}
              </ul>
            </div>
            <div class="highlight-card border-blue">
              <h3 class="text-blue">⚖️ Stable Dimensions</h3>
              <ul>
                ${(comp.unchanged_areas || []).map(a => `<li>• ${a}</li>`).join('')}
              </ul>
            </div>
          </div>

          <div class="report-section-card">
            <h2 class="section-heading">📊 Dimension-by-Dimension Breakdown</h2>
            <div class="table-responsive">
              <table class="scoring-table">
                <thead>
                  <tr>
                    <th>Evaluation Dimension</th>
                    <th>Session #${comp.first_interview_id}</th>
                    <th>Session #${comp.second_interview_id}</th>
                    <th>Score Delta (Δ)</th>
                    <th>Trajectory Status</th>
                  </tr>
                </thead>
                <tbody>
                  ${(comp.dimension_comparisons || []).map(d => `
                    <tr>
                      <td><strong>${d.dimension_name}</strong></td>
                      <td>${d.first_score}%</td>
                      <td>${d.second_score}%</td>
                      <td><strong style="color:${d.delta > 0 ? '#16a34a' : (d.delta < 0 ? '#dc2626' : '#64748b')}">${d.delta > 0 ? `+${d.delta}%` : `${d.delta}%`}</strong></td>
                      <td><span class="status-pill ${(d.status || 'unchanged').toLowerCase()}">${d.status}</span></td>
                    </tr>
                  `).join('')}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ` : `
        <div class="empty-state-card"><p>Complete at least 2 interview sessions to view side-by-side performance trajectories.</p></div>
      `}
    </div>
  `;
}

// App Root Renderer
function render() {
  const app = document.getElementById('app');
  if (!app) return;

  let content = '';
  const r = state.route;

  if (!state.token && r !== 'register') {
    content = renderLogin();
  } else if (!state.token && r === 'register') {
    content = renderRegister();
  } else if (r === 'login') {
    content = state.token ? renderDashboard() : renderLogin();
  } else if (r === 'register') {
    content = state.token ? renderDashboard() : renderRegister();
  } else if (r === 'setup') {
    content = renderSetup();
  } else if (r === 'interviews/compare') {
    if (state.interviews.length === 0) fetchDashboardData();
    content = renderInterviewCompare();
  } else if (r.startsWith('interviews/') && r.endsWith('/session')) {
    const id = r.split('/')[1];
    if (!state.activeInterview || state.activeInterview.id != id || state.questions.length === 0) {
      initInterviewSession(id);
    }
    content = renderInterviewSession();
  } else if (r.startsWith('interviews/') && r.endsWith('/report')) {
    const id = r.split('/')[1];
    if (!state.activeReport || state.activeReport.interview_id != id) {
      fetchReport(id);
    }
    content = renderInterviewReport();
  } else if (r.startsWith('interviews/')) {
    const id = r.split('/')[1];
    if (!state.activeInterview || state.activeInterview.id != id) {
      fetchInterviewDetail(id);
    }
    content = renderInterviewDetail();
  } else {
    if (state.interviews.length === 0 && !state.loading && state.stats === null) {
      fetchDashboardData();
    }
    content = renderDashboard();
  }

  app.innerHTML = `
    ${renderNavbar()}
    <main class="main-content">
      ${content}
    </main>
  `;
}

// Handlers
let selectedType = 'company';
let selectedDuration = 30;
let selectedFiles = { resume: null, jd: null };

function selectType(t) {
  selectedType = t;
  const compCard = document.getElementById('typeCompanyCard');
  const genCard = document.getElementById('typeGeneralCard');
  const compFields = document.getElementById('companyFields');
  const compRadio = document.getElementById('typeCompany');
  const genRadio = document.getElementById('typeGeneral');

  if (t === 'company') {
    compCard?.classList.add('selected');
    genCard?.classList.remove('selected');
    if (compFields) compFields.style.display = 'block';
    if (compRadio) compRadio.checked = true;
  } else {
    genCard?.classList.add('selected');
    compCard?.classList.remove('selected');
    if (compFields) compFields.style.display = 'none';
    if (genRadio) genRadio.checked = true;
  }
}

function selectDuration(mins) {
  selectedDuration = mins;
  document.querySelectorAll('.duration-card').forEach(c => {
    if (parseInt(c.getAttribute('data-duration')) === mins) {
      c.classList.add('selected');
      const r = c.querySelector('input[type="radio"]');
      if (r) r.checked = true;
    } else {
      c.classList.remove('selected');
      const r = c.querySelector('input[type="radio"]');
      if (r) r.checked = false;
    }
  });
}

function handleFileChange(input, type) {
  if (input.files && input.files.length > 0) {
    const file = input.files[0];
    selectedFiles[type] = file;
    const label = document.getElementById(`${type}FileLabel`);
    if (label) {
      label.innerHTML = `✅ <strong>Selected:</strong> ${file.name} (${(file.size/1024/1024).toFixed(2)} MB)`;
    }
  }
}

async function handleLoginSubmit(e) {
  e.preventDefault();
  const email = document.getElementById('loginEmail').value.trim();
  const password = document.getElementById('loginPassword').value;
  const btn = document.getElementById('loginBtn');

  state.error = null;
  btn.disabled = true;
  btn.innerText = 'Signing in...';

  try {
    const data = await apiRequest('/api/auth/login', {
      method: 'POST',
      body: { email, password }
    });
    state.token = data.access_token;
    state.user = data.user;
    localStorage.setItem('ai_mock_token', data.access_token);
    localStorage.setItem('ai_mock_user', JSON.stringify(data.user));
    navigate('dashboard');
    fetchDashboardData();
  } catch (err) {
    state.error = err.message;
    btn.disabled = false;
    btn.innerText = 'Sign In to Dashboard';
    render();
  }
}

async function handleRegisterSubmit(e) {
  e.preventDefault();
  const name = document.getElementById('regName').value.trim();
  const email = document.getElementById('regEmail').value.trim();
  const password = document.getElementById('regPassword').value;
  const confirmPassword = document.getElementById('regConfirmPassword').value;
  const btn = document.getElementById('registerBtn');

  state.error = null;
  btn.disabled = true;
  btn.innerText = 'Creating account...';

  try {
    const data = await apiRequest('/api/auth/register', {
      method: 'POST',
      body: { name, email, password, confirm_password: confirmPassword }
    });
    state.token = data.access_token;
    state.user = data.user;
    localStorage.setItem('ai_mock_token', data.access_token);
    localStorage.setItem('ai_mock_user', JSON.stringify(data.user));
    navigate('dashboard');
    fetchDashboardData();
  } catch (err) {
    state.error = err.message;
    btn.disabled = false;
    btn.innerText = 'Register & Start Preparing';
    render();
  }
}

async function handleSetupSubmit(e) {
  e.preventDefault();
  state.error = null;
  const company = selectedType === 'company' ? (document.getElementById('setupCompany')?.value || '').trim() : null;
  const role = selectedType === 'company' ? (document.getElementById('setupRole')?.value || '').trim() : null;

  const jdText = (document.getElementById('setupJdText')?.value || '').trim();
  const hasJdText = Boolean(jdText);
  const hasJdFile = Boolean(selectedFiles.jd);

  if (selectedType === 'company') {
    if (!company) { state.error = 'Please enter company name.'; render(); return; }
    if (!role) { state.error = 'Please enter target job role.'; render(); return; }
    if (!hasJdText && !hasJdFile) {
      state.error = 'Please provide a Job Description by pasting text or uploading a PDF/DOCX file.';
      render();
      return;
    }
    if (!selectedFiles.resume) { state.error = 'Please select a Resume (PDF/DOCX).'; render(); return; }
  } else {
    if (!selectedFiles.resume) { state.error = 'Please select your Resume (PDF/DOCX).'; render(); return; }
  }

  const pBox = document.getElementById('setupProgress');
  const pText = document.getElementById('setupProgressText');
  const sBtn = document.getElementById('setupSubmitBtn');

  if (pBox) pBox.style.display = 'block';
  if (sBtn) sBtn.disabled = true;

  try {
    if (pText) pText.innerText = 'Step 1/3: Initializing interview record...';
    const intData = await apiRequest('/api/interviews', {
      method: 'POST',
      body: {
        interview_type: selectedType,
        company_name: company,
        job_role: role,
        duration_minutes: selectedDuration || 30
      }
    });

    const intId = intData.id;

    if (selectedType === 'company') {
      if (hasJdText && hasJdFile) {
        if (pText) pText.innerText = 'Step 2/4: Saving pasted Job Description and uploading JD file...';
        const textForm = new FormData();
        textForm.append('jd_text', jdText);
        await apiRequest(`/api/interviews/${intId}/submit-jd`, {
          method: 'POST',
          body: textForm
        });
        const jdForm = new FormData();
        jdForm.append('file', selectedFiles.jd);
        await apiRequest(`/api/interviews/${intId}/upload-jd`, {
          method: 'POST',
          body: jdForm
        });
      } else if (hasJdText) {
        if (pText) pText.innerText = 'Step 2/4: Saving pasted Job Description...';
        const textForm = new FormData();
        textForm.append('jd_text', jdText);
        await apiRequest(`/api/interviews/${intId}/submit-jd`, {
          method: 'POST',
          body: textForm
        });
      } else if (hasJdFile) {
        if (pText) pText.innerText = 'Step 2/4: Uploading & extracting Job Description...';
        const jdForm = new FormData();
        jdForm.append('file', selectedFiles.jd);
        await apiRequest(`/api/interviews/${intId}/upload-jd`, {
          method: 'POST',
          body: jdForm
        });
      }
    }

    if (pText) pText.innerText = 'Step 3/4: Uploading & parsing Candidate Resume...';
    const resForm = new FormData();
    resForm.append('file', selectedFiles.resume);
    await apiRequest(`/api/interviews/${intId}/upload-resume`, {
      method: 'POST',
      body: resForm
    });

    if (pText) pText.innerText = 'Success! Redirecting to workspace...';
    selectedFiles = { resume: null, jd: null };
    setTimeout(() => {
      navigate(`interviews/${intId}`);
    }, 400);
  } catch (err) {
    state.error = err.message;
    if (pBox) pBox.style.display = 'none';
    if (sBtn) sBtn.disabled = false;
    render();
  }
}

// Initial render
render();
