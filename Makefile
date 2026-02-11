.PHONY: run install clean

install:
	pip install -r requirements.txt && pip install -e .

run:
	python -m panda_brain.main

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	rm -rf .venv dist *.egg-info
