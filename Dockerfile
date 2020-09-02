FROM ubuntu:18.04
LABEL maintainer="Kitware, Inc. <kitware@kitware.com>"

# See logs faster; don't write pyc or pyo files
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && \
    apt-get install --no-install-recommends --yes \
    software-properties-common \
    gpg-agent \
    fonts-dejavu \
    libmagic-dev \
    git \
    # libldap2-dev \
    # libsasl2-dev \
    curl \
    ca-certificates \
    fuse \
    vim && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN curl -LJ https://github.com/krallin/tini/releases/download/v0.19.0/tini -o /usr/bin/tini && \
    chmod +x /usr/bin/tini

RUN add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install --no-install-recommends --yes \
    python3.7 \
    python3.7-distutils && \
    curl --silent https://bootstrap.pypa.io/get-pip.py -O && \
    python3.7 get-pip.py && \
    rm get-pip.py && \
    rm /usr/bin/python3 && \
    ln -s /usr/bin/python3.7 /usr/bin/python3 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN curl -sL https://deb.nodesource.com/setup_12.x | bash && \
    apt-get update && \
    apt-get install --no-install-recommends --yes \
    nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# add a directory for girder mount
RUN mkdir -p /fuse --mode=a+rwx

RUN mkdir -p nci_seer && \
    mkdir -p /conf

WORKDIR nci_seer

COPY . .

# By using --no-cache-dir the Docker image is smaller
RUN pip install --pre --no-cache-dir \
    # Until https://github.com/cherrypy/cheroot/issues/312 is resolved.
    cheroot!=8.4.3,!=8.4.4 \
    # git+https://github.com/DigitalSlideArchive/NCI-SEER-Pediatric-WSI-Pilot.git \
    . \
    # girder[mount] adds dependencies to show tiles from S3 assets \
    girder[mount] \
    # Add additional girder plugins here \
    girder-homepage \
    # Use prebuilt wheels whenever possible \
    --find-links https://girder.github.io/large_image_wheels

# Build the girder web client
RUN girder build && \
    # Git rid of unnecessary files to keep the docker image smaller \
    find /usr/local/lib/python3.7 -name node_modules -exec rm -rf {} \+ && \
    rm -rf /tmp/npm*

COPY ./devops/nciseer/girder.local.conf ./devops/nciseer/provision.py /conf/

ENTRYPOINT ["/usr/bin/tini", "--"]

CMD python3 /conf/provision.py && (girder mount /fuse || true) && girder serve
