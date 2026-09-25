# API

All endpoints are rooted at `/api/v1/` and return a correlation ID. Initial resources:

- `POST /auth/token/`, `POST /auth/token/refresh/`
- `POST /auth/challenges/`, `POST /auth/challenges/verify/`
- `POST /invitations/`, `POST /invitations/activate/`
- `GET /me/`
- `GET|POST /identities/`
- `GET|POST /assets/`, `POST /assets/{id}/verify/`
- `GET|POST /transfers/`, `POST /transfers/{id}/accept/`, `/reject/`, and `/approve/`
- Inventory catalogue: `/inventory/categories/`, `/subcategories/`, `/catalog/`, `/variants/`, `/locations/`
- Inventory operations: `/inventory/stocks/`, `/requests/`, `/movements/` plus scoped stock/request actions
- `GET /audit/`, `GET /security-alerts/`, `GET /blockchain/transactions/`, `GET /blockchain/health/`
- Read-only Observer: `GET /observer/blocks/`, `/blocks/{number-or-hash}/`, `/transactions/{hash}/`, `/nfts/`, `/analytics/`, and `/search/?q=...`

Errors use `{error: {code, message, details}, correlation_id}`. State-changing requests accept `Idempotency-Key` where retry ambiguity is possible.
