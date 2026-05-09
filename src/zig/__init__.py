"""noidle.app — keep your status fresh.

Single source of truth for the project version. Importers (updater.py,
noidle.py launcher, packaging) should reference `zig.__version__`
rather than hardcoding their own copies.
"""
__version__ = "0.3.8"
