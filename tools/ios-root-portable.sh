# Sourced by a5xelte-stage-ios-root.sh: the three places where macOS and Linux differ.
#   r_uid FILE            numeric owner of FILE (BSD `stat -f %u` / GNU `stat -c %u`)
#   r_is_hfs_mount DIR    DIR is the mount point of an HFS/HFSX volume (macOS `mount` text / Linux /proc/self/mounts)
#   r_rsync_xattr_flag    the rsync flag that copies extended attributes (Apple rsync / GNU rsync)
r_uid() {
    if [[ $(uname -s) == Darwin ]]; then stat -f %u "$1"; else stat -c %u "$1"; fi
}
r_is_hfs_mount() {  # $1 = directory; R_MOUNTS_FILE is honoured only with R_TESTING=1 (the tests feed a fake mount table)
    local dir=$1
    if [[ $(uname -s) == Darwin ]]; then
        mount | grep -F " on $dir (hfs," >/dev/null
    else
        local dev mp fs rest real
        real=$(readlink -f -- "$dir") || return 1
        while read -r dev mp fs rest; do
            mp=${mp//\\040/ }
            [[ $mp == "$real" && ( $fs == hfsplus || $fs == hfs ) ]] && return 0
        done < "$([[ ${R_TESTING:-0} == 1 && -n ${R_MOUNTS_FILE:-} ]] && echo "$R_MOUNTS_FILE" || echo /proc/self/mounts)"
        return 1
    fi
}
r_rsync_xattr_flag() {
    if [[ $(uname -s) == Darwin ]]; then echo --extended-attributes; else echo -X; fi
}
r_rsync_bin() {  # Apple's rsync is the one that has --extended-attributes
    if [[ $(uname -s) == Darwin ]]; then echo /usr/bin/rsync; else echo rsync; fi
}
