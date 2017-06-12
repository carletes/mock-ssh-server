.PHONY: test install


install:
	pip install -r requirements-devel.txt

test:
	py.test
