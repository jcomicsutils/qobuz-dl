# tests/gui/__init__.py
# GUI tests require:  pip install qobuz-dl[dev]  (pulls in pytest-qt + PyQt6)
# Skip this entire directory if PyQt6 is absent:
#
#   pytest tests/gui/ -v
#   # or run everything and let the individual skips fire:
#   pytest -v
