import React, { useState, useEffect } from 'react';
import { 
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, 
  PieChart, Pie, Cell, Legend 
} from 'recharts';
import { 
  ShieldAlert, CheckCircle2, Activity, ShieldCheck, 
  Server, RefreshCw, AlertTriangle, Cpu, TrendingDown 
} from 'lucide-react';

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

export default function App() {
  const [stats, setStats] = useState({ total_requests: 0, status_codes: {}, ips: {}, edge_rules: [] });
  const [security, setSecurity] = useState({ suspicious_ips: {} });
  const [healing, setHealing] = useState({ 
    health_status: "Healthy", 
    consecutive_crashes: 0, 
    auto_scaling_triggered: false, 
    instances: [],
    system_mode: "Stable",
    crash_probability: 0,
    cpu_utilization: 35,
    latency_ms: 45
  });
  const [isConnected, setIsConnected] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const fetchData = async () => {
    setIsRefreshing(true);
    try {
      // Fetch General Stats
      const statsRes = await fetch('http://127.0.0.1:8000/api/stats');
      const statsData = await statsRes.json();
      
      // Fetch Security Audit
      const securityRes = await fetch('http://127.0.0.1:8000/api/security');
      const securityData = await securityRes.json();

      // Fetch Self-Healing info
      const healingRes = await fetch('http://127.0.0.1:8000/api/healing');
      const healingData = await healingRes.json();
      
      if (!statsData.error && !securityData.error && !healingData.error) {
        setStats(statsData);
        setSecurity(securityData);
        setHealing(healingData);
        setIsConnected(true);
      } else {
        setIsConnected(false);
      }
    } catch (err) {
      setIsConnected(false);
      console.error("Could not fetch data from FastAPI backend", err);
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchData();
    // Poll APIs every 1 second for real-time updates
    const interval = setInterval(fetchData, 1000);
    return () => clearInterval(interval);
  }, []);

  // Format Status Codes data for BarChart
  const statusChartData = Object.entries(stats.status_codes).map(([code, count]) => ({
    name: `HTTP ${code}`,
    count: count,
    fill: code.startsWith('2') ? '#10b981' : code.startsWith('4') ? '#f59e0b' : '#ef4444'
  }));

  // Format IP Traffic data for PieChart
  const trafficChartData = Object.entries(stats.ips).map(([ip, count]) => ({
    name: ip,
    value: count
  })).slice(0, 5); // top 5 IPs

  const suspiciousCount = Object.keys(security.suspicious_ips).length;
  const isServerCrashed = healing.consecutive_crashes >= 5;

  return (
    <div className="dashboard-container">
      {/* HEADER SECTION */}
      <header className="dashboard-header">
        <div className="header-left">
          <Activity className="header-icon text-blue" />
          <div>
            <h1>Cloud-Shield AI</h1>
            <p className="subtitle">Autonomous Observability & Cost Protection</p>
          </div>
        </div>
        
        <div className="header-right">
          <div className={`status-badge ${isConnected ? 'online' : 'offline'}`}>
            <span className="pulse-dot"></span>
            {isConnected ? 'Backend Connected' : 'Backend Disconnected'}
          </div>
          <button 
            className={`btn-refresh ${isRefreshing ? 'spinning' : ''}`}
            onClick={fetchData}
            title="Refresh logs stats"
          >
            <RefreshCw size={16} />
          </button>
        </div>
      </header>

      {/* AI PREDICTIVE SHIELD WARNING BANNER */}
      {healing.system_mode === "Predictive Warning" && (
        <div className="ai-warning-banner">
          <div className="banner-left">
            <ShieldAlert className="banner-icon text-danger animate-pulse" size={24} style={{ color: '#f59e0b' }} />
            <div>
              <h3>AI PRE-EMPTIVE SHIELD ACTIVE</h3>
              <p>Critical CPU spike (<b>{healing.cpu_utilization}%</b>) and Latency (<b>{healing.latency_ms}ms</b>) detected. Server crash predicted within 10s.</p>
            </div>
          </div>
          <div className="banner-right">
            <div className="probability-badge">
              <span className="prob-label">Crash Probability</span>
              <span className="prob-value">{healing.crash_probability}%</span>
            </div>
            <div className="action-badge">
              <span className="pulse-dot-orange"></span>
              Auto-Scaling Pre-emptive Backup Online
            </div>
          </div>
        </div>
      )}

      {/* METRICS CARDS */}
      <section className="metrics-grid">
        {/* Card 1: Total Requests */}
        <div className="metric-card">
          <div className="card-header">
            <span>Total Requests Ingested</span>
            <Server size={20} className="text-blue" />
          </div>
          <div className="card-value">{stats.total_requests}</div>
          <div className="card-footer">
            <span className="text-success">Active log stream</span>
          </div>
        </div>

        {/* Card 2: Security Alert Card */}
        <div className={`metric-card alert-card ${suspiciousCount > 0 ? 'critical-glow' : 'safe-glow'}`}>
          <div className="card-header">
            <span>Security Status</span>
            {suspiciousCount > 0 ? (
              <ShieldAlert size={20} className="text-danger animate-pulse" />
            ) : (
              <ShieldCheck size={20} className="text-success" />
            )}
          </div>
          <div className="card-value">
            {suspiciousCount > 0 ? `${suspiciousCount} Attack(s)` : 'Secure'}
          </div>
          <div className="card-footer">
            {suspiciousCount > 0 ? (
              <span className="text-danger">Brute force IPs flagged</span>
            ) : (
              <span className="text-success">No active threats detected</span>
            )}
          </div>
        </div>

        {/* Card 3: Cloud Savings Tracker */}
        <div className="metric-card">
          <div className="card-header">
            <span>FinOps Monthly Savings</span>
            <CheckCircle2 size={20} className="text-success" />
          </div>
          <div className="card-value text-success">
            ${stats.total_savings_usd !== undefined ? stats.total_savings_usd.toFixed(2) : '8.64'}
          </div>
          <div className="card-footer">
            <span className="text-slate" style={{ fontSize: '11px', display: 'block', lineHeight: '1.4' }}>
              Compute: <b className="text-success">$8.64</b> (Backup scaled down) <br />
              Bandwidth: <b className="text-success">${stats.bandwidth_savings_usd ? stats.bandwidth_savings_usd.toFixed(2) : '0.00'}</b> (Cached {stats.total_bandwidth_saved_mb ? stats.total_bandwidth_saved_mb.toFixed(1) : '0.0'} MB)
            </span>
          </div>
        </div>

        {/* Card 4: Self-Healing Server Health Status */}
        <div className={`metric-card alert-card ${
          isServerCrashed ? 'critical-glow' : 
          healing.system_mode === 'Predictive Warning' ? 'critical-glow' : 'safe-glow'
        }`} style={healing.system_mode === 'Predictive Warning' ? { borderColor: 'rgba(245, 158, 11, 0.4)', boxShadow: '0 0 15px rgba(245, 158, 11, 0.15)' } : {}}>
          <div className="card-header">
            <span>Server Health (Self-Healing)</span>
            {isServerCrashed ? (
              <AlertTriangle size={20} className="text-danger animate-pulse" />
            ) : healing.system_mode === 'Predictive Warning' ? (
              <ShieldAlert size={20} className="text-warning animate-pulse" />
            ) : (
              <Cpu size={20} className="text-success" />
            )}
          </div>
          <div className="card-value">
            {isServerCrashed ? 'Crashed' : healing.system_mode === 'Predictive Warning' ? 'Warning' : 'Healthy'}
          </div>
          <div className="card-footer">
            {isServerCrashed ? (
              <span className="text-danger">{healing.consecutive_crashes} consecutive crashes!</span>
            ) : healing.system_mode === 'Predictive Warning' ? (
              <span className="text-warning">CPU Spike: {healing.cpu_utilization}% (Crash Risk: {healing.crash_probability}%)</span>
            ) : (
              <span className="text-success">Servers operating normally</span>
            )}
          </div>
        </div>
      </section>

      {/* CHARTS CONTAINER */}
      <section className="charts-grid">
        {/* Status Codes Chart */}
        <div className="chart-card">
          <h3>Response Status Code Analysis</h3>
          <div className="chart-wrapper">
            {statusChartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={statusChartData}>
                  <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} />
                  <YAxis stroke="#94a3b8" fontSize={12} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
                    labelStyle={{ color: '#f8fafc' }}
                  />
                  <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                    {statusChartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="no-data">No traffic logs found. Send requests from Simulator.</div>
            )}
          </div>
        </div>

        {/* Traffic Distribution Chart */}
        <div className="chart-card">
          <h3>Traffic Distribution by Client IP</h3>
          <div className="chart-wrapper">
            {trafficChartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={trafficChartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={80}
                    paddingAngle={4}
                    dataKey="value"
                  >
                    {trafficChartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
                    itemStyle={{ color: '#f8fafc' }}
                  />
                  <Legend verticalAlign="bottom" height={36} wrapperStyle={{ fontSize: '11px', color: '#94a3b8' }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="no-data">No traffic logs found. Send requests from Simulator.</div>
            )}
          </div>
        </div>
      </section>

      {/* EDGE CACHING RECOMMENDATIONS SECTION */}
      <section className="security-logs-section">
        <div className="section-title">
          <TrendingDown size={16} className="text-success" />
          <span>FinOps Edge Caching Recommendations (suggested CloudFront rules)</span>
        </div>
        <div className="table-wrapper">
          {stats.edge_rules && stats.edge_rules.length > 0 ? (
            <table className="logs-table">
              <thead>
                <tr>
                  <th>Asset URL Path</th>
                  <th>Hits Detected</th>
                  <th>Recommended TTL</th>
                  <th>Caching Policy</th>
                  <th>Bandwidth Saved</th>
                  <th>Estimated Savings</th>
                </tr>
              </thead>
              <tbody>
                {stats.edge_rules.map((rule, idx) => (
                  <tr key={idx}>
                    <td><span className="ip-badge">{rule.url_path}</span></td>
                    <td>{rule.hits} requests</td>
                    <td>{rule.recommended_ttl}s (1 Hour)</td>
                    <td>
                      <span className="badge" style={{ backgroundColor: 'rgba(59, 130, 246, 0.15)', color: '#3b82f6' }}>
                        {rule.caching_status}
                      </span>
                    </td>
                    <td>
                      <span className="text-blue font-bold">{rule.mb_saved} MB</span>
                    </td>
                    <td className="text-success font-bold">+${rule.estimated_savings.toFixed(2)} saved</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="empty-security">
              <TrendingDown size={40} className="text-success mb-2" />
              <p>No optimization recommendations yet. Trigger multiple visits/downloads of the same file in Simulator.</p>
            </div>
          )}
        </div>
      </section>

      {/* LOGS AND HEALING SECTION */}
      <section className="logs-sections-grid">
        {/* Security Alert logs list */}
        <div className="security-logs-section">
          <div className="section-title">
            <ShieldAlert size={16} className="text-danger" />
            <span>Active Threat Intelligence List</span>
          </div>
          <div className="table-wrapper">
            {suspiciousCount > 0 ? (
              <table className="logs-table">
                <thead>
                  <tr>
                    <th>Attacking IP</th>
                    <th>Attempts</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(security.suspicious_ips).map(([ip, count]) => (
                    <tr key={ip} className="attack-row">
                      <td><span className="ip-badge">{ip}</span></td>
                      <td className="text-danger font-bold">{count} Failed Logins</td>
                      <td>
                        <span className="badge badge-danger">Blocked</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="empty-security">
                <ShieldCheck size={40} className="text-success mb-2" />
                <p>Everything is secure. No suspected hackers detected.</p>
              </div>
            )}
          </div>
        </div>

        {/* Self-healing EC2 scaling list */}
        <div className="security-logs-section">
          <div className="section-title">
            <Server size={16} className="text-blue" />
            <span>Self-Healing Scaled EC2 Instances</span>
          </div>
          <div className="table-wrapper">
            {healing.instances && healing.instances.length > 0 ? (
              <table className="logs-table">
                <thead>
                  <tr>
                    <th>Server Name / Role</th>
                    <th>Instance ID</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Launch Time</th>
                  </tr>
                </thead>
                <tbody>
                  {healing.instances.map((inst) => (
                    <tr key={inst.instance_id}>
                      <td>
                        <div className="font-bold" style={{ fontSize: '14px', color: '#f8fafc' }}>{inst.name}</div>
                        <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '2px' }}>{inst.role}</div>
                      </td>
                      <td><span className="ip-badge">{inst.instance_id}</span></td>
                      <td>{inst.type}</td>
                      <td>
                        <span className={`badge ${
                          inst.status.toLowerCase() === 'running' ? 'badge-running' : 
                          inst.status.toLowerCase() === 'crashed' ? 'badge-crashed' : 'badge-stopped'
                        }`}>{inst.status}</span>
                      </td>
                      <td>{inst.time}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="empty-security">
                <Cpu size={40} className="text-slate mb-2" />
                <p>No auto-scaling events triggered. Server loads are normal.</p>
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
