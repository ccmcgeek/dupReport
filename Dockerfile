FROM alpine:3.7

# Install python3
RUN apk add --no-cache \
        dcron \
        python3 \
        tzdata \
    && \
# Prepare cron
    mkdir -m 0644 -p /var/spool/cron/crontabs && \
# Create workdir
    mkdir -p /python/dupreport && \
# Create config location
    mkdir -p /config 

COPY . /python/dupreport/
COPY docker-entrypoint.sh /usr/local/bin/

WORKDIR /python/dupreport

# Create initial RC file
RUN mkdir /python/dupreport/default_config && \
    python3 -B /python/dupreport/dupReport.py -r /python/dupreport/default_config -d /python/dupreport/default_config -l /python/dupreport/default_config

# Declare the /config mount
VOLUME /config

# Entrypoint
ENTRYPOINT ["docker-entrypoint.sh"]
