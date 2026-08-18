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
