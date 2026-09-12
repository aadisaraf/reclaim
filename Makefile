.PHONY: setup test demo reset record

setup:
	uv sync --locked || uv sync
	cd web && npm install
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		SFTP_PW=$$(uv run python -c "import secrets;print(secrets.token_urlsafe(24))"); \
		HOSP_SEC=$$(uv run python -c "import secrets;print(secrets.token_urlsafe(24))"); \
		PAYER_TOK=$$(uv run python -c "import secrets;print(secrets.token_urlsafe(24))"); \
		sed -i.bak "s/^SFTP_PASSWORD=.*/SFTP_PASSWORD=$$SFTP_PW/" .env; \
		sed -i.bak "s/^HOSPITAL_CLIENT_SECRET=.*/HOSPITAL_CLIENT_SECRET=$$HOSP_SEC/" .env; \
		sed -i.bak "s/^PAYER_TOKEN=.*/PAYER_TOKEN=$$PAYER_TOK/" .env; \
		rm -f .env.bak; \
	fi
	mkdir -p .local/sftp/outbound-835 .local/data
	@if [ ! -f .local/sftp/ssh_host_ed25519_key ]; then \
		ssh-keygen -t ed25519 -N '' -f .local/sftp/ssh_host_ed25519_key; \
	fi
	touch .local/sftp/known_hosts
	cd web && npx playwright install chromium

test:
	uv run pytest
	LLM_MODE=replay docker compose up -d --build --wait
	@STATUS=0; \
	RECLAIM_DOCKER_TESTS=1 uv run pytest -m docker || STATUS=$$?; \
	(cd web && npx playwright test) || STATUS=$$?; \
	docker compose down; \
	exit $$STATUS

demo:
	docker compose up -d --build --wait

reset:
	curl -fsS -X POST localhost:8000/api/demo/reset

record:
	LLM_MODE=live uv run python scripts/record_replay.py
