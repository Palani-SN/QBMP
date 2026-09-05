import sys

if sys.version_info[:2] >= (3, 8):
    # Dead branch under the current `python_requires = >= 3.11` - importlib.metadata
    # has been stdlib since 3.8. Kept only so the fallback below stays available if
    # the floor is ever lowered; collapse both to a direct import otherwise.
    from importlib.metadata import PackageNotFoundError, version  # pragma: no cover
else:
    from importlib_metadata import PackageNotFoundError, version  # pragma: no cover

try:
    # __version__ reflects the INSTALLED distribution, not setup.py in the working
    # tree - a checkout edited past its last install reports the older number until
    # it is reinstalled. Change here if the project is renamed and the distribution
    # name stops matching the package name.
    dist_name = "QBMP"
    __version__ = version(dist_name)
except PackageNotFoundError:  # pragma: no cover
    __version__ = "unknown"
finally:
    del version, PackageNotFoundError
