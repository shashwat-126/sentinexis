import { useEffect, useRef, useState, useCallback } from "react";
import { signOut } from "firebase/auth";

import { auth } from "../firebase";
import {
  api,
  getIncidents,
  getIncidentStats,
  checkAllHealth,
  connectIncidentsSocket,
} from "../api";

import StatCards from "./StatCards";
import ServiceHealthGrid from "./ServiceHealthGrid";
import ObservabilityLinks from "./ObservabilityLinks";
import ChaosPanel from "./ChaosPanel";
import MetricsChart from "./MetricsChart";
import IncidentsTable from "./IncidentsTable";
import IncidentDrawer from "./IncidentDrawer";
import InferencePanel from "./InferencePanel";

/* ============================================================
   SENTINEXIS DASHBOARD

   This is the approved layout: one scrolling page, every panel
   visible at once, real data end-to-end. The gateway's
   /incidents/* routing bug (it was stripping the "incidents"
   prefix before forwarding, so every incident/stat/timeline call
   404'd against incident-service) is fixed in api-gateway/main.py
   -- this component no longer needs to work around it.
============================================================ */

export default function Dashboard({ user }) {
  const [services, setServices] = useState([]);
  const [stats, setStats] = useState(null);
  const [incidents, setIncidents] = useState([]);
  const [selected, setSelected] = useState(null);
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef(null);

  const gatewayHealthy = services.find((s) => s.key === "gateway")?.healthy;

  /* --------------------------------------------------------
     Firebase token is attached to every request automatically
     by the axios interceptor in api.js -- nothing to do here
     except make sure the very first request (fired on mount,
     possibly before the interceptor's first async round-trip
     resolves) doesn't race a stale/missing token.
  -------------------------------------------------------- */
  const primeToken = useCallback(async () => {
    if (!user) return;
    try {
      const token = await user.getIdToken();
      api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
    } catch (err) {
      console.error("Unable to get Firebase token:", err);
    }
  }, [user]);

  const refreshAll = useCallback(() => {
    getIncidents({ limit: 50 }).then(setIncidents).catch((err) => {
      console.error("getIncidents failed:", err?.response?.status, err?.message);
    });
    getIncidentStats().then(setStats).catch((err) => {
      console.error("getIncidentStats failed:", err?.response?.status, err?.message);
    });
    checkAllHealth().then(setServices).catch(() => {});
  }, []);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;

    primeToken().then(() => {
      if (!cancelled) refreshAll();
    });

    const interval = setInterval(refreshAll, 10000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [user, primeToken, refreshAll]);

  /* --------------------------------------------------------
     Live updates over WebSocket. The gateway's /ws/incidents
     route requires the Firebase token as a ?token= query param
     (browsers can't set headers on a native WebSocket) --
     connectIncidentsSocket() in api.js handles that.
  -------------------------------------------------------- */
  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    let reconnectTimer = null;

    const connect = async () => {
      try {
        const ws = await connectIncidentsSocket({
          onOpen: () => !cancelled && setWsConnected(true),
          onClose: () => {
            if (cancelled) return;
            setWsConnected(false);
            reconnectTimer = setTimeout(connect, 5000);
          },
          onError: () => !cancelled && setWsConnected(false),
          onMessage: ({ type, data }) => {
            if (type === "incident_created") {
              setIncidents((prev) => [data, ...prev].slice(0, 50));
              setStats((prev) => prev && { ...prev, open: prev.open + 1, total: prev.total + 1 });
            } else if (type === "incident_updated") {
              setIncidents((prev) => prev.map((inc) => (inc.id === data.id ? data : inc)));
              getIncidentStats().then(setStats).catch(() => {});
            }
          },
        });
        wsRef.current = ws;
      } catch (err) {
        console.error("WebSocket connection failed:", err);
        if (!cancelled) reconnectTimer = setTimeout(connect, 5000);
      }
    };

    connect();
    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      wsRef.current?.close();
    };
  }, [user]);

  const logout = async () => {
    try {
      await signOut(auth);
      delete api.defaults.headers.common["Authorization"];
    } catch (err) {
      console.error("Logout failed:", err);
    }
  };

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
          <button type="button" className="action-btn action-btn-secondary" onClick={logout}>
            Sign out ({user?.email})
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
