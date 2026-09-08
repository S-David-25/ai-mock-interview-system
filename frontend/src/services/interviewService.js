import { api } from './api';

export const interviewService = {
  // Master Prompt 1: Setup & Management
  async createInterview({ interview_type, company_name, job_role, duration_minutes = 30 }) {
    return await api.post('/api/interviews', {
      interview_type,
      company_name: interview_type === 'company' ? company_name : null,
      job_role: interview_type === 'company' ? job_role : null,
      duration_minutes: Number(duration_minutes) || 30,
    });
  },

  async getInterviews() {
    return await api.get('/api/interviews');
  },

  async getInterviewById(id) {
    return await api.get(`/api/interviews/${id}`);
  },

  async uploadResume(interviewId, file) {
    const formData = new FormData();
    formData.append('file', file);
    return await api.post(`/api/interviews/${interviewId}/upload-resume`, formData);
  },

  async uploadJD(interviewId, file) {
    const formData = new FormData();
    formData.append('file', file);
    return await api.post(`/api/interviews/${interviewId}/upload-jd`, formData);
  },

  async submitJDText(interviewId, jdText) {
    const formData = new FormData();
    formData.append('jd_text', jdText);
    return await api.post(`/api/interviews/${interviewId}/submit-jd`, formData);
  },

  async getInterviewStatus(interviewId) {
    return await api.get(`/api/interviews/${interviewId}/status`);
  },

  // Master Prompt 2: Engine & Voice Session
  async processDocuments(interviewId) {
    return await api.post(`/api/interviews/${interviewId}/process`);
  },

  async generateQuestions(interviewId) {
    return await api.post(`/api/interviews/${interviewId}/generate-questions`);
  },

  async getQuestions(interviewId) {
    return await api.get(`/api/interviews/${interviewId}/questions`);
  },

  async startInterview(interviewId) {
    return await api.post(`/api/interviews/${interviewId}/start`);
  },

  async transcribeAudio(interviewId, audioBlob, fallbackText = '') {
    const formData = new FormData();
    formData.append('file', audioBlob, 'recording.webm');
    if (fallbackText) {
      formData.append('fallback_text', fallbackText);
    }
    return await api.post(`/api/interviews/${interviewId}/transcribe`, formData);
  },

  async submitAnswer(interviewId, { questionId, transcript, speakingDuration = 0, audioFilename = null }) {
    return await api.post(`/api/interviews/${interviewId}/answer`, {
      question_id: questionId,
      transcript,
      speaking_duration: speakingDuration,
      audio_filename: audioFilename,
    });
  },

  async sendVisionFrame(interviewId, { questionId, imageBase64 }) {
    return await api.post(`/api/interviews/${interviewId}/vision-frame`, {
      question_id: questionId,
      image_base64: imageBase64,
    });
  },

  async completeInterview(interviewId) {
    return await api.post(`/api/interviews/${interviewId}/complete`);
  },

  // Master Prompt 3: Scoring, Performance Report, Roadmap & Progress Intelligence
  async generateReport(interviewId) {
    return await api.post(`/api/interviews/${interviewId}/generate-report`);
  },

  async getReport(interviewId) {
    return await api.get(`/api/interviews/${interviewId}/report`);
  },

  async getScore(interviewId) {
    return await api.get(`/api/interviews/${interviewId}/score`);
  },

  async getRoadmap(interviewId) {
    return await api.get(`/api/interviews/${interviewId}/roadmap`);
  },

  async getProgress() {
    return await api.get('/api/progress');
  },

  async compareInterviews(firstId, secondId) {
    return await api.get(`/api/interviews/compare?first_id=${firstId}&second_id=${secondId}`);
  }
};
