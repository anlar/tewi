check:
	flake8 src/ --count --max-complexity=10 --max-line-length=150 --statistics
