check:
	flake8 src/ --count --max-complexity=10 --max-line-length=120 --statistics

build: check
	rm --force dist/*
	python -m build

release-pypi-test: build
	python -m twine upload --repository testpypi dist/*

release-pypi-main: build
	python -m twine upload dist/*
