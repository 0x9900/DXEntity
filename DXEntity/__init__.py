#
# pylint: disable=invalid-name
from importlib.metadata import PackageNotFoundError, version

from ._dxentity import *  # noqa: F403,F401

try:
  __version__ = version("DXEntity")
except PackageNotFoundError:
  # If the package is not installed, don't add __version__
  pass
