#!/bin/bash
# HEROLTE: adjust a staged iOS 16 root (tools/a5xelte-stage-ios-root.sh) for a
# phone without modem, GPU or SEP, following the SWEET donor's image v12/v13
# (NOTES.md). Run as root on macOS with the HFSX root mounted read-write.
#   - com.apple.migration.plist LastSystemVersion = this build: backboardd
#     holds SpringBoard's system-shell check-in until DataMigration finishes,
#     and the migration plugin wrapper aborts on every boot.
#   - CommCenter jobs removed from launchd.plist (no modem: crash loop).
#   - com.herolte.autorun added: runs /private/var/herolte/autorun at boot
#     (test programs from the kernel's USERDATA drop zone).
#   - SpringBoard watchdogs off; Setup (purplebuddy) exempt from the scene
#     watchdog (it blocks in CoreTelephony without CommCenter).
#   - Setup marked complete (donor image v14), no cloud configuration UI.
#   - /private/var/containers skeleton (on iOS it lives on the data volume).
set -euo pipefail

if [[ $# != 2 || ${EUID} != 0 ]]; then
    echo "usage (as root): $0 HFSX_MOUNT BUILD" >&2
    exit 2
fi
root=$1 build=$2
[[ -f "$root/sbin/launchd" ]] || { echo "not a staged root: $root" >&2; exit 1; }

prefs="$root/private/var/mobile/Library/Preferences"
install -d -o 501 -g 501 -m 0755 "$root/private/var/mobile" \
    "$root/private/var/mobile/Library" "$prefs"

plutil_py() {  # plutil_py XML(0|1) FILE KEY TYPE VALUE ...: plutil -replace for Linux (Renegade's Linux backend)
    /usr/bin/env python3 - "$@" <<'EOF'
import json, os, plistlib, sys
xml, path, args = sys.argv[1] == '1', sys.argv[2], sys.argv[3:]
data, fmt = {}, plistlib.FMT_XML
if os.path.exists(path) and os.path.getsize(path):
    raw = open(path, 'rb').read()
    fmt = plistlib.FMT_BINARY if raw.startswith(b'bplist') else plistlib.FMT_XML
    data = plistlib.loads(raw)
conv = {'string': str, 'integer': int, 'json': json.loads,
        'bool': lambda v: v.strip().upper() in ('YES', 'TRUE', '1')}
for i in range(0, len(args), 3):
    key, typ, val = args[i:i + 3]
    data[key] = conv[typ](val)
with open(path, 'wb') as f:
    plistlib.dump(data, f, fmt=plistlib.FMT_XML if xml else fmt)
EOF
}

plist() {  # plist FILE KEY TYPE VALUE ...  (creates or updates entries, XML)
    local file=$1; shift
    if [[ -x /usr/bin/plutil ]]; then
        [[ -f $file ]] || /usr/bin/plutil -create xml1 "$file"
        while (($#)); do
            /usr/bin/plutil -replace "$1" "-$2" "$3" "$file"
            shift 3
        done
        /usr/bin/plutil -convert xml1 "$file"
    else
        plutil_py 1 "$file" "$@"
    fi
    chown 501:501 "$file"
    chmod 0600 "$file"
}

# WallpaperKit offers only the wallpapers that name this screen's class
# (1440x2560 at @3x); the IPSW has none. The 375w-812h ones are given it.
find "$root/Library/Wallpaper/Collections" -path '*375w-812h*' -name Wallpaper.plist -print0 |
while IFS= read -r -d '' wallpaper; do
    if [[ -x /usr/bin/plutil ]]; then
        /usr/bin/plutil -replace logicalScreenClass -string '480w-853h@3x~iphone' "$wallpaper"
    else
        plutil_py 0 "$wallpaper" logicalScreenClass string '480w-853h@3x~iphone'
    fi
done

plist "$prefs/com.apple.migration.plist" LastSystemVersion string "$build"
plist "$prefs/com.apple.springboard.plist" \
    BKNoWatchdogs bool YES \
    FBLaunchWatchdogExceptions json '{"com.apple.purplebuddy":100}' \
    MCForceShowCloudConfigurationUI bool NO
# Setup (purplebuddy) recognises the swipe but never finishes: it waits on
# CoreTelephony and activation (donor image v14). Mark it complete;
# activation itself comes from the ADT /chosen production-status 0 and
# security-mode 1 properties (mobileactivationd's native branch).
plist "$prefs/com.apple.purplebuddy.plist" \
    SetupDone bool YES \
    SetupFinishedAllSteps bool YES \
    SetupVersion integer 11 \
    daemonizeNeedsToRun bool NO
plist "$prefs/com.apple.managedconfiguration.notbackedup.plist" \
    LockdownActivationIndicatesCloudConfigurationAvailable bool NO

launchd="$root/System/Library/xpc/launchd.plist"
/usr/bin/env python3 - "$launchd" <<'EOF'
import plistlib, sys
path = sys.argv[1]
with open(path, 'rb') as f:
    data = plistlib.load(f)
fmt = plistlib.FMT_BINARY
removed = []
for section in ('LaunchDaemons', 'Agents', 'LaunchAgents'):
    jobs = data.get(section, {})
    for key in list(jobs):
        label = jobs[key].get('Label', '') if isinstance(jobs[key], dict) else ''
        if 'CommCenter' in key or 'CommCenter' in label:
            removed.append(label or key)
            del jobs[key]
if not removed:
    sys.exit('no CommCenter job found in launchd.plist')
# Developer hook: /private/var/herolte/autorun once per boot, as root, if the
# kernel's USERDATA drop zone put it there (bsd/dev/herolte_drop.c,
# tools/herolte-drop.py). Without the file launchd just logs an error.
data['LaunchDaemons']['/System/Library/LaunchDaemons/com.herolte.autorun.plist'] = {
    'Label': 'com.herolte.autorun',
    'ProgramArguments': ['/private/var/herolte/autorun'],
    'RunAtLoad': True,
    'UserName': 'root',
    'POSIXSpawnType': 'Interactive',
    'StandardOutPath': '/private/var/herolte/autorun.out',
    'StandardErrorPath': '/private/var/herolte/autorun.out',
}
with open(path, 'wb') as f:
    plistlib.dump(data, f, fmt=fmt)
print('launchd.plist: removed', ', '.join(removed), '; added com.herolte.autorun')
EOF

containers="$root/private/var/containers"
install -d -o 0 -g 0 -m 0755 "$containers" "$containers/Bundle" "$containers/Data" \
    "$containers/Data/System" "$containers/Shared" "$containers/Shared/SystemGroup" \
    "$containers/Temp"

sync
echo "HEROLTE root tuning complete for build $build"
