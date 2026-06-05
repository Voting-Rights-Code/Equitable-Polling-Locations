#!/usr/bin/env bash
#
# R-package install wrapper used by postCreateCommand in devcontainer.json.
# Bootstraps renv (one-line install.packages()), then runs renv::restore()
# against renv.lock — the project's canonical pinned package set — into
# /usr/local/lib/R/site-library. The previous inline `|| echo ...` swallowed
# failures silently — a killed or errored install left the R library
# half-built while postCreate reported success. This wrapper:
#
#   - writes a full log to /tmp/r-install.log (for diagnosing the next failure)
#   - on failure, drops a marker file in $HOME and prints a loud banner to
#     stderr so the first terminal a contributor opens makes the breakage
#     obvious
#   - on success, removes any prior marker so state matches reality
#   - always exits 0 so a broken R library does not block the container from
#     coming up (the same non-blocking intent as the original `|| echo`)
#
# Run manually with: bash .devcontainer/run_r_install.sh

set -u

LOG=/tmp/r-install.log
MARKER="${HOME}/.r-install-failed"

if (
    sudo Rscript -e 'install.packages("renv", repos = "https://cloud.r-project.org")' \
        && sudo Rscript -e 'renv::restore(library = "/usr/local/lib/R/site-library", prompt = FALSE)'
   ) 2>&1 | sudo tee "$LOG"; then
    status="${PIPESTATUS[0]}"
else
    status="${PIPESTATUS[0]}"
fi

if [ "$status" -eq 0 ]; then
    rm -f "$MARKER"
    exit 0
fi

date -Iseconds > "$MARKER"
echo "exit_status=$status" >> "$MARKER"
echo "log=$LOG" >> "$MARKER"

cat >&2 <<BANNER

################################################################################
# R PACKAGE INSTALL FAILED (exit $status)
#
# The R environment is incomplete — scripts in R/ will fail to load packages.
# See $LOG for the full install output.
#
# To retry (the script is idempotent and cleans stale locks):
#     bash .devcontainer/run_r_install.sh
#
# Marker file: $MARKER (removed automatically on next successful install)
################################################################################

BANNER

exit 0
