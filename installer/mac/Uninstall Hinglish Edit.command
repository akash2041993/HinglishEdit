#!/bin/bash
# Double-click to remove Hinglish Edit (helper app and Premiere panel). Your settings and outputs are kept in
# ~/Library/Application Support/HinglishEdit (delete that folder yourself if you want).
UPIA="/Library/Application Support/Adobe/Adobe Desktop Common/RemoteComponents/UPI/UnifiedPluginInstallerAgent/UnifiedPluginInstallerAgent.app/Contents/MacOS/UnifiedPluginInstallerAgent"
pkill -f HinglishEditHelper/HinglishEditHelper 2>/dev/null
[ -x "$UPIA" ] && "$UPIA" --remove "Hinglish Edit"
echo "Removing /Applications/HinglishEdit (your Mac password may be asked)…"
sudo rm -rf /Applications/HinglishEdit && sudo pkgutil --forget com.azone.hinglishedit >/dev/null 2>&1
echo "Done."
read -n 1 -s -r -p "Press any key to close."
