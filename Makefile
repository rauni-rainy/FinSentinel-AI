.PHONY: redteam start-backend start-frontend

redteam:
	@echo "Running Adversarial Red-Team Simulator..."
	@cd backend && python scripts/run_redteam_simulation.py

start-backend:
	@cd backend && uvicorn main:app --reload

start-frontend:
	@cd frontend && npm run dev
