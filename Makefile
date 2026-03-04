.PHONY: up down logs bridge-test lint bootstrap-sheets prepare-env preflight test-mock import-workflows phase2-real-setup phase2-stage-a phase2-stage-b phase2-stage-c phase2-stage-d phase2-gate phase2-status

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

bridge-test:
	cd bridge && python3 -m pytest -q

lint:
	python3 -m compileall bridge/app

bootstrap-sheets:
	./scripts/bootstrap_sheets.sh ./sheets/seed

prepare-env:
	./scripts/prepare_beginner_env.sh

preflight:
	./scripts/preflight_check.sh

test-mock:
	./scripts/test_mock_flow.sh

import-workflows:
	./scripts/import_workflows.sh

phase2-real-setup:
	./scripts/phase2_real_setup.sh

phase2-stage-a:
	./scripts/phase2_stage_activate.sh --stage A

phase2-stage-b:
	./scripts/phase2_stage_activate.sh --stage B

phase2-stage-c:
	./scripts/phase2_stage_activate.sh --stage C

phase2-stage-d:
	./scripts/phase2_stage_activate.sh --stage D

phase2-gate:
	./scripts/phase2_day1_gate.sh

phase2-status:
	./scripts/phase2_stage_activate.sh --stage status
