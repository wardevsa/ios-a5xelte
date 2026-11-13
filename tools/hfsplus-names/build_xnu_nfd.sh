#!/bin/bash
# build_xnu_nfd.sh BUILDTREE_TGZ OUTDIR : extract XNU's utfconv sources from the CI build tree and compile xnu_nfd (needs gcc). Nothing is installed.
set -euo pipefail
T=${1:?buildtree.tgz} O=${2:?outdir}; H=$(cd "$(dirname "$0")" && pwd)
[[ -e $O/xnu_nfd ]] && { echo "$O/xnu_nfd already exists"; exit 0; }
mkdir -p "$O/src" "$O/stubs/sys" "$O/stubs/libkern" "$O/stubs/kern"
tar -xzf "$T" -C "$O/src" xnu/bsd/vfs/vfs_utfconv.c xnu/bsd/vfs/vfs_utfconvdata.h xnu/bsd/sys/utfconv.h
: > "$O/stubs/sys/param.h"; : > "$O/stubs/sys/malloc.h"; : > "$O/stubs/kern/assert.h"; : > "$O/stubs/sys/appleapiopts.h"
echo '#include <errno.h>' > "$O/stubs/sys/errno.h"
printf '%s\n' '#include <stdint.h>' '#include <endian.h>' '#define OSSwapInt16(x) __builtin_bswap16(x)' \
  '#define OSSwapHostToBigInt16(x) htobe16(x)' '#define OSSwapBigToHostInt16(x) be16toh(x)' \
  '#define OSSwapHostToLittleInt16(x) htole16(x)' '#define OSSwapLittleToHostInt16(x) le16toh(x)' > "$O/stubs/libkern/OSByteOrder.h"
X=$O/src/xnu/bsd
cp "$H/xnu_nfd.c" "$O/xnu_nfd.c"
gcc -O1 -w -DKERNEL=1 -D__APPLE_API_UNSTABLE -D__APPLE_API_PRIVATE -DKERNEL_PRIVATE -DMAXPATHLEN=1024 -DZ_WAITOK=0 \
  '-Dkalloc_data(a,b)=malloc(a)' '-Dkfree_data(a,b)=free(a)' -I"$O/stubs" -I"$X" -I"$X/vfs" -o "$O/xnu_nfd" "$O/xnu_nfd.c"
echo "built $O/xnu_nfd"
