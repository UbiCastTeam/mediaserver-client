PYFILES = ms_client/ examples/

all:

lint:
	flake8 ${PYFILES}

test:
	python3 -m unittest discover tests/ -v

build: clean
	python3 setup.py sdist bdist_wheel

install: build
	pip install -I dist/*.whl

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
