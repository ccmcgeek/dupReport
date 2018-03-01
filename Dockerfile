FROM alpine:3.7

ENV DUPREPORT_CONFIG_DIR=/config

# Install python3
RUN apk add --no-cache python3 && \
# Create user
    mkdir -p /usr/src/dupreport && \
    addgroup -g 1000 dupreport && \
    adduser -D -u 1000 -G dupreport -h /usr/src/dupreport dupreport && \
    chown -Rh dupreport:dupreport /usr/src/dupreport && \
# Create config location
    mkdir -p $DUPREPORT_CONFIG_DIR

COPY . /usr/src/dupreport/

WORKDIR /usr/src/dupreport

VOLUME /config

# Entrypoint
CMD ["python3", "-B", "/usr/src/dupreport/dupReport.py", "-r", "/config", "-d", "/config", "-l", "/config"]
