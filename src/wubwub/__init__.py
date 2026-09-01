"""wubwub: fetch album cover art, render it through a Blender animation, publish the results."""

import logging

# Library convention: emit records but stay silent unless a host app
# configures logging. Without this, the stdlib prints a "no handlers
# found" warning to stderr the first time this package logs anything.
logging.getLogger(__name__).addHandler(logging.NullHandler())
