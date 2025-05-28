# build via
#  docker build --force-rm -t kitware/bioometiff -f bioformatsToOmeTIFF.Dockerfile .
# run something like
#  docker run --rm -it -v /mnt/data2:/data kitware/bioometiff /data/NCISEER/Mouse/SEER_Mouse_1_17158538.svs --rgb --compression=JPEG --quality=70 /data/SEER_Mouse_1_17158538.ome.tiff
# Make sure the output file does not exist; otherwise, it will get appended to
# rather than replaced.
# Contrary to the --help statement, compression options are
#  NONE, LZW, JPEG, JPEG-2000, 'JPEG-2000 Lossy'
# For JPEG-2000 Lossy, quality is a floating point number of bits per sample in
# the compressed data stream (e.g., from 0 to the bits per sample of the
# image).
# JPEG compression duplicates the jpeg headers, greatly increasing the output
# file size over what is expected.
# A JPEG-2000 compression that seems reasonable is
#  docker run --rm -it -v /mnt/data2:/data kitware/bioometiff /data/NCISEER/Mouse/SEER_Mouse_1_17158538.svs --rgb --quality=0.95 --compression='JPEG-2000 Lossy' /data/SEER_Mouse_1_17158538.ome.tiff --max_workers=`nproc`

FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y \
    curl \
    less \
    libblosc1 \
    unzip \
    vim \
    && true

RUN pip install large-image-source-bioformats --find-links https://girder.github.io/large_image_wheels

RUN mkdir /project && \
    cd /project && \
    curl -L https://github.com/glencoesoftware/bioformats2raw/releases/download/v0.9.4/bioformats2raw-0.9.4.zip -o bioformats2raw.zip && \
    unzip bioformats2raw.zip && \
    mv bioformats2raw-0.9.4 bioformats2raw && \
    curl -L https://github.com/glencoesoftware/raw2ometiff/releases/download/v0.7.1/raw2ometiff-0.7.1.zip -o raw2ometiff.zip && \
    unzip raw2ometiff.zip && \
    mv raw2ometiff-0.7.1 raw2ometiff && \
    true

WORKDIR /project

RUN echo 'bioformats2raw/bin/bioformats2raw --max-workers=`nproc` --target-min-size=1024 --progress "$1" /tmp/output' > /project/run.sh && \
    echo 'raw2ometiff/bin/raw2ometiff --progress /tmp/output "${@:2}"' >> /project/run.sh

ENTRYPOINT ["bash", "/project/run.sh"]
