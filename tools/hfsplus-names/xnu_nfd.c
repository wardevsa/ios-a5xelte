/* Userland harness around XNU's OWN vfs_utfconv.c: utf8_decodestr(..., UTF_DECOMPOSED) is what XNU's HFS stores/looks up for a name.
   stdin: one UTF-8 name per line. stdout: "<rc> <hex UTF-16 units>". Built by build_xnu_nfd.sh from the XNU tree of the CI build; not part of the kernel. */
#define VFS_UTF8_UNIT_TEST 1
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <sys/types.h>
#include "vfs_utfconv.c"
int main(void) {
    char line[1024];
    while (fgets(line, sizeof line, stdin)) {
        size_t n = strlen(line); while (n && line[n - 1] == '\n') line[--n] = 0;
        u_int16_t out[2048]; size_t outlen = 0;
        int rc = utf8_decodestr((const u_int8_t *)line, n, out, &outlen, sizeof out, 0, UTF_DECOMPOSED);
        printf("%d", rc);
        for (size_t i = 0; i < outlen / 2; i++) printf(" %04X", out[i]);
        printf("\n");
    }
    return 0;
}
