PYTHON = python3

.PHONY: default reinstall install upload uninstall rebuild build clean

default:
	make rebuild
	make install
	make clean

reinstall:
	make uninstall
	make rebuild
	make install
	make clean

install: dist/*.whl
	$(PYTHON) -m pip install dist/*.whl
	$(PYTHON) -m pip show docker-compose-all

upload: dist/*.whl dist/*.tar.gz
	$(PYTHON) -m twine check dist/*.whl dist/*.tar.gz
	# username is: __token__
	$(PYTHON) -m twine upload dist/*.whl dist/*.tar.gz

uninstall:
	$(PYTHON) -m pip uninstall -y docker-compose-all

rebuild build dist/*.whl dist/*.tar.gz: ./setup.py ./docker_compose_all.py
	# make sure clean old versions
	make clean

	$(PYTHON) ./setup.py sdist bdist_wheel

	# 'pip install' is buggy when .egg-info exist
	rm -rf *.egg-info build

clean:
	rm -rf *.egg-info build dist
