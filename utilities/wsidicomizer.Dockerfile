# build via
#  docker build --force-rm -t kitware/wsidicomizer -f wsidicomizer.Dockerfile .
# run something like
#  docker run --rm -it -v /mnt/data2:/data kitware/wsidicomizer -i /data/NCISEER/Mouse/SEER_Mouse_1_17158538.svs -o /data/NCISEER/SEER_Mouse_1_17158538.dicom -t 256 --add-missing-levels -w `nproc`
# Make sure the output folder does not exist

FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y \
    curl \
    less \
    libturbojpeg0-dev \
    vim \
    && true

RUN pip install wsidicomizer[bioformats,openslide] openslide-bin

ENTRYPOINT ["wsidicomizer"]
