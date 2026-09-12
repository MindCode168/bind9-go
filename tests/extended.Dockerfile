FROM bind9-go-upstream-test:9.20.27
RUN apt-get update && apt-get install -y --no-install-recommends \
    softhsm2 opensc libengine-pkcs11-openssl gnutls-bin \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m pip install --no-cache-dir sslyze
RUN mkdir -p /src/tokens && \
    printf 'directories.tokendir = /src/tokens\nobjectstore.backend = file\nlog.level = ERROR\n' > /src/softhsm2.conf && \
    chown -R tester:tester /src/tokens /src/softhsm2.conf
COPY openssl-engine.cnf /src/openssl-engine.cnf
ENV SOFTHSM2_CONF=/src/softhsm2.conf
ENV OPENSSL_CONF=/etc/ssl/openssl.cnf
ENV CI_ENABLE_LONG_TESTS=1
