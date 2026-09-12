FROM bind9-go-upstream-test:9.20.27
RUN apt-get update && apt-get install -y --no-install-recommends dnsperf \
    && rm -rf /var/lib/apt/lists/*
