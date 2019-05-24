PYFILES = ms_client/ examples/

all:

format:
	black ${PYFILES}

lint:
	flake8 ${PYFILES}

develop:
	pip install -e .[dev]

build: clean
	python setup.py sdist bdist_wheel

install: build
	pip install -I dist/mediaserver_api_client-*.whl

publish_dry: build
	twine check dist/*.{whl,tar.gz}
	twine upload -r testubicast --skip-existing dist/*.{whl,tar.gz}

publish: build
	twine check dist/*.{whl,tar.gz}
	twine upload -r ubicast --skip-existing dist/*.{whl,tar.gz}

clean:
	rm -rf .eggs/ build/ dist/ *.egg-info/
	find . -type f -name *.pyc -delete
	find . -type d -name __pycache__ -delete
