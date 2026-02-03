import React from 'react';
import { BrowserRouter as Router, Routes, Route, NavLink } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import Dashboard from './pages/Dashboard';
import Upload from './pages/Upload';
import Recordings from './pages/Recordings';
import RecordingView from './pages/RecordingView';
import Models from './pages/Models';
import RealtimeDashboard from './pages/RealtimeDashboard';

function App() {
  return (
    <AuthProvider>
      <Router>
        <div className="app">
          <nav className="nav">
            <div className="nav-content">
              <NavLink to="/" className="nav-brand">
                🧠 <span>Neuro</span>Lab
              </NavLink>
              <div className="nav-links">
                <NavLink 
                  to="/" 
                  className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
                  end
                >
                  Dashboard
                </NavLink>
                <NavLink 
                  to="/upload" 
                  className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
                >
                  Upload
                </NavLink>
                <NavLink 
                  to="/recordings" 
                  className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
                >
                  Recordings
                </NavLink>
                <NavLink 
                  to="/models" 
                  className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
                >
                  Models
                </NavLink>
                <NavLink 
                  to="/realtime" 
                  className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
                >
                  Real-time
                </NavLink>
              </div>
            </div>
          </nav>
          
          <main className="main-content">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/upload" element={<Upload />} />
              <Route path="/recordings" element={<Recordings />} />
              <Route path="/recordings/:id" element={<RecordingView />} />
              <Route path="/models" element={<Models />} />
              <Route path="/realtime" element={<RealtimeDashboard />} />
            </Routes>
          </main>
        </div>
      </Router>
    </AuthProvider>
  );
}

export default App;
