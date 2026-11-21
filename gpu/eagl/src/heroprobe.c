// SPDX-License-Identifier: MIT
// Galaxy S7 port: the smallest possible inserted library, to tell "dyld does not load what the kernel inserts" from "libheroapp has a
// dependency that fails to load" (E-0336). It links only libSystem; its constructor appends one line to /private/var/tmp/heroprobe.log
// (world-writable, no sandbox needed). Dropped in place of lib/libheroapp.dylib for one boot.
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <unistd.h>

__attribute__((constructor)) static void
probe(void)
{
   char line[160];
   int n = snprintf(line, sizeof line, "heroprobe loaded in %s pid %d\n", getprogname(), (int)getpid());
   int fd = open("/private/var/tmp/heroprobe.log", O_WRONLY | O_CREAT | O_APPEND, 0666);
   if (fd >= 0) {
      (void)!write(fd, line, (size_t)(n > 0 ? n : 0));
      fchmod(fd, 0666);
      close(fd);
   }
}
