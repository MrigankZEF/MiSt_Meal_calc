import { type ReactNode } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import Nav from './components/Nav';
import { AuthProvider, useAuth } from './context/AuthContext';
import AdminEatLancet from './routes/AdminEatLancet';
import History from './routes/History';
import Landing from './routes/Landing';
import Login from './routes/Login';
import MealMode from './routes/MealMode';
import ProcurementMode from './routes/ProcurementMode';

// ── Route guard ───────────────────────────────────────────────────────────
// Redirects to /login when the user is not authenticated.
// Shows a brief loading state while the stored token is being verified.

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="route-loading">
        <span>Loading…</span>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

// ── App ───────────────────────────────────────────────────────────────────

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Nav />
        <Routes>
          {/* Public routes */}
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />

          {/* Protected routes — redirect to /login if not signed in */}
          <Route path="/meal"         element={<ProtectedRoute><MealMode /></ProtectedRoute>} />
          <Route path="/procurement"  element={<ProtectedRoute><ProcurementMode /></ProtectedRoute>} />
          <Route path="/history"      element={<ProtectedRoute><History /></ProtectedRoute>} />
          <Route path="/admin"        element={<ProtectedRoute><AdminEatLancet /></ProtectedRoute>} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
