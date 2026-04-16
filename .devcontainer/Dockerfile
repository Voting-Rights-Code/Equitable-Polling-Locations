FROM mcr.microsoft.com/devcontainers/base:ubuntu-22.04

# R + system libraries needed by R packages.
#
# We install R directly here (via Ubuntu's apt repo) rather than through a
# devcontainer feature (ghcr.io/rocker-org/devcontainer-features/r-apt) because
# the feature install has been unreliable under Zed. This is the R version
# shipped by Ubuntu 22.04 (R 4.1.x); good enough for the analysis scripts in
# R/. If newer R is needed later, swap this for the CRAN apt repo setup.
#
# System libraries for R packages that compile from source:
#   - sf              → libgdal-dev, libproj-dev, libgeos-dev, libudunits2-dev
#   - bigrquery, gargle, googleCloudStorageR (via httr/curl/openssl)
#                     → libssl-dev, libcurl4-openssl-dev
#   - R XML parsing   → libxml2-dev
#   - s2 (sf dep)     → cmake + libabsl-dev (else it tries to build Abseil from
#                       source and fails without cmake)
#   - fs              → cmake + libuv1-dev (else it builds bundled libuv and
#                       fails without cmake)
# These are apt dependencies (not conda) because R links against the system
# versions of these libraries.
RUN apt-get update && apt-get install -y --no-install-recommends \
        cmake \
        libabsl-dev \
        libuv1-dev \
        libgdal-dev \
        libproj-dev \
        libgeos-dev \
        libudunits2-dev \
        libssl-dev \
        libcurl4-openssl-dev \
        libxml2-dev \
        r-base \
        r-base-dev \
    && rm -rf /var/lib/apt/lists/*

# Install R packages from the renv lockfile into the system library (as root).
# renv.lock is the single source of truth for R package versions — equivalent
# to environment.yml for Python. Packages install into the system library so
# they're available to all users without renv project-local isolation.
COPY renv.lock /tmp/renv.lock
RUN Rscript -e "install.packages('renv', repos='https://cloud.r-project.org')" && \
    Rscript -e "renv::restore(lockfile='/tmp/renv.lock', library='/usr/local/lib/R/site-library', prompt=FALSE)" && \
    rm /tmp/renv.lock

# Ensure the equitable-polls conda env is on PATH for ALL shell types (login,
# non-login, non-interactive). This is the fix for Zed — it launches tool
# processes (pylint, pytest) without sourcing .bashrc, so the conda feature's
# shell init alone isn't enough. Listing the env bin dir first makes pytest,
# pylint, and python resolve to the project env directly.
RUN echo 'export PATH="/opt/conda/envs/equitable-polls/bin:/opt/conda/bin:/usr/local/share/nvm/current/bin:$PATH"' > /etc/profile.d/conda-path.sh && \
    chmod +x /etc/profile.d/conda-path.sh

WORKDIR /workspaces
