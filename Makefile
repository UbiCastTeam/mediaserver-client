
lint:
	docker run -v ${CURDIR}:/apps registry.ubicast.net/docker/flake8:latest make lint_local

lint_local:
	flake8 .

deadcode:
	docker run -v ${CURDIR}:/apps registry.ubicast.net/docker/vulture:latest make deadcode_local

deadcode_local:
	vulture --exclude .eggs --min-confidence 90 .

test:
	docker run -v ${CURDIR}:/apps registry.ubicast.net/docker/pytest:latest make test_local

test_local:
	pytest tests/ -vv --color=yes --log-level=DEBUG --cov=ms_client ${PYTEST_ARGS}

build: clean
	python setup.py sdist bdist_wheel

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
