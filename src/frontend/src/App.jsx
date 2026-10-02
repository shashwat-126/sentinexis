import { useEffect, useRef, useState } from "react";
import { onAuthStateChanged, signOut } from "firebase/auth";

import { auth } from "./firebase";
import {
  getIncidents,
  getIncidentStats,
  checkAllHealth,
  connectIncidentsSocket,
} from "./api";

import Login from "./components/Login";
import Register from "./components/Register";
import StatCards from "./components/StatCards";
import ServiceHealthGrid from "./components/ServiceHealthGrid";
import IncidentsTable from "./components/IncidentsTable";
import IncidentDrawer from "./components/IncidentDrawer";
import ChaosPanel from "./components/ChaosPanel";
import MetricsChart from "./components/MetricsChart";
import ObservabilityLinks from "./components/ObservabilityLinks";
import InferencePanel from "./components/InferencePanel";

function App() {
  /* ----------------------------------------------------------
     AUTH STATE (Firebase -- unchanged from the working login flow)
  ---------------------------------------------------------- */
  const [user, setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [showRegister, setShowRegister] = useState(false);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (currentUser) => {
      setUser(currentUser);
      setAuthLoading(false);
    });
    return unsubscribe;
  }, []);

  const logout = () => signOut(auth);

  if (authLoading) {
    return (
      <div className="loading-screen">
        <div className="loading-logo">⚡</div>
        <h2>Sentinexis</h2>
        <p>Initializing secure control plane...</p>
      </div>
    );
  }

  if (!user) {
    return showRegister ? (
      <Register onRegistered={setUser} switchToLogin={() => setShowRegister(false)} />
    ) : (
      <Login onLogin={setUser} switchToRegister={() => setShowRegister(true)} />
    );
  }

  return <PlatformDashboard user={user} onLogout={logout} />;
}

/* ============================================================
   PLATFORM DASHBOARD -- the flat, single-page layout: stat cards,
   cluster health, observability links, chaos engineering, metrics
   history, incidents table + drawer, and the inference test feed.
   Every panel below fetches real data through api.js -- nothing
   here is mocked.
============================================================ */
function PlatformDashboard({ user, onLogout }) {
  const [services, setServices] = useState([]);
  const [stats, setStats] = useState(null);
  const [incidents, setIncidents] = useState([]);
  const [selected, setSelected] = useState(null);
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef(null);

  const gatewayHealthy = services.find((s) => s.key === "gateway")?.healthy;

  const refreshAll = () => {
    getIncidents({ limit: 50 }).then(setIncidents).catch(() => {});
    getIncidentStats().then(setStats).catch(() => {});
    checkAllHealth().then(setServices).catch(() => {});
  };

  // Initial load + 10s poll fallback (in case the WebSocket below is down).
  useEffect(() => {
    refreshAll();
    const interval = setInterval(refreshAll, 10000);
    return () => clearInterval(interval);
  }, []);

  // Live updates -- connectIncidentsSocket() attaches the current Firebase
  // ID token as a query param (the gateway's /ws/incidents route requires
  // it); auto-reconnects every 5s if the connection drops.
  useEffect(() => {
    let cancelled = false;
    let reconnectTimer = null;

    const connect = async () => {
      try {
        const ws = await connectIncidentsSocket({
          onOpen: () => !cancelled && setWsConnected(true),
          onMessage: ({ type, data }) => {
            if (type === "incident_created") {
              setIncidents((prev) => [data, ...prev].slice(0, 50));
              setStats((prev) => prev && { ...prev, open: prev.open + 1, total: prev.total + 1 });
            } else if (type === "incident_updated") {
              setIncidents((prev) => prev.map((inc) => (inc.id === data.id ? data : inc)));
              getIncidentStats().then(setStats).catch(() => {});
            }
          },
          onClose: () => {
            if (cancelled) return;
            setWsConnected(false);
            reconnectTimer = setTimeout(connect, 5000);
          },
          onError: () => !cancelled && setWsConnected(false),
        });
        wsRef.current = ws;
      } catch {
        if (!cancelled) reconnectTimer = setTimeout(connect, 5000);
      }
    };

    connect();
    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      wsRef.current?.close();
    };
  }, []);

  return (
    <div className="dashboard-container">
      <header className="header">
        <h1>AIOps Platform Dashboard</h1>
        <div className="header-badges">
          <div className={`status-badge ${wsConnected ? "status-healthy" : "status-warning"}`}>
            <span className="dot">●</span>
            {wsConnected ? "Live Updates Connected" : "Polling Mode"}
          </div>
          <div className={`status-badge ${gatewayHealthy ? "status-healthy" : "status-warning"}`}>
            <span className="dot">●</span>
            {gatewayHealthy ? "Platform Online" : "Platform Degraded"}
          </div>
          <button type="button" className="action-btn action-btn-secondary" onClick={onLogout}>
            {user?.email || "Account"} — Sign out
          </button>
        </div>
      </header>

      <StatCards stats={stats} />

      <div className="grid">
        <ServiceHealthGrid services={services} />
        <ObservabilityLinks />
        <ChaosPanel />
      </div>

      <div className="grid">
        <MetricsChart />
      </div>

      <div className="grid">
        <IncidentsTable incidents={incidents} onSelect={setSelected} />
      </div>

      <div className="grid">
        <InferencePanel />
      </div>

      <IncidentDrawer incident={selected} onClose={() => setSelected(null)} />
    </div>
  );
}

export default App;
