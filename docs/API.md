# API

All endpoints are rooted at `/api/v1/` and return a correlation ID. Initial resources:

- `POST /auth/token/`, `POST /auth/token/refresh/`
- `POST /auth/challenges/`, `POST /auth/challenges/verify/`
- `POST /invitations/`, `POST /invitations/activate/`
- `GET /me/`
- `GET|POST /identities/`
- `GET|POST /assets/`, `POST /assets/{id}/verify/`
- `GET|POST /transfers/`, `POST /transfers/{id}/accept/`, `/reject/`, and `/approve/`
- `GET /audit/`, `GET /security-alerts/`, `GET /blockchain/transactions/`, `GET /blockchain/health/`

Errors use `{error: {code, message, details}, correlation_id}`. State-changing requests accept `Idempotency-Key` where retry ambiguity is possible.
