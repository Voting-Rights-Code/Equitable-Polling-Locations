FROM condaforge/miniforge3:latest

# This image is the single source of truth for both the dev container and
# the run.py host-invoked workflow. Everything the project needs at runtime
# (conda env, R packages, Node/Claude Code, R itself) is baked in at build
# time so `docker compose run --rm app ...` and the dev container terminal
# see identical tools.

# Create the non-root vscode user with passwordless sudo. The condaforge
# base image runs as root, so this mirrors what devcontainers/base gives
# out of the box.
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID
RUN apt-get update \
    && apt-get install -y --no-install-recommends sudo \
    && groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m -s /bin/bash $USERNAME \
    && echo "$USERNAME ALL=(root) NOPASSWD:ALL" > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME \
    && rm -rf /var/lib/apt/lists/*

# System packages:
#   - git, git-lfs: source control + large data files
#   - curl: bootstrap for NodeSource repo
#   - R + system libs: analysis scripts in R/
# R system libs needed by packages that compile from source:
#   - sf              → libgdal-dev, libproj-dev, libgeos-dev, libudunits2-dev
#   - bigrquery et al → libssl-dev, libcurl4-openssl-dev
#   - R XML parsing   → libxml2-dev
#   - s2 (sf dep)     → cmake + libabsl-dev
#   - fs              → cmake + libuv1-dev
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        git-lfs \
        curl \
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

# Install Node.js 20 from NodeSource (for Claude Code). curl must already be
# installed (previous layer).
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install R packages from the renv lockfile into the system library.
# renv.lock lives at the repo root (the single source of truth for R package
# versions — equivalent to environment.yml for Python). The build context is
# the repo root (see .devcontainer/docker-compose.yml), so this COPY reaches
# it as `renv.lock`. Packages install into the system library so they're
# available to all users without renv project-local isolation.
COPY renv.lock /tmp/renv.lock
RUN Rscript -e "install.packages('renv', repos='https://cloud.r-project.org')" && \
    Rscript -e "renv::restore(lockfile='/tmp/renv.lock', library='/usr/local/lib/R/site-library', prompt=FALSE)" && \
    rm /tmp/renv.lock

# Create the conda env at image build time from environment.yml. Baking the
# env in (instead of creating it via postCreateCommand) keeps run.py and the
# dev container in sync: both use the same image, so editing environment.yml
# and rebuilding the image updates both workflows at once.
COPY environment.yml /tmp/environment.yml
RUN mamba env create -n equitable-polls -f /tmp/environment.yml && \
    mamba clean -afy && \
    rm /tmp/environment.yml

# Hand /opt/conda to vscode so that `conda env update` inside the running
# container doesn't need sudo. The env is still backed by the image; for a
# persistent update, rebuild the image.
RUN chown -R $USERNAME:$USERNAME /opt/conda

# Install Claude Code globally (available in the dev container terminal for
# AI-assisted development; idle for run.py invocations).
RUN npm install -g @anthropic-ai/claude-code

# Put the equitable-polls conda env on PATH for every shell type (login,
# non-login, non-interactive). Zed launches tool processes without sourcing
# .bashrc, so /etc/profile.d is the reliable place. Listing the env bin dir
# first makes pytest, pylint, and python resolve to the project env.
RUN echo 'export PATH="/opt/conda/envs/equitable-polls/bin:/opt/conda/bin:$PATH"' > /etc/profile.d/conda-path.sh && \
    chmod +x /etc/profile.d/conda-path.sh

USER $USERNAME
WORKDIR /workspaces
