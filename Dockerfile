FROM nikolaik/python-nodejs:python3.7-nodejs12
LABEL maintainer="Kitware, Inc. <kitware@kitware.com>"

# See logs faster; don't write pyc or pyo files
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Yarn breaks their deployment once a year.  We don't use yarn.  Just remove it.
RUN rm /etc/apt/sources.list.d/yarn.list

RUN apt-get update && \
    apt-get install -y \
    # Install libfuse.  This allows better access to files on S3 \
    fuse \
    # Install tini for quicker shutdown \
    tini \
    && \
    rm -rf /var/lib/apt/lists/*

# add a directory for girder mount
RUN mkdir -p /fuse --mode=a+rwx

RUN mkdir -p nci_seer

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

ENTRYPOINT ["/usr/bin/tini", "--"]

CMD python /conf/provision.py && (girder mount /fuse || true) && girder serve
