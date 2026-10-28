# Importing the modules registers their converters. Order matters only when two
# converters can handle the same input/output pair: the first one registered wins.
from . import images, pdf, data, sheets, documents  # noqa: F401
