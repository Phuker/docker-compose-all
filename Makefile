PYTHON = python3

.PHONY: all uninstall clean build install dev-install upload
.NOTPARALLEL:

all: uninstall clean build install

uninstall:
	$(PYTHON) -m pip uninstall -y docker-compose-all

clean:
	rm -rf *.egg-info dist

build: clean
	uvx --from build pyproject-build --installer uv
	rm -rf *.egg-info

install: uninstall clean build
	$(PYTHON) -m pip install dist/*.whl
	$(PYTHON) -m pip show docker-compose-all

dev-install: uninstall clean
	$(PYTHON) -m pip install -e .
	rm -rf *.egg-info

upload:
	$(PYTHON) -m twine check dist/*.whl dist/*.tar.gz
	$(PYTHON) -m twine upload dist/*.whl dist/*.tar.gz
