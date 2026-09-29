# PARKWISE

PARKWISE is a production-structured academic MVP for authenticated parking operations at colleges, offices, malls, hospitals, and other institutions. It combines a FastAPI API, PostgreSQL/SQLite persistence, a role-aware Streamlit dashboard, signed QR tickets, live occupancy derived from parking sessions, and a trusted Random Forest artifact that predicts availability 30 minutes ahead.

> Academic-data notice: the bundled Random Forest model was trained on simulated data. Predictions are labelled as estimates and must not be treated as live guarantees or reservations.

## Features

- JWT authentication with access/refresh token rotation, expiration, and server-side revocation
- Argon2 password hashing and role-based access control for `ADMIN`, `ATTENDANT`, `STUDENT`, `STAFF`, and `VISITOR`
- Vehicle registration normalization and ownership enforcement
- Transactional entry, unique digital tickets, automatic zone/slot assignment, and QR PNG generation
- Transactional QR/manual exit, duplicate-exit rejection, and automatic slot release
- Live facility, zone, and vehicle-type occupancy computed from active database sessions
- Find My Vehicle with exact facility, zone, row, slot, map coordinates, parking diagram, and signed slot-QR confirmation
- Admin facility/zone/slot management, active-session operations, lost-ticket recovery, wrong-slot correction, user management API, reports, CSV export, and audit logs
- Feedback workflow with administrative status updates
- Cached model loading, optional SHA-256 artifact verification, prediction persistence, metrics, and deterministic fallback
- Alembic migrations, pytest integration tests, structured JSON logging, Dockerfiles, and Docker Compose

## Architecture

```text
Browser
  |
  +--> Streamlit frontend (:8501)
          |  Authorization: Bearer <JWT>
          v
       FastAPI backend (:8000)
          |-- auth/RBAC + token revocation
          |-- parking/availability/report services
          |-- signed QR generation and validation
          |-- cached Random Forest inference
          v
       SQLAlchemy 2.x
          |
          +--> PostgreSQL (production/Docker)
          +--> SQLite (local development/tests)
```

The frontend never connects to the database. Menu hiding is only a usability feature; every private API operation is authenticated and authorized again by FastAPI.

## Technology stack

- Python 3.11+
- FastAPI, Uvicorn, Pydantic v2
- SQLAlchemy 2.x, Alembic, PostgreSQL, optional SQLite
- PyJWT and Argon2
- qrcode and Pillow
- Streamlit, pandas, Altair-native charts
- scikit-learn and joblib
- pytest and FastAPI TestClient
- Docker and Docker Compose

## Folder structure

```text
parkwise/
|-- backend/
|   |-- app/
|   |   |-- main.py
|   |   |-- dependencies.py
|   |   |-- core/          # settings, database, JWT/passwords, logging
|   |   |-- models/        # SQLAlchemy models and enums
|   |   |-- schemas/       # Pydantic request/response contracts
|   |   |-- routers/       # REST endpoints
|   |   |-- services/      # parking, occupancy, QR, audit, ML logic
|   |   `-- cli/           # idempotent demo and admin seed commands
|   |-- alembic/
|   |   `-- versions/0001_initial.py
|   |-- alembic.ini
|   |-- requirements.txt
|   `-- Dockerfile
|-- frontend/
|   |-- streamlit_app.py
|   |-- api_client.py
|   |-- app_pages/         # modern st.navigation pages
|   |-- components/
|   |-- .streamlit/
|   |   |-- config.toml
|   |   `-- secrets.toml.example
|   |-- requirements.txt
|   `-- Dockerfile
|-- ml/
|   |-- train.py
|   |-- predict.py
|   |-- model_metrics.json
|   `-- artifacts/
|       |-- parking_model.pkl
|       `-- feature_columns.json
|-- tests/
|-- data/
|-- docker-compose.yml
|-- .env.example
|-- .gitignore
`-- README.md
```

`app_pages/` is intentional: modern Streamlit navigation uses `st.navigation` and avoids the legacy auto-discovered `pages/` behavior.

## Local installation

From the `parkwise` directory with Python 3.11 or newer:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
python -m pip install -r frontend\requirements.txt
Copy-Item .env.example .env
Copy-Item frontend\.streamlit\secrets.toml.example frontend\.streamlit\secrets.toml
```

On macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
python -m pip install -r frontend/requirements.txt
cp .env.example .env
cp frontend/.streamlit/secrets.toml.example frontend/.streamlit/secrets.toml
```

Generate a real secret instead of using the placeholder:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Place that value in `.env` as `JWT_SECRET_KEY`. For local SQLite development, set `.env` to:

```dotenv
DATABASE_URL=sqlite:///./parkwise.db
```

The committed `.env.example` and `secrets.toml.example` contain placeholders only. Never commit `.env`, `secrets.toml`, database dumps, access tokens, or production model secrets.

## Database migrations

Apply migrations:

```powershell
python -m alembic -c backend\alembic.ini upgrade head
```

Check the active revision:

```powershell
python -m alembic -c backend\alembic.ini current
```

Create a future migration after changing models:

```powershell
python -m alembic -c backend\alembic.ini revision --autogenerate -m "describe change"
```

Production startup runs migrations; the API does not call `create_all()` and does not silently recreate production tables.

## Seed administrator and demo data

No demo passwords are embedded in source. After migrations, run the idempotent demo seed:

```powershell
python -m backend.app.cli.seed
```

It creates ADMIN, ATTENDANT, STUDENT, STAFF, and VISITOR users; a 100-capacity two-wheeler facility; two zones with 50 slots each; signed slot QR codes; three vehicles; completed historical sessions; a simulated prediction; and feedback. New passwords are generated at seed time and printed once as development-only credentials. Existing credentials are not reset or printed on repeat runs. Do not reuse development credentials outside local environments.

For a custom admin, use `python -m backend.app.cli.seed_admin --email admin@example.org`; it prompts for a password without echoing and does not seed the full demo dataset.

### Complete demonstration workflow

1. Copy `.env.example` to `.env`, replace the secret/database placeholders, and choose PostgreSQL or SQLite.
2. Start PostgreSQL if selected, apply migrations, then run `python -m backend.app.cli.seed`.
3. Start FastAPI and Streamlit in separate terminals; open `http://localhost:8501`.
4. Sign in as ADMIN using the credential printed by the seed. The seeded facility has two 50-space two-wheeler zones and 100 QR-labelled slots. Admin pages support adding facilities, zones, slots, and user roles.
5. Sign in as seeded STUDENT or STAFF. A two-wheeler is already registered; users can register additional vehicles.
6. Start entry from the dashboard. PARKWISE assigns an available compatible slot and creates a ticket. View or download the signed ticket QR from “My parking ticket”.
7. Check Live availability, use Find My Vehicle to view the facility/zone/row/slot, and submit feedback.
8. Open Dashboard → Exit parking, enter the ticket ID, scan its ticket QR with an external scanner, and paste the decoded token. The API validates the signed QR, marks the session COMPLETED, frees the slot, and refreshes availability.
9. Sign in as ADMIN to review active and historical sessions, occupancy, reports, CSV exports, feedback, and 30-minute predictions.

Seeded historical sessions and prediction examples make reports available immediately. They are demo records; use the seeded student/staff account for a clean entry/exit walkthrough.

## Run commands

Backend:

```powershell
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend in a second terminal:

```powershell
python -m streamlit run frontend\streamlit_app.py --server.port=8501
```

Open:

- Streamlit: `http://localhost:8501`
- OpenAPI/Swagger (development only): `http://localhost:8000/docs`
- ReDoc (development only): `http://localhost:8000/redoc`
- Health check: `http://localhost:8000/health`

## Docker Compose

Copy `.env.example` to `.env`, replace every credential/secret placeholder, then run:

```powershell
docker compose up --build
```

Compose starts PostgreSQL on localhost:5432 with a persistent named volume, runs Alembic before the API, waits for health checks, and then starts Streamlit. Avoid exposing PostgreSQL outside a trusted development network.

To start only PostgreSQL for native development:

```powershell
docker compose up -d postgres
```

With `.env` using the PostgreSQL URL in `.env.example`, run the host migration and seed commands.

## Application URLs

- Streamlit frontend: `http://localhost:8501`
- FastAPI API: `http://localhost:8000`
- Swagger API docs: `http://localhost:8000/docs` (development/test only)
- ReDoc API docs: `http://localhost:8000/redoc` (development/test only)
- PostgreSQL: `localhost:5432`

Set `ENVIRONMENT=production` to disable Swagger and ReDoc. Deploy behind HTTPS and publish only required frontend/reverse-proxy and API ports.

## Tests

```powershell
python -m pytest -q tests
python -m pytest --cov=backend.app --cov-report=term-missing tests
```

The integration suite uses an isolated SQLite database and covers registration, hashing, login failure, JWT validation, all five demo roles, RBAC, facilities/zones/slots, entry/full/duplicate sessions, QR rejection, successful and rejected QR exits, ownership, staff-assisted exits, slot release, availability updates, recovery, slot correction, occupancy, isolation, idempotent seeding, reports, CSV, predictions, and Streamlit navigation. From macOS/Linux, `pytest -q` also works from the project root.

The current development environment emits a `StarletteDeprecationWarning` while importing FastAPI's `TestClient`: Starlette's `starlette.testclient` currently uses its `httpx` integration and recommends `httpx2`. It is an upstream test-client dependency warning, not a PARKWISE runtime warning; tests still pass. The inspected environment had FastAPI 0.141.1, Starlette 1.7.0, and httpx 0.28.1. No dependency replacement was made as part of this exit-flow change.

## QR operation

- Self-service entry uses a signed slot QR: select a registered vehicle and facility on the Dashboard, scan the printed slot label, and submit the decoded token. The API verifies the signature and assigns only that scanned slot; invalid, expired, occupied, or incompatible slots are rejected.
- Entry creates a random `PW-<UUID>` ticket reference.
- Ticket and slot QR codes contain signed, expiring references only—never passwords, names, email addresses, phone numbers, or registration details.
- The API validates signature, token type, expiry, and referenced ticket/slot; Streamlit validation is not trusted.
- Ticket PNG: `GET /api/parking/session/{ticket_id}/qr.png`
- Slot generation: `POST /api/slots/{slot_id}/qr`
- Slot PNG: `GET /api/slots/{slot_id}/qr.png`
- QR exit: authenticated `POST /api/parking/exit` with the ticket ID and signed ticket QR token. The owner can exit their own session; ADMIN and ATTENDANT can assist with another driver's exit.
- The Dashboard accepts external scanner output as text for both entry and exit; native device-camera scanning is not included.
- Exit responses include the ticket, vehicle registration/type, assigned slot, entry and exit times, and parking duration. The session completion and slot release are committed in one database transaction, so live availability reflects the release.

## ML workflow

The API loads the configured model once per process through an LRU-cached loader. It does not retrain on Streamlit reruns. Inference uses current database occupancy and facility metadata, stores a 30-minute prediction, and later records an observed value when the target time has passed.

Run offline training explicitly:

```powershell
python -m ml.train --data data\parking.csv --output ml\artifacts
```

For production, compute the approved artifact's SHA-256 digest and set `ML_MODEL_SHA256`. Python pickle/joblib artifacts can execute code during deserialization, so only a reviewed local artifact with a verified checksum should be deployed. If loading or inference fails, PARKWISE stores a clearly versioned capacity-based fallback rather than crashing.

## Default development workflow

1. Activate the virtual environment and load `.env`.
2. Apply `alembic upgrade head`.
3. Seed an admin, optionally with demo parking data.
4. Start FastAPI and confirm `/health`.
5. Start Streamlit and sign in.
6. Run tests before committing changes.
7. Add a reviewed Alembic revision for every schema change.

## Security decisions

- **Passwords:** Argon2 hashes only; plain-text passwords are never persisted or logged.
- **Tokens:** short-lived access tokens include `sub`, `role`, `type`, `jti`, issue time, and expiry. Refresh tokens are rotated and the prior token is revoked. Logout revokes presented tokens and clears Streamlit session state.
- **Authorization:** ownership checks protect tickets, history, location, vehicles, and feedback. Administrative mutations use server-side role dependencies.
- **Database invariants:** partial unique indexes prevent simultaneous active sessions for one vehicle or one slot. Check constraints enforce capacity and exit-time consistency.
- **Transactions/concurrency:** entry and exit lock selected records where supported, update the session and slot in one commit, and rely on database uniqueness as the final race-condition guard.
- **QR privacy:** signed references contain no personal data. Every scan is validated by the API.
- **Secrets:** environment variables or Streamlit secrets only. The application refuses JWT secrets shorter than 32 characters.
- **CORS:** explicit origins only; wildcard origins are rejected.
- **Errors/logging:** validation errors are sanitized, unexpected errors return a generic response, and structured logs avoid passwords and tokens.
- **Rate limiting:** a process-local login limiter protects the academic MVP. Production must use a shared Redis/API-gateway limiter because in-memory counters do not coordinate across workers.
- **API docs:** disabled automatically when `ENVIRONMENT=production`.
- **Transport:** deploy only behind HTTPS with HSTS and HTTP-to-HTTPS redirection. If tokens are later moved to browser cookies, use `Secure`, `HttpOnly`, `SameSite=Lax/Strict`, short lifetimes, and CSRF protection.
- **Secret rotation:** deploy a new JWT secret during a maintenance window, restart all API instances, and require users to sign in again. For zero-downtime rotation, add a key ID (`kid`) and overlapping old/new verification keys.
- **Backups:** use encrypted PostgreSQL backups, test restores regularly, apply retention rules, restrict backup access, and back up before migrations.

## Deployment notes

- Use managed PostgreSQL, a reverse proxy/load balancer, HTTPS certificates, centralized logs, and an external secrets manager.
- Run multiple Uvicorn workers only after moving rate limits and token revocation to shared storage such as Redis.
- Run Alembic once as a release job rather than concurrently in every replica.
- Set `CORS_ORIGINS` to exact deployed frontend origins.
- Mount or bake in only a trusted, checksum-pinned model artifact.
- Add database monitoring, connection-pool limits, backup alerts, and audit-log retention.

## Current limitations

- The prediction artifact and metrics originate from simulated historical data.
- Occupancy is transaction-derived, not fed by physical gate sensors or cameras.
- QR scanning is represented by submitting scanned token text; native mobile camera integration is not included.
- The local login rate limiter and database token revocation are appropriate for the academic MVP, not a high-scale cluster.
- Printable output is a QR PNG plus ticket details; branded PDF tickets are a future enhancement.

## College rollout plan

### Phase 1: Digital registration

- Register facilities and zones with capacity by vehicle type.
- Create student, staff, visitor, attendant, and approved administrator accounts.
- Register vehicle details and print QR labels for tickets, slots, and parking areas.
- Compare configured zone totals with the physical parking layout.

### Phase 2: Controlled pilot

- Begin with one parking area, one entrance, one exit, and one attendant.
- Ask drivers/attendants to complete entry and exit scans.
- Compare application occupancy with physical counts each day and correct exceptions.
- Collect feedback and document failure cases before expanding.

### Phase 3: Campus deployment

- Add all approved campus parking areas and permanent, weather-resistant labels.
- Train security and parking attendants and post entry/exit instructions.
- Provide an attendant tablet or phone with managed access.
- Review occupancy, active sessions, feedback, and audit logs daily.

### Phase 4: Advanced deployment

- Add physical sensors or camera verification and number-plate recognition where approved.
- Add payments, notifications, or campus analytics if needed.
- Retrain and validate the prediction model on real campus history before operational use.
- Deploy behind HTTPS with managed PostgreSQL, tested backups, monitoring, access reviews, and privacy/retention controls.

The academic MVP can support a small staff-assisted college pilot. A QR scan alone does not prove a vehicle physically occupies its assigned slot. The initial release relies on users or attendants completing entry and exit scans; sensors or cameras are needed for automated occupancy verification. Real operation also requires data-protection and retention policies, tested backups, HTTPS, monitoring, trained staff, and real historical data to retrain and validate predictions.

Before a large production rollout, add distributed rate limiting and token revocation, SSO/MFA, verified signed model artifacts, background jobs, external audit storage, observability and alerts, high-availability database operations, and mobile camera scanning.

## Future production improvements

- Redis-backed distributed rate limiting, token revocation, and caching
- OIDC/SSO, MFA, device/session management, and password-reset/email-verification flows
- Dedicated immutable audit pipeline and SIEM integration
- Physical gate, ANPR, camera, payment, reservation, and IoT sensor integrations
- Native mobile QR scanner and offline attendant mode
- Background job queue for prediction scheduling, reconciliation, exports, and notifications
- Model registry, signed artifacts, drift monitoring, retraining approvals, and per-facility calibration
- High-availability PostgreSQL, read replicas, automated encrypted backups, and restore drills
- Observability with OpenTelemetry traces, metrics, dashboards, and alerting
- Kubernetes manifests, autoscaling, network policies, and managed secret rotation
- Branded printable PDF tickets and accessible wayfinding diagrams
