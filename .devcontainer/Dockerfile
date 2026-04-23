FROM condaforge/miniforge3:latest

# This image is the single source of truth for both the dev container and
# the run.py host-invoked workflow. Everything the project needs at runtime
# (conda env, R packages, Node/Claude Code, R itself) is baked in at build
# time so `docker compose run --rm app ...` and the dev container terminal
# see identical tools.

# Create the non-root vscode user with passwordless sudo. The condaforge
# base image runs as root, so this mirrors what devcontainers/base gives
# out of the box.
#
# condaforge/miniforge3 now ships a pre-existing `mambauser` at UID 1000
# (added in their image in 2024). Plain `groupadd --gid 1000 vscode` fails
# with "GID already exists", so handle three cases:
#   (1) vscode already exists — do nothing
#   (2) a different user owns UID 1000 — rename it to vscode and move $HOME
#   (3) UID 1000 is unclaimed — create vscode fresh
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID
RUN apt-get update \
    && apt-get install -y --no-install-recommends sudo \
    && if id -u $USERNAME >/dev/null 2>&1; then \
         echo "User $USERNAME already exists, skipping creation"; \
       elif existing=$(getent passwd $USER_UID | cut -d: -f1) && [ -n "$existing" ]; then \
         echo "Renaming existing UID $USER_UID user '$existing' to $USERNAME" \
         && groupmod -n $USERNAME "$(id -gn $existing)" \
         && usermod -l $USERNAME -d /home/$USERNAME -m $existing; \
       else \
         groupadd --gid $USER_GID $USERNAME \
         && useradd --uid $USER_UID --gid $USER_GID -m -s /bin/bash $USERNAME; \
       fi \
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

# NOTE: R package install (renv::restore) is deliberately NOT baked into the
# image. It's run from postCreateCommand in devcontainer.json against a
# docker volume mounted at /usr/local/lib/R/site-library, so:
#   (1) failures there don't block the image build,
#   (2) R package changes don't force a full image rebuild,
#   (3) the slow compile step only runs once per container recreation, not
#       on every image rebuild.
# The image still ships r-base + r-base-dev (above) so R itself is available
# immediately; only the add-on packages are deferred.

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

# Install GitHub CLI (gh). Container does not bind-mount host SSH keys;
# instead, contributors authenticate once with `gh auth login` (device flow),
# and gh acts as git's credential helper for HTTPS operations. gh's auth
# state lives in /home/vscode/.config/gh which is mounted from a named
# docker volume, so the login persists across container rebuilds without
# exposing host credentials.
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        -o /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*

# Put the equitable-polls conda env on PATH for every shell type (login,
# non-login, non-interactive). Zed launches tool processes without sourcing
# .bashrc, so /etc/profile.d is the reliable place. Listing the env bin dir
# first makes pytest, pylint, and python resolve to the project env.
RUN echo 'export PATH="/opt/conda/envs/equitable-polls/bin:/opt/conda/bin:$PATH"' > /etc/profile.d/conda-path.sh && \
    chmod +x /etc/profile.d/conda-path.sh

# Pre-create mount parent directories as vscode-owned. Without this, Docker
# creates intermediate directories for bind mounts (like /home/vscode/.config/
# for the gcloud mount) as root-owned, which then prevents other tools from
# writing siblings (e.g. Zed's remote server needs /home/vscode/.config/zed).
RUN mkdir -p /home/$USERNAME/.config /home/$USERNAME/.config/gh /home/$USERNAME/.claude && \
    chown -R $USERNAME:$USERNAME /home/$USERNAME/.config /home/$USERNAME/.claude

USER $USERNAME
WORKDIR /workspaces
