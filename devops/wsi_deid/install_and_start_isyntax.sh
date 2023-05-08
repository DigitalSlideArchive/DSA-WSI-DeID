#!/bin/bash
set -e 
# Try to install the iSyntax library.  If we fail, start any way
(
  # the installer needs Python 3.8 to be the first python it finds
  export PATH="/venv3.8/bin:$PATH"
  cd /isyntax 
  # This installs in dist-packages instead of in our virtualenv because that is
  # the Ubuntu deb way.
  echo y | source ./InstallPathologySDK.sh 
  # Copy the so files to our virtualenv
  cp /usr/lib/python3/dist-packages/*cpython-38-x86_64-linux-gnu* /venv3.8/lib/python3.8/site-packages/.
  # Start the client to allow access to the 3.8 library files
  /venv3.8/bin/rpyc_classic &
) || true
# This is our original start method
python /conf/provision.py 
girder serve
