#!/bin/bash
# Double-click to start the Hinglish Edit helper. Keep this Terminal window open while you edit in Premiere.
cd "$(dirname "$0")/HinglishEditHelper" || exit 1
if curl -s --max-time 2 http://127.0.0.1:47800/health >/dev/null 2>&1; then
  echo "The Hinglish Edit helper is already running. You can close this window."
  sleep 4; exit 0
fi
clear
./HinglishEditHelper
echo
read -n 1 -s -r -p "Helper stopped. Press any key to close."
