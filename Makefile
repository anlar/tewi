check:
	flake8 src/ --count --max-complexity=10 --max-line-length=120 --statistics

release-pypi-test:
	rm dist/*
	python -m build
	python -m twine upload --repository testpypi dist/*

release-pypi-main:
	rm dist/*
	python -m build
	python -m twine upload dist/*
