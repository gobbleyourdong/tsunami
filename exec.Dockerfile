FROM node:20-slim

# Python + common tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv \
    curl git jq \
    && rm -rf /var/lib/apt/lists/*

# Common global npm packages
RUN npm install -g typescript vite

# Set working directory
WORKDIR /workspace

# Non-root user for safety
RUN useradd -m sandbox
USER sandbox

CMD ["bash"]
