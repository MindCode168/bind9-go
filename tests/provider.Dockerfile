FROM bind9-go-upstream-extended:9.20.27
ENV OPENSSL_CONF=/etc/ssl/openssl.cnf
RUN python3 -m pip install --no-cache-dir meson ninja
ARG PROVIDER_VERSION=1.2.0
RUN curl --fail --location --max-time 120 \
    https://codeload.github.com/openssl-projects/pkcs11-provider/tar.gz/refs/tags/v${PROVIDER_VERSION} \
    -o /tmp/pkcs11-provider.tar.gz && \
    sha256sum /tmp/pkcs11-provider.tar.gz > /src/pkcs11-provider.sha256 && \
    tar -xzf /tmp/pkcs11-provider.tar.gz -C /opt && \
    meson setup /opt/pkcs11-build /opt/pkcs11-provider-${PROVIDER_VERSION} && \
    meson compile -C /opt/pkcs11-build -j4 && \
    meson install -C /opt/pkcs11-build
ARG PROVIDER_CONFIG=openssl-provider.cnf
COPY ${PROVIDER_CONFIG} /src/openssl-provider.cnf
ENV OPENSSL_CONF=/src/openssl-provider.cnf
RUN openssl list -providers && /src/bin/tests/system/feature-test --md5
