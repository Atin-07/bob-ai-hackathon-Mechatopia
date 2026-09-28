import { useEffect, useState } from "react";
import { AlertTriangle, User } from "lucide-react";

interface Toast {
  id: string;
  message: string;
  category: string;
  timestamp: number;
}

let addToast: (t: Omit<Toast, "timestamp">) => void = () => {};

export function showToast(id: string, message: string, category: string) {
  addToast({ id, message, category });
}

export default function ToastContainer() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  useEffect(() => {
    addToast = (t) => {
      setToasts((prev) => [{ ...t, timestamp: Date.now() }, ...prev].slice(0, 5));
    };
  }, []);

  // Auto-dismiss after 6s
  useEffect(() => {
    if (toasts.length === 0) return;
    const timer = setTimeout(() => {
      setToasts((prev) => prev.slice(0, -1));
    }, 6000);
    return () => clearTimeout(timer);
  }, [toasts]);

  return (
    <div className="toast-container">
      {toasts.map((t) => (
        <div key={t.id + t.timestamp} className={`toast ${t.category}`}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            {t.category === "wanted" ? (
              <AlertTriangle size={14} color="var(--red)" />
            ) : (
              <User size={14} color="var(--blue)" />
            )}
            <span className={`badge ${t.category}`}>{t.category}</span>
          </div>
          <div style={{ fontSize: "0.82rem" }}>{t.message}</div>
        </div>
      ))}
    </div>
  );
}
