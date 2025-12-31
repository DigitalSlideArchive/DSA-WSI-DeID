FROM ubuntu:24.04
LABEL maintainer="Kitware, Inc. <kitware@kitware.com>"

# See logs faster; don't write pyc or pyo files
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=en_US.UTF-8 \
    PYENV_ROOT="/.pyenv" \
    PATH="/.pyenv/bin:/.pyenv/shims:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHON_VERSIONS="3.11 3.8"

RUN apt-get update && \
    # DEBIAN_FRONTEND=noninteractive apt-get install -qy tzdata && \
    DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends --yes \
    software-properties-common \
    # gpg-agent \
    ca-certificates \
    curl \
    fonts-dejavu \
    fuse \
    git \
    less \
    libtiff5-dev \
    libmagic-dev \
    vim \
    # needed for easyocr \
    libgl1-mesa-dev \
    libsm6 \
    libxext6 \
    libxrender-dev \
    # for pyenv \
    build-essential \
    libbz2-dev \
    libffi-dev \
    liblzma-dev \
    libncursesw5-dev \
    libreadline-dev \
    libsqlite3-dev \
    libssl-dev \
    libxml2-dev \
    libxmlsec1-dev \
    locales \
    make \
    tk-dev \
    wget \
    xz-utils \
    zlib1g-dev \
    # shrink docker image \
    rdfind \
    # for isyntax libraries \
    gdebi \
    libegl1-mesa-dev \
    libgles2-mesa-dev \
    libjpeg-dev \
    liblcms2-dev \
    libtinyxml-dev \
    # for ldap if we optionally install it \
    libldap2-dev \
    libsasl2-dev \
    && \
    localedef -i en_US -c -f UTF-8 -A /usr/share/locale/locale.alias en_US.UTF-8 && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN curl -LJ https://github.com/krallin/tini/releases/download/v0.19.0/tini -o /usr/bin/tini && \
    chmod +x /usr/bin/tini

RUN curl -L https://github.com/pyenv/pyenv-installer/raw/master/bin/pyenv-installer | bash && \
    find / -xdev -name __pycache__ -type d -exec rm -r {} \+ && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* /var/cache/*

RUN pyenv update && \
    pyenv install --list && \
    echo $PYTHON_VERSIONS | xargs -P `nproc` -n 1 pyenv install && \
    echo $PYTHON_VERSIONS | xargs -n 1 bash -c 'pyenv global "${0}" && pip install -U setuptools pip' && \
    pyenv global $(pyenv versions --bare) && \
    find $PYENV_ROOT/versions -type d '(' -name '__pycache__' -o -name 'test' -o -name 'tests' ')' -exec rm -rfv '{}' + >/dev/null && \
    find $PYENV_ROOT/versions -type f '(' -name '*.py[co]' -o -name '*.exe' ')' -exec rm -fv '{}' + >/dev/null && \
    echo $PYTHON_VERSIONS | tr " " "\n" > $PYENV_ROOT/version && \
    rm -r /root/.cache/pip && \
    find / -xdev -name __pycache__ -type d -exec rm -r {} \+ && \
    rm -rf /tmp/* /var/tmp/* && \
    # This makes duplicate python library files hardlinks of each other \
    find /.pyenv -name 'libpython*.a' -delete && \
    rdfind -minsize 1048576 -makehardlinks true -makeresultsfile false /.pyenv

RUN pip install --no-cache-dir virtualenv && \
    virtualenv /venv && \
    rm -rf /root/.cache/pip/*

ENV PATH="/venv/bin:$PATH"

# Use nvm to install node
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash

# Default node version
RUN . ~/.bashrc && \
    nvm install 14 && \
    nvm alias default 14 && \
    nvm use default && \
    cd /root/.nvm/versions/node/v14.21.3/lib && \
    npm install 'form-data@^2.5.5' && \
    cd /root/.nvm/versions/node/v14.21.3/lib/node_modules/npm && \
    npm install 'cross-spawn@^6.0.6' && \
    npm install 'form-data@^2.5.5' && \
    npm install 'http-cache-semantics@^4.1.1' && \
    npm install 'qs@^6.14.1' && \
    npm install 'semver@^5.7.2' && \
    cd /root/.nvm/versions/node/v14.21.3/lib/node_modules/npm && \
    # ip package has an unaddressed HIGH CVE, ip-address is a direct sustitute \
    npm install --no-save ip-address && \
    rm -rf node_modules/ip && \
    mv node_modules/ip-address node_modules/ip && \
    find / -xdev -name ip -exec grep '"version"' {}/package.json \; && \
    cd /root/.nvm/versions/node/v14.21.3/lib/node_modules/npm/node_modules/term-size && \
    npm install 'cross-spawn@^6.0.6' && \
    cd /root/.nvm/versions/node/v14.21.3/lib/node_modules/npm/node_modules/execa && \
    npm install 'cross-spawn@^6.0.6' && \
    cd /root/.nvm/versions/node/v14.21.3/lib/node_modules/npm/node_modules/request && \
    npm install 'form-data@^2.5.5' && \
    npm install 'qs@^6.14.1' && \
    cd /root/.nvm/versions/node/v14.21.3/lib/node_modules/npm/node_modules/string-width && \
    npm install 'ansi-regex@^3.0.1' && \
    cd /root/.nvm/versions/node/v14.21.3/lib/node_modules/npm/node_modules/yargs && \
    npm install 'ansi-regex@^4.1.1' && \
    cd /root/.nvm/versions/node/v14.21.3/lib/node_modules/npm/node_modules/make-fetch-happen && \
    npm install 'http-cache-semantics@^4.1.1' && \
    find / -xdev -name ip -exec grep '"version"' {}/package.json \; && \
    rm -rf /root/.nvm/.cache && \
    ln -s $(dirname `which npm`) /usr/local/node

ENV PATH="/usr/local/node:$PATH"

RUN mkdir -p /fuse --mode=a+rwx

RUN mkdir -p /wsi_deid && \
    mkdir -p /conf

WORKDIR /wsi_deid

COPY . .

# By using --no-cache-dir the Docker image is smaller
RUN python -m pip install --no-cache-dir \
    git+https://github.com/DigitalSlideArchive/import-tracker.git \
    # git+https://github.com/DigitalSlideArchive/DSA-WSI-DeID.git \
    . \
    # girder[mount] adds dependencies to show tiles from S3 assets \
    girder[mount] \
    # Add additional girder plugins here \
    # girder-homepage \
    # Use prebuilt wheels whenever possible \
    --find-links https://girder.github.io/large_image_wheels && \
    rm -r /root/.cache/pip && \
    find / -xdev -name __pycache__ -type d -exec rm -r {} \+ && \
    find /venv/lib -name '*.so' -o -name '*.so.*' -exec strip {} --strip-unneeded \; && \
    rm -rf /tmp/* /var/tmp/* && \
    rdfind -minsize 32768 -makehardlinks true -makeresultsfile false /pyenv && \
    rdfind -minsize 32768 -makehardlinks true -makeresultsfile false /usr/local/bin

# Download ocr model
RUN python -c 'import easyocr,PIL.Image,numpy;OCRReader = easyocr.Reader(["en"], verbose=False, quantize=False);print(OCRReader.readtext(numpy.asarray(PIL.Image.open("tests/data/sample_label.jpg")),contrast_ths=0.75,adjust_contrast=1.0))' && \
    find / -xdev -name __pycache__ -type d -exec rm -r {} \+ && \
    rm -rf /tmp/* /var/tmp/*

# Build the girder web client
RUN NPM_CONFIG_FUND=false NPM_CONFIG_AUDIT=false NPM_CONFIG_AUDIT_LEVEL=high NPM_CONFIG_LOGLEVEL=warn NPM_CONFIG_PROGRESS=false NPM_CONFIG_PREFER_OFFLINE=true \
    girder build && \
    # Get rid of unnecessary files to keep the docker image smaller \
    find /venv -name node_modules -exec rm -rf {} \+ && \
    find /venv -name package-lock.json -exec rm -f {} \+ && \
    find /usr/lib -name package-lock.json -exec rm -f {} \+ && \
    npm cache clear --force && \
    rm -rf /tmp/npm*

RUN virtualenv /venv3.8 --python 3.8 && \
    /venv3.8/bin/python -m pip install git+https://github.com/DigitalSlideArchive/large_image_source_isyntax.git rpyc && \
    /venv/bin/python -m pip install git+https://github.com/DigitalSlideArchive/large_image_source_isyntax.git rpyc

COPY ./devops/wsi_deid/girder.local.conf ./devops/wsi_deid/provision.py ./devops/wsi_deid/homepage.md /conf/

ENTRYPOINT ["/usr/bin/tini", "--"]

CMD python /conf/provision.py && (girder mount /fuse 2>/dev/null || true) && girder serve
