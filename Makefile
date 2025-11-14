check:
	flake8 src/ --count --max-complexity=10 --max-line-length=120 --statistics
	flake8 tests/ --count --max-complexity=10 --max-line-length=120 --statistics

test:
	python -m pytest -v

clean:
	rm --force dist/*

build: check test clean
	python -m build

install-pipx: build
	pipx install --force ./dist/tewi_transmission-*-py3-none-any.whl

release-pypi-test: build
	python -m twine upload --repository testpypi dist/*

release-pypi-main: build
	python -m twine upload dist/*

docker-up:
	docker compose -f docker/docker-compose.yml up -d

docker-down:
	docker compose -f docker/docker-compose.yml down

docker-remove:
	docker compose -f docker/docker-compose.yml down -v

docker-init:
	./docker/init-torrents.sh

run-transmission:
	PYTHONPATH=src textual run --dev tewi.app:create_app -- --client-type transmission --port 9092

run-qbittorrent:
	PYTHONPATH=src textual run --dev tewi.app:create_app -- --client-type qbittorrent --port 9093 --username admin --password $$(docker logs tewi-qbittorrent-dev 2>&1 | grep 'temporary password' | tail -1 | sed 's/.*: //')
