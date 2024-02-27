#!/bin/bash
set -e
# Try to install the iSyntax library.  If we fail, start any way
(
  export TERM="${TERM:=xterm}"
  # the installer needs Python 3.8 to be the first python it finds
  export PATH="/venv3.8/bin:$PATH"
  echo 'Listing isyntax directory'
  ls -l /isyntax
  echo 'Switch to isyntax directory'
  cd /isyntax
  echo 'Run Philips installer script'
  # This installs in dist-packages instead of in our virtualenv because that is
  # the Ubuntu deb way.
  echo y | source ./InstallPathologySDK.sh
  # Copy the so files to our virtualenv
  echo 'Copy files to our internal python 3.8 environment'
  cp /usr/lib/python3/dist-packages/*cpython-38-x86_64-linux-gnu* /venv3.8/lib/python3.8/site-packages/.
  # Start the client to allow access to the 3.8 library files
  echo 'Start rpyc protocol'
  /venv3.8/bin/rpyc_classic &
) || true
# This is our original start method
python /conf/provision.py
girder mount /fuse || true
girder serve
