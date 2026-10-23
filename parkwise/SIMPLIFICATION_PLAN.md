# PARKWISE College Parking Simplification Plan

## Baseline

- FastAPI backend, SQLAlchemy models, Alembic migrations, and the existing authenticated parking/scanner APIs are retained.
- The TypeScript/Vite application is the active web client. Streamlit remains available for compatibility but is not the primary interface.
- Existing users, facilities, slots, sessions, audit records, and scanner records are preserved.
- Baseline checks: Python compilation and the frontend TypeScript check are run before implementation; the initial pytest process required a retry because it did not return output.

## Target

1. Expose only a Student/User dashboard and an Admin dashboard in the active web workflow.
2. Use one configured college facility and a two-wheeler slot grid as the source of truth for occupancy.
3. Reuse the existing authenticated entry/exit transaction services, adding explicit source tracking for QR, student-button, and admin-manual actions.
4. Add profile completion/editing, intent-only entry/exit QR links, admin configuration, daily records, and safe CSV/Excel exports.
5. Keep provider-dependent email verification and phone OTP honest: configured providers are required for those flows, and no OTP is returned by the API.
6. Add migration-backed tests for access control, capacity, duplicate/concurrent entry, exit, date filtering, exports, and unconfigured maps.

## Safe cleanup boundary

Prediction, recommendation, pricing, feedback, multi-location, and scanner-management features are removed from the visible application navigation only after the replacement dashboard is verified. Backend routes, migration history, audit data, and existing records remain available for compatibility.
