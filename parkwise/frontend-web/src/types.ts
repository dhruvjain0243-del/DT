export type Role = "ADMIN" | "ATTENDANT" | "STUDENT" | "STAFF" | "VISITOR";
export type VehicleType = "CAR" | "MOTORCYCLE" | "BICYCLE" | "VAN" | "EV" | "ACCESSIBLE";
export type SlotStatus = "AVAILABLE" | "OCCUPIED" | "RESERVED" | "OUT_OF_SERVICE";
export type GateType = "ENTRY" | "EXIT" | "BOTH";
export type ScanType = "ENTRY" | "EXIT";
export type ScanResult = "SUCCESS" | "FAILED";

export interface User { id: number; full_name: string; email: string; role: Role; is_active: boolean; }
export interface Tokens { access_token: string; refresh_token: string; expires_in: number; user: User; }
export interface Vehicle { id: number; user_id: number; registration_number: string; vehicle_type: VehicleType; }
export interface Facility { id: number; name: string; address: string; total_capacity: number; latitude: number | null; longitude: number | null; distance_km: number; price_per_hour: number; is_active: boolean; }
export interface Zone { id: number; facility_id: number; name: string; vehicle_type: VehicleType; capacity: number; is_active: boolean; }
export interface Slot { id: number; zone_id: number; row_label: string | null; slot_code: string; status: SlotStatus; qr_code_value: string | null; is_active: boolean; }
export interface Availability { facility_id: number; facility_name: string; total_capacity: number; occupied_spaces: number; available_spaces: number; occupancy_percentage: number; last_update_time: string; zones: { zone_id: number; zone_name: string; vehicle_type: VehicleType; total_capacity: number; occupied_spaces: number; available_spaces: number; occupancy_percentage: number }[]; }
export interface Ticket { id: number; ticket_id: string; user_id: number; vehicle_id: number; facility_id: number; zone_id: number; slot_id: number; entry_time: string; exit_time: string | null; status: string; entry_method: string; facility_name: string; zone_name: string; row_label: string | null; slot_code: string; registration_number: string; qr_token: string; qr_png_base64: string; }
export interface ExitResult { ticket_id: string; status: string; registration_number: string; vehicle_type: VehicleType; slot_id: number; slot_code: string; entry_time: string; exit_time: string; duration_minutes: number; message: string; }
export interface Prediction { id: number; facility_id: number; zone_id: number | null; prediction_time: string; target_time: string; predicted_available_spaces: number; actual_available_spaces: number | null; model_version: string; }
export interface Metrics { baseline_mae: number | null; model_mae: number | null; model_rmse: number | null; model_r2: number | null; dataset_type: string; prediction_horizon_minutes: number; }
export interface Gate { id: number; facility_id: number; name: string; gate_type: GateType; is_active: boolean; created_at: string; }
export interface Scanner { id: number; gate_id: number; name: string; device_identifier: string; is_active: boolean; last_seen_at: string | null; created_at: string; api_key?: string; }
export interface ScanEvent { id: number; facility_id: number; gate_id: number; scanner_device_id: number | null; actor_user_id: number | null; session_id: number | null; scan_type: ScanType; result: ScanResult; reference: string | null; failure_reason: string | null; scanned_at: string; }
export interface ScannerSummary { scanner_device_id: number; day: string; success: number; failed: number; entries: number; exits: number; }
