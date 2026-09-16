"""Jarvis: a personal daily-ops assistant built from small, testable pieces.

Each module is a CLI (`python -m jarvis.<name>`) so n8n can call it from an Execute
Command node and a person can run it by hand. Nothing here sends a message, places a
trade or writes to an account on its own; those steps are drafts or explicit flags.
"""
