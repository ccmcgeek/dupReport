#!/bin/sh
set -e

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

# Actual entry
exec "$@"
