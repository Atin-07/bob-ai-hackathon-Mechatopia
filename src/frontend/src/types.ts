export interface DashboardSummary {
  total_cameras: number;
  cameras_online?: number;
  cameras_offline?: number;
  cameras_maintenance?: number;
  total_users: number;
  total_vehicle_events: number;
  total_person_events: number;
  total_alerts: number;
  watchlist_entries: number;
}