#!/usr/bin/with-contenv bashio

echo "--- STARTING DIAGNOSTIC SCRIPT ---"
env

if [ -f /data/options.json ]; then
    cat /data/options.json
else
    echo "ERROR: /data/options.json not found."
fi

ls -la /data
echo "--- DIAGNOSTIC COMPLETE, IDLING ---"
sleep 300
