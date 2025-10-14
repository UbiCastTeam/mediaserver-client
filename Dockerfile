FROM debian:bookworm

RUN apt update
RUN apt install -y python3-venv make

RUN python3 -m venv /opt/venv --system-site-packages
ENV VIRTUAL_ENV="/opt/venv"
ENV PATH="/opt/venv/bin:/usr/sbin:/usr/bin:/sbin:/bin"
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

WORKDIR /opt/src

COPY pyproject.toml pyproject.toml
COPY ms_client ms_client
RUN pip install --no-cache-dir --editable '.[dev]'
