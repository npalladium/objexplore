all: check format

check:
	mypy objexplore
	flake8 objexplore/
	flake8 tests/
format-check:
	black --check .
format:
	black .
publish:
	python3 setup.py sdist bdist_wheel
	twine upload --skip-existing dist/*
pytest:
	PYTHONPATH=PYTHONPATH:$(pwd) pytest tests/
test:
	python3 -c "import objexplore; import rich; objexplore.explore(rich)"
test-pandas:
	python3 -c "import objexplore; import pandas; objexplore.explore(pandas.DataFrame())"
