.PHONY: help live record audio config setup pair list

help:
	@echo "Usage:"
	@echo "  make live     - Start live broadcast from microphone"
	@echo "  make record   - Record 10s from mic and stream"
	@echo "  make audio    - Stream audio file (interactive selection)"
	@echo "  make config   - Setup/configure device"
	@echo "  make pair     - Pair with AirPlay device"
	@echo "  make list     - List available devices"

live:
	uv run python main.py --live

record:
	uv run python main.py --record

audio:
	uv run python main.py

config:
	uv run python main.py --setup

setup: config

pair:
	uv run python main.py --pair

list:
	uv run python main.py --list
