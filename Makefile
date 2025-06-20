check:
	flake8 src/ --count --max-complexity=10 --max-line-length=120 --statistics
	flake8 tests/ --count --max-complexity=10 --max-line-length=120 --statistics

clean:
	rm --force dist/*

build: check clean
	python -m build

install-pipx: build
	pipx install --force ./dist/tewi_transmission-*-py3-none-any.whl

release-pypi-test: build
	python -m twine upload --repository testpypi dist/*

release-pypi-main: build
	python -m twine upload dist/*
