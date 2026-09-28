import { Routes, Route, NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Camera,
  Search,
  Bell,
  Shield,
  Sun,
  Moon,
  Radio,
} from "lucide-react";
import { useTheme } from "./context/ThemeContext";
import DashboardPage from "./pages/DashboardPage";
import CamerasPage from "./pages/CamerasPage";
import PersonSearchPage from "./pages/PersonSearchPage";
import AlertsPage from "./pages/AlertsPage";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/cameras", label: "Cameras", icon: Camera },
  { to: "/search", label: "Person Search", icon: Search },
  { to: "/alerts", label: "Alerts", icon: Bell },
] as const;

export default function App() {
  const { theme, toggleTheme } = useTheme();

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="sidebar-brand">
            <div className="brand-icon-wrapper">
              <Shield size={20} />
            </div>
            <span>Mechatopia</span>
          </div>
        </div>

        <nav className="sidebar-nav">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                "nav-link" + (isActive ? " active" : "")
              }
            >
              <Icon size={18} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <button
            className="theme-toggle-btn"
            onClick={toggleTheme}
            title={`Switch to ${theme === "dark" ? "Light" : "Dark"} mode`}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
              <span className="theme-toggle-label">
                {theme === "dark" ? "Light Mode" : "Dark Mode"}
              </span>
            </div>
            <span style={{ fontSize: "0.75rem", opacity: 0.6 }}>
              {theme === "dark" ? "☀️" : "🌙"}
            </span>
          </button>

          <div className="system-status-indicator">
            <Radio size={12} color="var(--green)" />
            <span>Surveillance Mesh Online</span>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/cameras" element={<CamerasPage />} />
          <Route path="/search" element={<PersonSearchPage />} />
          <Route path="/alerts" element={<AlertsPage />} />
        </Routes>
      </main>
    </div>
  );
}
