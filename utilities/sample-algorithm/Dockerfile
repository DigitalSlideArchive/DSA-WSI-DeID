# build via docker build --force-rm -t dsarchive/example_ssa .

FROM python:3.13-slim

LABEL maintainer="Kitware, Inc. <kitware@kitware.com>"

RUN pip install girder-client girder-slicer-cli-web 'setuptools<80'

COPY . /opt/main
WORKDIR /opt/main

ENTRYPOINT ["/bin/bash", "entrypoint.sh"]
