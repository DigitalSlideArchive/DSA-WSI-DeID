FROM ubuntu:18.04
LABEL maintainer="Kitware, Inc. <kitware@kitware.com>"

# See logs faster; don't write pyc or pyo files
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -qy tzdata && \
    DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends --yes \
    software-properties-common \
    gpg-agent \
    fonts-dejavu \
    libmagic-dev \
    git \
    # libldap2-dev \
    # libsasl2-dev \
    curl \
    ca-certificates \
    vim \
    # needed for easyocr
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1-mesa-dev \
    && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN curl -LJ https://github.com/krallin/tini/releases/download/v0.19.0/tini -o /usr/bin/tini && \
    chmod +x /usr/bin/tini

RUN add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install --no-install-recommends --yes \
    python3.9 \
    python3.9-distutils && \
    curl --silent https://bootstrap.pypa.io/get-pip.py -O && \
    python3.9 get-pip.py && \
    rm get-pip.py && \
    rm /usr/bin/python3 && \
    ln -s /usr/bin/python3.9 /usr/bin/python3 && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    rm -r ~/.cache

RUN curl -sL https://deb.nodesource.com/setup_12.x | bash && \
    apt-get update && \
    apt-get install --no-install-recommends --yes \
    nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN mkdir -p wsi_deid && \
    mkdir -p /conf

WORKDIR wsi_deid

COPY . .

# By using --no-cache-dir the Docker image is smaller
RUN python3.9 -m pip install --no-cache-dir \
    # git+https://github.com/DigitalSlideArchive/DSA-WSI-DeID.git \
    . \
    # girder[mount] adds dependencies to show tiles from S3 assets \
    # girder[mount] \
    # Add additional girder plugins here \
    # girder-homepage \
    # Use prebuilt wheels whenever possible \
    --find-links https://girder.github.io/large_image_wheels

# Download ocr model
RUN python3.9 -c 'import easyocr;OCRReader = easyocr.Reader(["en"], verbose=False)'

# Build the girder web client
RUN NPM_CONFIG_FUND=false NPM_CONFIG_AUDIT=false NPM_CONFIG_AUDIT_LEVEL=high NPM_CONFIG_LOGLEVEL=warn NPM_CONFIG_PROGRESS=false NPM_CONFIG_PREFER_OFFLINE=true \
    girder build && \
    # Get rid of unnecessary files to keep the docker image smaller \
    find /usr/local/lib/python3.9 -name node_modules -exec rm -rf {} \+ && \
    find /usr/local/lib/python3.9 -name package-lock.json -exec rm -f {} \+ && \
    npm cache clear --force && \
    rm -rf /tmp/npm*

COPY ./devops/wsi_deid/girder.local.conf ./devops/wsi_deid/provision.py ./devops/wsi_deid/homepage.md /conf/

ENTRYPOINT ["/usr/bin/tini", "--"]

CMD python3.9 /conf/provision.py && girder serve
