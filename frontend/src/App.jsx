import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Navbar } from './components/Navbar';
import { Login } from './pages/Login';
import { Register } from './pages/Register';
import { ForgotPassword } from './pages/ForgotPassword';
import { Dashboard } from './pages/Dashboard';
import { InterviewSetup } from './pages/InterviewSetup';
import { InterviewDetail } from './pages/InterviewDetail';
import { InterviewSession } from './pages/InterviewSession';
import { InterviewReport } from './pages/InterviewReport';
import { InterviewCompare } from './pages/InterviewCompare';
import { AdminLogin } from './pages/AdminLogin';
import { AdminRegister } from './pages/AdminRegister';
import { AdminForgotPassword } from './pages/AdminForgotPassword';
import { AdminDashboard } from './pages/AdminDashboard';
import { AdminCandidateDetail } from './pages/AdminCandidateDetail';
import { AdminInterviewDetail } from './pages/AdminInterviewDetail';
import { AdminProtectedRoute } from './components/AdminProtectedRoute';

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <div className="app-layout">
          <Navbar />
          <main className="main-content">
            <Routes>
              {/* Public Routes */}
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/forgot-password" element={<ForgotPassword />} />
              <Route path="/admin/login" element={<AdminLogin />} />
              <Route path="/admin/register" element={<AdminRegister />} />
              <Route path="/admin/forgot-password" element={<AdminForgotPassword />} />

              {/* Protected Routes */}
              <Route
                path="/dashboard"
                element={
                  <ProtectedRoute>
                    <Dashboard />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/setup"
                element={
                  <ProtectedRoute>
                    <InterviewSetup />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/interviews/compare"
                element={
                  <ProtectedRoute>
                    <InterviewCompare />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/interviews/:id"
                element={
                  <ProtectedRoute>
                    <InterviewDetail />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/interviews/:id/session"
                element={
                  <ProtectedRoute>
                    <InterviewSession />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/interviews/:id/report"
                element={
                  <ProtectedRoute>
                    <InterviewReport />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/dashboard"
                element={
                  <AdminProtectedRoute>
                    <AdminDashboard />
                  </AdminProtectedRoute>
                }
              />
              <Route
                path="/admin/candidates/:candidateId"
                element={
                  <AdminProtectedRoute>
                    <AdminCandidateDetail />
                  </AdminProtectedRoute>
                }
              />
              <Route
                path="/admin/interviews/:interviewId"
                element={
                  <AdminProtectedRoute>
                    <AdminInterviewDetail />
                  </AdminProtectedRoute>
                }
              />

              {/* Fallbacks */}
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
