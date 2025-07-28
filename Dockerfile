FROM debian:bookworm

RUN apt update
RUN apt install -y python3-venv make

RUN python3 -m venv /opt/venv --system-site-packages
ENV VIRTUAL_ENV="/opt/venv"
ENV PATH="/opt/venv/bin:/usr/sbin:/usr/bin:/sbin:/bin"

WORKDIR /opt/src

COPY setup.cfg setup.cfg
COPY setup.py setup.py
COPY ms_client ms_client
RUN pip install -e '.[dev]'
RUN python3 setup.py install
