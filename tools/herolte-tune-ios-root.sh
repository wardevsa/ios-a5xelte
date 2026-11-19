#!/bin/bash
# HEROLTE: adjust a staged iOS 16 root (tools/a5xelte-stage-ios-root.sh) for a
# phone without modem, GPU or SEP, following the SWEET donor's image v12/v13
# (NOTES.md). Run as root on macOS with the HFSX root mounted read-write.
#   - com.apple.migration.plist LastSystemVersion = this build: backboardd
#     holds SpringBoard's system-shell check-in until DataMigration finishes,
#     and the migration plugin wrapper aborts on every boot.
#   - CommCenter jobs removed from launchd.plist (no modem: crash loop); on
#     iOS 18 also herolte-disabled.list and the jobs heronoexec refuses.
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
/usr/bin/env python3 - "$launchd" "$build" "$(dirname "$0")/herolte-disabled.list" <<'EOF'
import os, plistlib, sys
path, build, listed = sys.argv[1], sys.argv[2], sys.argv[3]
with open(path, 'rb') as f:
    data = plistlib.load(f)
fmt = plistlib.FMT_BINARY
# iOS 18 (builds 22*) has no hero-run to put tools/herolte-disabled.list into launchd's disabled jobs, and launchd
# relaunched every job the kernel's heronoexec refuses every 10 s for ever: in boot-18k15, 40 tries each of
# analyticsd, homed, cloudd, ReportCrash, searchd in 7 minutes (950 xpcproxy exits), with spaceattributiond, wifip2pd
# and fairplayd exiting as often. Those jobs leave launchd.plist here: the phone ran hot to the touch.
off_labels, off_programs = set(), set()
if build[:2].isdigit() and int(build[:2]) >= 22:
    off_labels = {l.strip() for l in open(listed) if l.strip() and not l.startswith('#')}
    off_labels |= {'com.apple.spaceattributiond', 'com.apple.wifip2pd'}
    # boot-18k18g: cryptexd died 14 times in libimage4 (it needs the SEP; KeepAlive until its init file exists, which never
    # comes), passd 7 times in FinanceKit (Wallet), and findmylocated (~100 %) and nehelper (~100 %) spun the whole session.
    off_labels |= {'com.apple.security.cryptexd', 'com.apple.passd', 'com.apple.findmy.findmylocated', 'com.apple.nehelper'}
    # boot-18k20 (system UI on the Mali): searchpartyd (Find My network) ~70 %, mobileassetd ~33 %, osanalyticshelper ~19 %
    # (writing crash reports) and PerfPowerServices ~16 % on average, nothing of it of use here.
    off_labels |= {'com.apple.icloud.searchpartyd', 'com.apple.osanalytics.osanalyticshelper',
                   'com.apple.PerfPowerServices', 'com.apple.PerfPowerServicesExtended'}
    # mobileassetd stays (boot-18k21 on, without it, the wallpaper gallery came up white; its thumbnails had been there).
    # parsecd (Spotlight's suggestions) ~15 % in boot-18k24, of no use here.
    off_labels |= {'com.apple.parsecd'}
    # boot-18k34: networkserviceproxy (iCloud Private Relay) ~180 % the whole session (~73 % in 18k32), and the software
    # update daemons kept mobileassetd at ~190 % (softwareupdateservicesd, KeepAlive; no OTA can apply here anyway);
    # sirittsd asked for voices whose audio units are gone (below).
    off_labels |= {'com.apple.networkserviceproxy', 'com.apple.softwareupdateservicesd', 'com.apple.mobile.softwareupdated',
                   'com.apple.OTATaskingAgent', 'com.apple.subridged', 'com.apple.sirittsd'}
    # the boot-arg heronoexec list of xnu/patches 0253 (docs/herolte-howto.md), by program name
    off_programs = {'vmd', 'searchd', 'ReportCrash', 'aggregated', 'analyticsd', 'cloudd', 'homed', 'driverkitd'}
removed = []
for section in ('LaunchDaemons', 'Agents', 'LaunchAgents'):
    jobs = data.get(section, {})
    for key in list(jobs):
        job = jobs[key] if isinstance(jobs[key], dict) else {}
        label = job.get('Label', '')
        prog = job.get('Program') or (job.get('ProgramArguments') or [''])[0]
        if 'CommCenter' in key or 'CommCenter' in label or label in off_labels \
                or os.path.basename(prog) in off_programs:
            removed.append(label or key)
            del jobs[key]
if not any('CommCenter' in r for r in removed):
    sys.exit('no CommCenter job found in launchd.plist')
if off_labels:
    print(f'launchd.plist: {len(removed)} jobs out (iOS 18), not found:',
          ', '.join(sorted(off_labels - set(removed))) or 'none')
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

# iOS 18: extensions that only crash here, relaunched again and again (boot-18k29/18k30): the Watch face poster
# Kaleidoscope (SIGSEGV x12, PosterBoard relaunches it; iOS's own wallpapers are CollectionsPoster's) and the speech
# synthesis audio units (SiriAUSP/MauiAUSP abort x23 in audiomxd, MacinTalkAUSP fails to spawn).
if [[ ${build:0:2} =~ ^[0-9]+$ ]] && (( ${build:0:2} >= 22 )); then
    for appex in System/Library/PrivateFrameworks/WatchFacesWallpaperSupport.framework/PlugIns/KaleidoscopePoster.appex \
                 System/Library/PrivateFrameworks/TextToSpeech.framework/PlugIns/SiriAUSP.appex \
                 System/Library/PrivateFrameworks/TextToSpeechMauiSupport.framework/PlugIns/MauiAUSP.appex \
                 System/Library/PrivateFrameworks/MacinTalk.framework/PlugIns/MacinTalkAUSP.appex; do
        if [[ -d "$root/$appex" ]]; then
            rm -rf "${root:?}/$appex"
            echo "removed /$appex"
        fi
    done
    # iOS's own wallpapers are HEIC, and there is no HEVC decoder for iOS here: black (tools/ios18/heic2png.py)
    heicpy=${HEIC_PYTHON:-python3}
    [[ -x /root/venv/bin/python ]] && heicpy=${HEIC_PYTHON:-/root/venv/bin/python}
    "$heicpy" -I "$(dirname "$0")/ios18/heic2png.py" "$root"
fi

containers="$root/private/var/containers"
install -d -o 0 -g 0 -m 0755 "$containers" "$containers/Bundle" "$containers/Data" \
    "$containers/Data/System" "$containers/Shared" "$containers/Shared/SystemGroup" \
    "$containers/Temp"

sync -f "$root" 2>/dev/null || sync     # only this filesystem (a global sync can hang on WSL2, see mkroot-s7.py)
echo "HEROLTE root tuning complete for build $build"
