.PHONY: test install


install:
	pip install -r requirements-devel.txt

test:
	py.test

lint:
	flake8 mockssh/
