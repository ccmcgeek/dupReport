#!/bin/sh
set -e

# Confirm TZ setting from ENV params
if [[ ! -z "$TZ" ]] ; then
    echo Timezone: $TZ
    date
fi

# Update config file from ENV params
if [[ ! -f /config/dupReport.rc ]] ; then
    cp /python/dupreport/default_config/dupReport.rc /config/dupReport.rc
fi

# Function to perform an .RC file config variable substitution
#  updateConfig <var> <value>
updateConfig() {
    if [[ ! -z "$2" ]] ; then
        escapedValue=$(echo $2 | sed 's/[&/\]/\\&/g')
        case "$1" in
            *password*) echo Substituting $1 = \*\*\*\* ;;
            *         ) echo Substituting $1 = $2 ;;
        esac
        sed -i 's/^\('"$1"'\s*=\s*\).*$/\1'"$escapedValue"'/' /config/dupReport.rc
    fi
}

updateConfig 'intransport' "$IN_TRANSPORT"
updateConfig 'inserver' "$IN_SERVER"
updateConfig 'inport' "$IN_PORT"
updateConfig 'inencryption' "$IN_ENCRYPTION"
updateConfig 'inaccount' "$IN_ACCOUNT"
updateConfig 'inpassword' "$IN_PASSWORD"
updateConfig 'infolder' "$IN_FOLDER"
updateConfig 'outserver' "$OUT_SERVER"
updateConfig 'outport' "$OUT_PORT"
updateConfig 'outencryption' "$OUT_ENCRYPTION"
updateConfig 'outaccount' "$OUT_ACCOUNT"
updateConfig 'outpassword' "$OUT_PASSWORD"
updateConfig 'outsender' "$OUT_SENDER"
updateConfig 'outreceiver' "$OUT_RECEIVER"
updateConfig 'style' "$REPORT_STYLE"
updateConfig 'sortby' "$REPORT_SORTBY"
updateConfig 'sizedisplay' "$REPORT_SIZEDISPLAY"

# Launch the script, a cron job for the script, or the provided command
if [[ "$#" -eq 0 ]] ; then

    if [[ ! -z "$REPORT_TIME" ]] ; then

        cat > /config/crontab <<EOCRON
$(expr substr $REPORT_TIME 4 2) $(expr substr $REPORT_TIME 1 2) * * * python3 /python/dupreport/dupReport.py -r /config -d /config -l /config 

EOCRON
        (crontab -l ; cat /config/crontab) | crontab -
# Note: cannot directly exec crond -f here, due to dcron calling setpgid which is disallowed in docker containers for PID 1
        crond -f

    else

        exec python3 /python/dupreport/dupReport.py -r /config -d /config -l /config

    fi

else

    exec "$@"

fi
