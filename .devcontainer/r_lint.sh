#!/bin/bash
# Wrapper for lintr::lint() — called from .zed/tasks.json to avoid
# quoting issues when Zed passes R expressions through bash -i -c.
Rscript -e "lintr::lint('$1')"
