DOCKER_RUN ?= docker run \
	--name ms-client-builder \
	--workdir /apps \
	--mount type=bind,src=${PWD},dst=/apps \
	--user "$(shell id -u):$(shell id -g)" \
	--rm -it

lint:
	${DOCKER_RUN} registry.ubicast.net/docker/flake8:latest make lint_local

lint_local:
	flake8 .

deadcode:
	${DOCKER_RUN} registry.ubicast.net/docker/vulture:latest make deadcode_local

deadcode_local:
	vulture --exclude .eggs --min-confidence 90 .

test:
	${DOCKER_RUN} -e "PYTEST_ARGS=${PYTEST_ARGS}" registry.ubicast.net/docker/pytest:latest make test_local

test_local:
	pytest tests/ -vv --color=yes --log-level=DEBUG --cov=ms_client ${PYTEST_ARGS}

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
