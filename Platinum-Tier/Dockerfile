FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Install Node.js dependencies for MCP servers
WORKDIR /app/mcp-servers/email-mcp
RUN npm install

WORKDIR /app/mcp-servers/social-mcp-fb
RUN npm install

WORKDIR /app/mcp-servers/social-mcp-ig
RUN npm install

WORKDIR /app/mcp-servers/social-mcp-x
RUN npm install

WORKDIR /app/mcp-servers/browser-social-mcp
# No npm install needed - using Python-based authentication

WORKDIR /app

# Create necessary directories for the vault system
RUN mkdir -p data/Inbox \
    data/Needs_Action/cloud \
    data/Needs_Action/local \
    data/Pending_Approval/local \
    data/Approved \
    data/Rejected \
    data/Done/cloud \
    data/Done/local \
    data/Plans/cloud \
    data/Plans/local \
    data/Logs \
    data/Accounting \
    data/Briefings \
    data/Docs \
    data/Quarantine \
    data/In_Progress/cloud \
    data/In_Progress/local \
    data/Updates \
    data/Signals

# Set up environment
ENV PYTHONPATH=/app
ENV CLAUDE_CODE_ENV=production

# Expose any necessary ports for MCP servers
EXPOSE 5432 8069 8072 80 443

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD test -d /app/data || exit 1

# Default command - can be overridden for specific services
CMD ["python", "watcher/orchestrator_cloud.py"]