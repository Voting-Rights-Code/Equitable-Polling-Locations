FROM mcr.microsoft.com/devcontainers/base:ubuntu-22.04

# Ensure the equitable-polls conda env is on PATH for ALL shell types (login,
# non-login, non-interactive). This is the fix for Zed — it launches tool
# processes (pylint, pytest) without sourcing .bashrc, so the conda feature's
# shell init alone isn't enough. Listing the env bin dir first makes pytest,
# pylint, and python resolve to the project env directly.
RUN echo 'export PATH="/opt/conda/envs/equitable-polls/bin:/opt/conda/bin:/usr/local/share/nvm/current/bin:$PATH"' > /etc/profile.d/conda-path.sh && \
    chmod +x /etc/profile.d/conda-path.sh

WORKDIR /workspaces
