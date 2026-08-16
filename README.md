# FinSentinel AI

A multi-agent financial operations platform.

## Getting Started

To run the application locally:

1. Ensure you have Docker and Docker Compose installed.
2. Run the following command from the root directory:
   ```bash
   docker compose up --build
   ```

### Services
- **Frontend**: [http://localhost:3000](http://localhost:3000)
- **Backend**: [http://localhost:8000](http://localhost:8000) (Health check: `/health`)
- **Database**: PostgreSQL on port 5432 (with `pgvector`)
