FROM python:3.13-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    postgresql-client \
    libpq-dev \
    python3-dev \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libjpeg-dev \
    libldap2-dev \
    libsasl2-dev \
    wget \
    fonts-liberation \
    fonts-noto-core \
    fonts-noto-extra \
    xfonts-75dpi \
    xfonts-base \
    && rm -rf /var/lib/apt/lists/*

# wkhtmltopdf was dropped from Debian's own repos (unmaintained WebKit fork),
# so install the official patched-Qt build directly (bookworm build; runs
# fine on newer Debian bases thanks to glibc backward compatibility).
RUN wget -q https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.bookworm_amd64.deb \
    -O /tmp/wkhtmltox.deb \
    && apt-get update \
    && apt-get install -y /tmp/wkhtmltox.deb \
    && rm -f /tmp/wkhtmltox.deb \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /opt/odoo

# Copy source code
COPY . .

# Install Python dependencies (exclude the Windows-only rl-renderPM line)
RUN grep -v "rl-renderPM" requirements.txt > requirements-linux.txt && \
    pip install --no-cache-dir -r requirements-linux.txt

# Create config directory
RUN mkdir -p /etc/odoo && chmod 755 /etc/odoo

# Copy Odoo config (points db_host at the 'db' compose service)
COPY odoo-docker.conf /etc/odoo/odoo.conf

# Expose ports
EXPOSE 8069 8072

# Default command
CMD ["python", "/opt/odoo/odoo-bin", "-c", "/etc/odoo/odoo.conf"]
