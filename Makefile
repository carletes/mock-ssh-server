.PHONY: test install


install:
	pip install -r requirements-devel.txt

test:
	py.test

coverage:
	py.test --cov=mockssh --cov-report=term-missing

lint:
	flake8 mockssh/
