ARG BASE_IMAGE=ubuntu:24.04
FROM ${BASE_IMAGE}
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential pkg-config perl python3 python3-venv ca-certificates \
    libssl-dev libuv1-dev liburcu-dev libnghttp2-dev libcap-dev \
    libcmocka-dev libxml2-dev libjson-c-dev liblmdb-dev libidn2-dev \
    libmaxminddb-dev libkrb5-dev libfstrm-dev libprotobuf-c-dev \
    protobuf-c-compiler libjemalloc-dev libreadline-dev zlib1g-dev \
    libnet-dns-perl iproute2 net-tools curl openssl gosu \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY . /src
RUN python3 -m venv /opt/testenv && \
    /opt/testenv/bin/pip install --no-cache-dir -r bin/tests/system/requirements.txt
ENV PATH="/opt/testenv/bin:${PATH}"
RUN ./configure --disable-maintainer-mode --with-cmocka=yes \
    --enable-dnstap --enable-fixed-rrset --with-libidn2=yes \
    --with-json-c=yes --with-libxml2=yes --with-libnghttp2=yes \
    && make -j4
RUN useradd --create-home tester && chown -R tester:tester /src
CMD ["/bin/bash"]
