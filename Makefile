DOCKER_IMAGE_NAME ?= ms-client:latest
DOCKER_WORK_DIR ?= /opt/src
DOCKER_RUN ?= docker run --rm -it --user "$(shell id -u):$(shell id -g)" -v ${CURDIR}:${DOCKER_WORK_DIR} --name ms-client

build:
	docker build -t ${DOCKER_IMAGE_NAME} ${BUILD_ARGS} .

rebuild:
	BUILD_ARGS="--no-cache" make docker_build

shell:
	${DOCKER_RUN} ${DOCKER_IMAGE_NAME} /bin/sh

lint:
	${DOCKER_RUN} ${DOCKER_IMAGE_NAME} make lint_local

lint_local:
	flake8 .

typing:
	${DOCKER_RUN} ${DOCKER_IMAGE_NAME} make typing_local

typing_local:
	mypy ms_client

deadcode:
	${DOCKER_RUN} ${DOCKER_IMAGE_NAME} make deadcode_local

deadcode_local:
	vulture --exclude .eggs --min-confidence 90 .

test:
	${DOCKER_RUN} -e "PYTEST_ARGS=${PYTEST_ARGS}" ${DOCKER_IMAGE_NAME} make test_local

test_local:PYTEST_ARGS := $(or ${PYTEST_ARGS},--cov=ms_client --cov=examples --no-cov-on-fail --junitxml=report.xml --cov-report xml --cov-report term --cov-report html)
test_local:
	pytest tests/ -vv --color=yes --log-level=DEBUG ${PYTEST_ARGS}

publish:
	make clean
	@mkdir -p .local
	${DOCKER_RUN} \
		-e "TWINE_USERNAME=${TWINE_USERNAME}" \
		-e "TWINE_PASSWORD=${TWINE_PASSWORD}" \
		-v ${PWD}/.local:/.local \
		registry.ubicast.net/docker/pytest:latest make publish_local

publish_local:
	test -z "${TWINE_USERNAME}" \
		&& $echo 'You have to define a value for "TWINE_USERNAME" in your environment' \
		&& exit 1 || true
	test -z "${TWINE_PASSWORD}" \
		&& echo 'You have to define a value for "TWINE_PASSWORD" in your environment' \
		&& exit 1 || true
	pip install build twine
	python -m build
	python -m twine upload --repository pypi -u "${TWINE_USERNAME}" -p "${TWINE_PASSWORD}" dist/*

clean:
	rm -rf .coverage .pytest_cache .local .eggs build dist *.egg-info
	find . -type f -name *.pyc -delete
	find . -type d -name __pycache__ -delete
