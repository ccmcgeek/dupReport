FROM alpine:3.7

# Install python3
RUN apk add --no-cache python3 && \
# Create workdir
    mkdir -p /python/dupreport && \
# Create unprivileged user
    addgroup -g 1000 dupreport && \
    adduser -D -u 1000 -G dupreport -h /python/dupreport dupreport && \
    chown -Rh dupreport:dupreport /python/dupreport && \
# Create config location
    mkdir -p /config && \
    chown -Rh dupreport:dupreport /config

COPY . /python/dupreport/
COPY docker-entrypoint.sh /usr/local/bin/

WORKDIR /python/dupreport
USER dupreport

# Create initial RC file
RUN mkdir /python/dupreport/default_config && \
    python3 -B /python/dupreport/dupReport.py -r /python/dupreport/default_config -d /python/dupreport/default_config -l /python/dupreport/default_config

# Declare the /config mount
VOLUME /config

# Entrypoint
ENTRYPOINT ["docker-entrypoint.sh"]
CMD python3 /python/dupreport/dupReport.py -r /config -d /config -l /config
