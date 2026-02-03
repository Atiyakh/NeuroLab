import React, { useState, useEffect, useRef, useCallback } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, AreaChart, Area } from 'recharts';
import socketService from '../services/socket';

const RealtimeDashboard = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [eegData, setEegData] = useState([]);
  const [bandPowers, setBandPowers] = useState([]);
  const [selectedChannels, setSelectedChannels] = useState(['Fp1', 'Fp2', 'C3', 'C4']);
  const [bufferSize, setBufferSize] = useState(100);
  const [updateRate, setUpdateRate] = useState(10);
  const dataRef = useRef([]);
  const intervalRef = useRef(null);

  // Available EEG channels
  const availableChannels = ['Fp1', 'Fp2', 'F3', 'F4', 'C3', 'C4', 'P3', 'P4', 'O1', 'O2', 'Fz', 'Cz', 'Pz'];

  // Frequency bands
  const bands = [
    { name: 'Delta', range: '0.5-4 Hz', color: '#8B5CF6' },
    { name: 'Theta', range: '4-8 Hz', color: '#06B6D4' },
    { name: 'Alpha', range: '8-13 Hz', color: '#10B981' },
    { name: 'Beta', range: '13-30 Hz', color: '#F59E0B' },
    { name: 'Gamma', range: '30-100 Hz', color: '#EF4444' },
  ];

  const generateSimulatedData = useCallback(() => {
    const timestamp = Date.now();
    const newPoint = { timestamp };

    selectedChannels.forEach((channel) => {
      // Simulate EEG-like signals with multiple frequency components
      const t = timestamp / 1000;
      const delta = Math.sin(2 * Math.PI * 2 * t) * 20;
      const theta = Math.sin(2 * Math.PI * 6 * t) * 15;
      const alpha = Math.sin(2 * Math.PI * 10 * t) * 25;
      const beta = Math.sin(2 * Math.PI * 20 * t) * 10;
      const noise = (Math.random() - 0.5) * 20;
      newPoint[channel] = delta + theta + alpha + beta + noise;
    });

    dataRef.current = [...dataRef.current, newPoint].slice(-bufferSize);
    setEegData([...dataRef.current]);

    // Update band powers periodically
    if (dataRef.current.length % 10 === 0) {
      const newBandPowers = bands.map((band) => ({
        name: band.name,
        power: Math.random() * 100,
        normalized: Math.random() * 100,
      }));
      setBandPowers(newBandPowers);
    }
  }, [selectedChannels, bufferSize]);

  const startStreaming = () => {
    setIsStreaming(true);
    intervalRef.current = setInterval(generateSimulatedData, 1000 / updateRate);
  };

  const stopStreaming = () => {
    setIsStreaming(false);
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  };

  const clearData = () => {
    dataRef.current = [];
    setEegData([]);
    setBandPowers([]);
  };

  useEffect(() => {
    const unsubConnect = socketService.onConnect(() => setIsConnected(true));
    const unsubDisconnect = socketService.onDisconnect(() => setIsConnected(false));

    return () => {
      unsubConnect();
      unsubDisconnect();
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  const toggleChannel = (channel) => {
    setSelectedChannels((prev) =>
      prev.includes(channel)
        ? prev.filter((c) => c !== channel)
        : [...prev, channel]
    );
  };

  const channelColors = ['#8B5CF6', '#06B6D4', '#10B981', '#F59E0B', '#EF4444', '#EC4899', '#6366F1', '#84CC16'];

  return (
    <div>
      <div className="page-header">
        <div className="flex justify-between items-start">
          <div>
            <h1>Real-time Dashboard</h1>
            <p>Monitor live EEG/MEG signals and computed features</p>
          </div>
          <div className="flex items-center gap-md">
            <div className={`flex items-center gap-sm ${isConnected ? 'text-success' : 'text-error'}`}>
              <div style={{
                width: '10px',
                height: '10px',
                borderRadius: '50%',
                background: isConnected ? 'var(--accent-success)' : 'var(--accent-error)',
                boxShadow: isConnected ? '0 0 10px var(--accent-success)' : '0 0 10px var(--accent-error)',
                animation: isConnected && isStreaming ? 'pulse 2s infinite' : 'none'
              }} />
              <span style={{ fontSize: '0.875rem' }}>
                {isConnected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Control Panel */}
      <div className="card mb-xl">
        <div className="flex flex-wrap justify-between items-center gap-lg">
          <div className="flex gap-md">
            {isStreaming ? (
              <button className="btn btn-warning" onClick={stopStreaming}>
                ⏸ Pause Stream
              </button>
            ) : (
              <button className="btn btn-primary" onClick={startStreaming}>
                ▶ Start Stream
              </button>
            )}
            <button className="btn btn-secondary" onClick={clearData}>
              🗑 Clear Data
            </button>
          </div>

          <div className="flex gap-lg items-center">
            <div className="flex items-center gap-sm">
              <label className="text-muted" style={{ fontSize: '0.875rem' }}>Buffer:</label>
              <select 
                className="form-input" 
                value={bufferSize} 
                onChange={(e) => setBufferSize(Number(e.target.value))}
                style={{ width: '100px' }}
              >
                <option value={50}>50 pts</option>
                <option value={100}>100 pts</option>
                <option value={200}>200 pts</option>
                <option value={500}>500 pts</option>
              </select>
            </div>

            <div className="flex items-center gap-sm">
              <label className="text-muted" style={{ fontSize: '0.875rem' }}>Rate:</label>
              <select 
                className="form-input" 
                value={updateRate} 
                onChange={(e) => setUpdateRate(Number(e.target.value))}
                style={{ width: '100px' }}
              >
                <option value={5}>5 Hz</option>
                <option value={10}>10 Hz</option>
                <option value={20}>20 Hz</option>
                <option value={50}>50 Hz</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-3 mb-xl">
        {/* Channel Selector */}
        <div className="card">
          <h3 className="card-title mb-lg">📡 Channels</h3>
          <div className="flex flex-wrap gap-sm">
            {availableChannels.map((channel, idx) => (
              <button
                key={channel}
                onClick={() => toggleChannel(channel)}
                className={`btn btn-sm ${selectedChannels.includes(channel) ? 'btn-primary' : 'btn-ghost'}`}
                style={selectedChannels.includes(channel) ? {
                  background: channelColors[selectedChannels.indexOf(channel) % channelColors.length],
                } : {}}
              >
                {channel}
              </button>
            ))}
          </div>
          <p className="text-muted mt-md" style={{ fontSize: '0.8125rem' }}>
            {selectedChannels.length} channel(s) selected
          </p>
        </div>

        {/* Stream Stats */}
        <div className="card">
          <h3 className="card-title mb-lg">📊 Stream Stats</h3>
          <div className="grid grid-2" style={{ gap: 'var(--spacing-md)' }}>
            <div className="metric-card">
              <div className="metric-value">{eegData.length}</div>
              <div className="metric-label">Data Points</div>
            </div>
            <div className="metric-card">
              <div className="metric-value">{updateRate} Hz</div>
              <div className="metric-label">Sample Rate</div>
            </div>
            <div className="metric-card">
              <div className="metric-value">{selectedChannels.length}</div>
              <div className="metric-label">Channels</div>
            </div>
            <div className="metric-card">
              <div className="metric-value" style={{ color: isStreaming ? 'var(--accent-success)' : 'var(--text-muted)' }}>
                {isStreaming ? 'Active' : 'Idle'}
              </div>
              <div className="metric-label">Status</div>
            </div>
          </div>
        </div>

        {/* Band Power Summary */}
        <div className="card">
          <h3 className="card-title mb-lg">🧠 Band Power</h3>
          {bandPowers.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-sm)' }}>
              {bands.map((band, idx) => {
                const power = bandPowers.find(b => b.name === band.name)?.power || 0;
                return (
                  <div key={band.name} className="flex items-center gap-md">
                    <span style={{ width: '60px', fontSize: '0.8125rem', color: band.color }}>
                      {band.name}
                    </span>
                    <div style={{ flex: 1, height: '8px', background: 'var(--bg-primary)', borderRadius: '4px' }}>
                      <div style={{
                        height: '100%',
                        width: `${power}%`,
                        background: band.color,
                        borderRadius: '4px',
                        transition: 'width 0.3s ease'
                      }} />
                    </div>
                    <span style={{ width: '40px', fontSize: '0.75rem', textAlign: 'right', color: 'var(--text-muted)' }}>
                      {power.toFixed(0)}%
                    </span>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-muted">Start streaming to see band powers</p>
          )}
        </div>
      </div>

      {/* Main EEG Chart */}
      <div className="card mb-xl">
        <div className="card-header">
          <h3 className="card-title">⚡ EEG Signal (μV)</h3>
          {isStreaming && (
            <span className="badge badge-success">
              <span className="badge-dot"></span>
              Live
            </span>
          )}
        </div>

        {eegData.length > 0 ? (
          <div style={{ height: '400px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={eegData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis 
                  dataKey="timestamp" 
                  tickFormatter={(value) => new Date(value).toLocaleTimeString()} 
                  stroke="rgba(255,255,255,0.3)"
                  tick={{ fontSize: 11 }}
                />
                <YAxis 
                  domain={[-100, 100]} 
                  stroke="rgba(255,255,255,0.3)"
                  tick={{ fontSize: 11 }}
                />
                <Tooltip
                  contentStyle={{
                    background: 'var(--bg-glass)',
                    border: '1px solid var(--border-color)',
                    borderRadius: 'var(--radius-md)',
                    backdropFilter: 'blur(20px)'
                  }}
                  labelFormatter={(value) => new Date(value).toLocaleTimeString()}
                />
                <Legend />
                {selectedChannels.map((channel, idx) => (
                  <Line
                    key={channel}
                    type="monotone"
                    dataKey={channel}
                    stroke={channelColors[idx % channelColors.length]}
                    dot={false}
                    strokeWidth={1.5}
                    isAnimationActive={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="empty-state" style={{ padding: 'var(--spacing-3xl)' }}>
            <div className="empty-state-icon">📈</div>
            <h3 className="empty-state-title">No data yet</h3>
            <p className="empty-state-text">
              Click "Start Stream" to begin visualizing simulated EEG data
            </p>
          </div>
        )}
      </div>

      {/* Band Power Spectrum */}
      {bandPowers.length > 0 && (
        <div className="card">
          <h3 className="card-title mb-lg">📊 Band Power Spectrum</h3>
          <div style={{ height: '250px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={bandPowers} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <defs>
                  {bands.map((band) => (
                    <linearGradient key={band.name} id={`gradient-${band.name}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={band.color} stopOpacity={0.8} />
                      <stop offset="95%" stopColor={band.color} stopOpacity={0.1} />
                    </linearGradient>
                  ))}
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis 
                  dataKey="name" 
                  stroke="rgba(255,255,255,0.3)"
                  tick={{ fontSize: 11 }}
                />
                <YAxis 
                  stroke="rgba(255,255,255,0.3)"
                  tick={{ fontSize: 11 }}
                />
                <Tooltip
                  contentStyle={{
                    background: 'var(--bg-glass)',
                    border: '1px solid var(--border-color)',
                    borderRadius: 'var(--radius-md)',
                    backdropFilter: 'blur(20px)'
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="power"
                  stroke="#8B5CF6"
                  fill="url(#gradient-Delta)"
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
};

export default RealtimeDashboard;
