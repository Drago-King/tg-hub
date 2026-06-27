"""
Module registry.

Each future module (ordering, calls, study) is a self-contained file in
modules/ that exposes a `register(application)` function. The hub
discovers and registers all of them at startup — so adding a new
capability later means dropping a file in modules/ and adding one line
to MODULE_NAMES below. No changes needed to main.py or the core bot.
"""
import importlib

from utils.logger import log_event

# Add new module filenames here as you build them, e.g.:
# MODULE_NAMES = ["study", "ordering", "calls"]
MODULE_NAMES = ["study", "ordering.ordering", "ordering.swiggy_order_flow"]


def register_all_modules(application):
    for name in MODULE_NAMES:
        try:
            module = importlib.import_module(f"modules.{name}")
            module.register(application)
            log_event(f"Module loaded: {name}")
        except Exception as e:
            log_event(f"Module FAILED to load: {name} ({e})")
