#!/bin/bash
# Test of tools/plutil_lite.py and of tools/herolte-tune-ios-root.sh on a FAKE root, without sudo and without mounting
# anything: the script runs under fakeroot (EUID 0, chown recorded by fakeroot, nothing real is changed).
#   bash tools/test_tune_ios_root.sh        (needs fakeroot and python3; the sandbox in $TMPDIR is left in place)
set -u
HERE=$(cd "$(dirname "$0")" && pwd); PL="$HERE/plutil_lite.py"; TUNE="$HERE/herolte-tune-ios-root.sh"
SB=$(mktemp -d "${TMPDIR:-/tmp}/tune-test.XXXXXX"); PASS=0; FAIL=0
ok(){ if "$@" >/dev/null 2>&1; then PASS=$((PASS+1)); echo "PASS  $NAME"; else FAIL=$((FAIL+1)); echo "FALLA $NAME"; fi; }
t(){ NAME=$1; shift; ok "$@"; }
py(){ python3 -I - "$@"; }

# --- plutil_lite
F=$SB/a.plist
t "create xml1 crea un diccionario vacio" bash -c "python3 '$PL' -create xml1 '$F' && python3 -I -c \"import plistlib,sys;assert plistlib.load(open('$F','rb'))=={}\" && head -c 5 '$F' | grep -q '<?xml'"
t "create no pisa un fichero existente" bash -c "! python3 '$PL' -create xml1 '$F'"
t "replace string/bool/integer/json" bash -c "python3 '$PL' -replace A -string x '$F' && python3 '$PL' -replace B -bool YES '$F' && python3 '$PL' -replace C -bool NO '$F' && python3 '$PL' -replace D -integer 11 '$F' && python3 '$PL' -replace E -json '{\"com.apple.purplebuddy\":100}' '$F' && python3 -I -c \"import plistlib;d=plistlib.load(open('$F','rb'));assert d=={'A':'x','B':True,'C':False,'D':11,'E':{'com.apple.purplebuddy':100}},d\""
t "replace sustituye un valor existente" bash -c "python3 '$PL' -replace A -string y '$F' && python3 -I -c \"import plistlib;assert plistlib.load(open('$F','rb'))['A']=='y'\""
B=$SB/b.plist; python3 -I -c "import plistlib;plistlib.dump({'k':1},open('$B','wb'),fmt=plistlib.FMT_BINARY)"
t "replace conserva el formato binario" bash -c "python3 '$PL' -replace k -integer 2 '$B' && head -c 6 '$B' | grep -q bplist"
t "convert xml1 reescribe en XML" bash -c "python3 '$PL' -convert xml1 '$B' && head -c 5 '$B' | grep -q '<?xml' && python3 -I -c \"import plistlib;assert plistlib.load(open('$B','rb'))=={'k':2}\""
t "convert binary1 no esta soportado (el script no lo usa)" bash -c "! python3 '$PL' -convert binary1 '$B'"
t "float no esta soportado (el script no lo usa)" bash -c "! python3 '$PL' -replace k -float 1.5 '$B'"
t "unittest de tipos y estructuras (test_plutil_lite.py)" python3 -I "$HERE/test_plutil_lite.py"
t "tipo no soportado falla" bash -c "! python3 '$PL' -replace k -data abc '$B'"
t "bool invalido falla" bash -c "! python3 '$PL' -replace k -bool maybe '$B'"
t "integer invalido falla" bash -c "! python3 '$PL' -replace k -integer 1x '$B'"
t "key path (con punto) se rechaza" bash -c "! python3 '$PL' -replace a.b -string x '$B'"
t "fichero que no existe: falla" bash -c "! python3 '$PL' -replace k -string x '$SB/no-existe.plist'"
t "un fallo no deja ficheros temporales" bash -c "! ls -A '$SB' | grep -q '^\.plutil_lite\.'"

# --- tune sobre un root falso, bajo fakeroot
R=$SB/root; mkdir -p "$R/sbin" "$R/System/Library/xpc" "$R/Library/Wallpaper/Collections/x-375w-812h-y" "$R/Library/Wallpaper/Collections/z-414w-896h"
: > "$R/sbin/launchd"
python3 -I - "$R" <<'EOF'
import plistlib, sys
r = sys.argv[1]
plistlib.dump({'LaunchDaemons': {'/a/com.apple.CommCenter.plist': {'Label': 'com.apple.CommCenter'},
                                 '/a/com.apple.other.plist': {'Label': 'com.apple.other'}},
               'Agents': {}}, open(r + '/System/Library/xpc/launchd.plist', 'wb'), fmt=plistlib.FMT_BINARY)
plistlib.dump({'logicalScreenClass': '375w-812h@3x~iphone'}, open(r + '/Library/Wallpaper/Collections/x-375w-812h-y/Wallpaper.plist', 'wb'), fmt=plistlib.FMT_BINARY)
plistlib.dump({'logicalScreenClass': '414w-896h@3x~iphone'}, open(r + '/Library/Wallpaper/Collections/z-414w-896h/Wallpaper.plist', 'wb'), fmt=plistlib.FMT_XML)
EOF
P=$R/private/var/mobile/Library/Preferences
snap(){ (cd "$R" && find . -mindepth 1 \( -type f -printf 'F %p %s ' -exec sha256sum {} \; -o -type d -printf 'D %p\n' \) | sed 's/  \.\/.*//' | sort); }
snap > "$SB/tree.before"
fakeroot -- bash -c "bash '$TUNE' '$R' 20H392 > '$SB/tune.out' 2>&1; echo \$? > '$SB/tune.rc'; stat -c '%u:%g %a' '$P/com.apple.springboard.plist' > '$SB/own.txt'; stat -c '%u:%g' '$R/private/var/containers' > '$SB/own2.txt'"
snap > "$SB/tree.after"
# entradas y salidas: lo creado, lo borrado y lo modificado deben ser EXACTAMENTE lo que el script documenta
CH=$(diff "$SB/tree.before" "$SB/tree.after" | grep '^[<>]' | awk '{print $3}' | sort -u | tr '\n' ' ')
EXPECTED="./Library/Wallpaper/Collections/x-375w-812h-y/Wallpaper.plist ./System/Library/xpc/launchd.plist ./private ./private/var ./private/var/containers ./private/var/containers/Bundle ./private/var/containers/Data ./private/var/containers/Data/System ./private/var/containers/Shared ./private/var/containers/Shared/SystemGroup ./private/var/containers/Temp ./private/var/mobile ./private/var/mobile/Library ./private/var/mobile/Library/Preferences ./private/var/mobile/Library/Preferences/com.apple.managedconfiguration.notbackedup.plist ./private/var/mobile/Library/Preferences/com.apple.migration.plist ./private/var/mobile/Library/Preferences/com.apple.purplebuddy.plist ./private/var/mobile/Library/Preferences/com.apple.springboard.plist "
echo "cambiado: $CH" > "$SB/changed.txt"
t "tune: el conjunto de rutas creadas/modificadas es exactamente el esperado (nada mas)" test "$CH" = "$(echo $EXPECTED | tr ' ' '\n' | sort -u | tr '\n' ' ')"
t "tune: sbin/launchd y el wallpaper de otra pantalla no cambian de contenido" bash -c "! echo '$CH' | grep -q -e './sbin/launchd' -e 'z-414w-896h'"
t "tune: rc 0 (sin plutil de Apple: usa plutil_lite)" test "$(cat "$SB/tune.rc")" = 0
t "tune: dice que completo" grep -q "tuning complete for build 20H392" "$SB/tune.out"
t "tune: migration LastSystemVersion" bash -c "python3 -I -c \"import plistlib;assert plistlib.load(open('$P/com.apple.migration.plist','rb'))['LastSystemVersion']=='20H392'\""
t "tune: springboard BKNoWatchdogs, excepcion purplebuddy, cloud UI off" bash -c "python3 -I -c \"import plistlib;d=plistlib.load(open('$P/com.apple.springboard.plist','rb'));assert d['BKNoWatchdogs'] is True and d['FBLaunchWatchdogExceptions']=={'com.apple.purplebuddy':100} and d['MCForceShowCloudConfigurationUI'] is False,d\""
t "tune: purplebuddy Setup completo" bash -c "python3 -I -c \"import plistlib;d=plistlib.load(open('$P/com.apple.purplebuddy.plist','rb'));assert d=={'SetupDone':True,'SetupFinishedAllSteps':True,'SetupVersion':11,'daemonizeNeedsToRun':False},d\""
t "tune: managedconfiguration" bash -c "python3 -I -c \"import plistlib;d=plistlib.load(open('$P/com.apple.managedconfiguration.notbackedup.plist','rb'));assert d=={'LockdownActivationIndicatesCloudConfigurationAvailable':False},d\""
t "tune: prefs en XML, propietario 501:501, modo 600" bash -c "head -c 5 '$P/com.apple.springboard.plist' | grep -q '<?xml' && [ \"\$(cat '$SB/own.txt')\" = '501:501 600' ]"
t "tune: containers de root 0:0" test "$(cat "$SB/own2.txt")" = "0:0"
t "tune: wallpaper 375w-812h recibe la clase 480w-853h" bash -c "python3 -I -c \"import plistlib;assert plistlib.load(open('$R/Library/Wallpaper/Collections/x-375w-812h-y/Wallpaper.plist','rb'))['logicalScreenClass']=='480w-853h@3x~iphone'\" && head -c 6 '$R/Library/Wallpaper/Collections/x-375w-812h-y/Wallpaper.plist' | grep -q bplist"
t "tune: wallpaper de otra pantalla intacto (y en XML)" bash -c "python3 -I -c \"import plistlib;assert plistlib.load(open('$R/Library/Wallpaper/Collections/z-414w-896h/Wallpaper.plist','rb'))['logicalScreenClass']=='414w-896h@3x~iphone'\" && head -c 5 '$R/Library/Wallpaper/Collections/z-414w-896h/Wallpaper.plist' | grep -q '<?xml'"
t "tune: launchd.plist sin CommCenter, con autorun, otro job intacto" bash -c "python3 -I -c \"import plistlib;d=plistlib.load(open('$R/System/Library/xpc/launchd.plist','rb'))['LaunchDaemons'];assert not [k for k in d if 'CommCenter' in k] and d['/a/com.apple.other.plist']['Label']=='com.apple.other' and d['/System/Library/LaunchDaemons/com.herolte.autorun.plist']['ProgramArguments']==['/private/var/herolte/autorun'],d\""
t "tune: sin root real (no EUID 0) se niega" bash -c "! bash '$TUNE' '$R' 20H392"
t "tune: raiz no preparada se niega" bash -c "mkdir -p '$SB/vacio' && ! fakeroot -- bash '$TUNE' '$SB/vacio' 20H392"
echo "RESUMEN: $PASS PASS, $FAIL FALLA  (sandbox: $SB)"; [ "$FAIL" = 0 ]
