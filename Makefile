run_strategy:
	arb --log-level CRITICAL check \
		--min-profit 0.02 \
		--trade-size 800  \
		--watch \
		--execute-buy \
		--execute-sell \
		--async-execution 

lint:
	poetry run pylama tests olas_arbitrage

fmt:
	poetry run isort tests olas_arbitrage
	poetry run autoflake tests olas_arbitrage --remove-all-unused-imports -r --in-place
	poetry run black tests olas_arbitrage

	cd olas_arbitrage/aea_contracts_solana && make fmt

test: 
	poetry run pytest tests -vv

all: fmt lint test clean

run_report_gsheet:
	arb report --time-of-report '17:00' --repeat

run_report_slack:
	arb report --time-of-report '19:00' --repeat --output slack


run_gno:
	arb --log-level CRITICAL check --config-file gno_config.json --trade-size 1 --watch --execute  --min-profit 0.03

run_polygon:
	arb --log-level CRITICAL check \
		--config-file configs/polygon_config.json \
		--trade-size 100 \
		--min-profit 0.035 \
		--watch \
		--execute-buy \
		--execute-sell \
		--async-execution 

run_solana:
	arb --log-level CRITICAL check \
		--config-file configs/solana_config.json \
		--trade-size 200 \
		--min-profit 0.03 \
		--execute-buy \
		--execute-sell \
		--watch 


run_all:
	docker-compose --profile olas up --build --force-recreate -d --remove-orphans


run_from_env:
	arb run-from-env

clean:
	cd olas_arbitrage/aea_contracts_solana && make clean


release:
	$(eval current_version := $(shell poetry run tbump current-version))
	@echo "Current version is $(current_version)"
	$(eval new_version := $(shell python -c "import semver; print(semver.bump_patch('$(current_version)'))"))
	@echo "New version is $(new_version)"
	poetry run tbump $(new_version)

deploy:
	# helm upgrade  arber charts/arbitrage/ -n auto-arbs --create-namespace --install --values charts/arbitrage/ETH_L2-config_list.yaml
	kubectl create ns auto-arbs || echo "Namespace already exists"
	kubectl create secret generic regcred \
         --from-file=.dockerconfigjson=/home/$(shell whoami)/.docker/config.json \
         --type=kubernetes.io/dockerconfigjson -n auto-arbs  || echo "Secret already exists"
	kubectl apply -f ../ARB_ENV/config_map.yaml -n auto-arbs
	helm upgrade  l2-arber charts/arbitrage/ -n auto-arbs --create-namespace --install \
		--values charts/arbitrage/config_list.yaml


generate_configs:
	rm -rf configs/generated/*
	poetry run python scripts/config_generator.py
	poetry run fish scripts/validate_configs.fish
