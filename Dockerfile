FROM nikolaik/python-nodejs:python3.7-nodejs12
LABEL maintainer="Kitware, Inc. <kitware@kitware.com>"

# This prevents gdal from complaining that it can't write aux.xml files.
ENV GDAL_PAM_PROXY_DIR=/tmp/gdal

# See logs faster; don't write pyc or pyo files
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

# Yarn breaks their deployment once a year.  We don't use yarn.  Just remove it.
RUN rm /etc/apt/sources.list.d/yarn.list

# Install libfuse.  This allows better access to files on S3
RUN apt-get update && \
    apt-get install -y fuse && \
    rm -rf /var/lib/apt/lists/*

# add a directory for girder mount
RUN mkdir -p /fuse --mode=a+rwx

RUN mkdir -p nci_seer

WORKDIR nci_seer

COPY . .

# By using --no-cache-dir the Docker image is smaller
RUN pip install --pre --no-cache-dir \
    # git+https://github.com/DigitalSlideArchive/NCI-SEER-Pediatric-WSI-Pilot.git \
    -e . \
    # girder[mount] adds dependencies to show tiles from S3 assets \
    girder[mount] \
    # You could add additional girder plugins here (e.g., \
    # girder-virtual-folders or girder-dicom-viewer) \
    girder-homepage \
    # Use prebuilt wheels whenever possible \
    --find-links https://girder.github.io/large_image_wheels

# Build the girder web client
RUN girder build && \
    # Git rid of unnecessary files to keep the docker image smaller \
    find /usr/local/lib/python3.7 -name node_modules -exec rm -rf {} \+ && \
    rm -rf /tmp/npm*

CMD python /conf/provision.py && (girder mount /fuse || true) && girder serve
