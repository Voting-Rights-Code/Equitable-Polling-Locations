# Use the correct Docker Hub image name
FROM condaforge/miniforge3:latest

# Install basic system requirements
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create the environment from your existing file
COPY environment.yml requirements.txt ./
RUN mamba env create -f environment.yml && mamba clean -afy

# Set the path so the container uses the environment by default
ENV PATH=/opt/conda/envs/equitable-polls/bin:$PATH

WORKDIR /app
# Note: We don't COPY code here because docker-compose mounts it live.
