/*
 * DROP v2, lado userland (hero-run): ¿hay un paquete nuevo pendiente de consumir?
 *
 * El kernel (xnu/drop-v2/herolte_drop_core.c) publica /private/var/herolte/.drop/ready con
 * "<generación>|<sha256 hex>" cuando un paquete está entero en su sitio. hero-run anota lo ya
 * procesado en .drop/consumed. Pendiente <=> ready existe y es distinto de consumed.
 * ready no se borra nunca: el kernel no lo recrea si coincide con consumed.
 *
 * C puro (POSIX), sin Apple: se prueba en el anfitrión con xnu/drop-v2/test/test_userland.c.
 */
#ifndef DROP_V2_USERLAND_H
#define DROP_V2_USERLAND_H

#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#define DROPV2_TOKEN_MAX 160

/* Lee un fichero de control a buf (con 0 final). Longitud, o -1 si no existe o no se puede leer. */
static int
dropv2_read(const char *path, char *buf, size_t cap)
{
	int fd = open(path, O_RDONLY);
	if (fd < 0) {
		return -1;
	}
	ssize_t n = read(fd, buf, cap - 1);
	close(fd);
	if (n < 0) {
		return -1;
	}
	buf[n] = 0;
	return (int)n;
}

/*
 * 1: hay un paquete pendiente (token = su ready); 0: ready existe y ya está consumido;
 * -1: no hay ready (kernel sin DROP v2, o aún no publicado).
 */
static int
dropv2_pending(const char *ready, const char *consumed, char *token, size_t cap)
{
	char done[DROPV2_TOKEN_MAX];
	int n = dropv2_read(ready, token, cap);
	if (n <= 0) {
		return -1;
	}
	int m = dropv2_read(consumed, done, sizeof(done));
	return (m == n && memcmp(token, done, (size_t)n) == 0) ? 0 : 1;
}

/* Anota token en consumed de forma atómica: tmp + fsync + rename. 0 o -1. */
static int
dropv2_mark_consumed(const char *consumed, const char *token)
{
	char tmp[512];
	if (snprintf(tmp, sizeof(tmp), "%s.tmp", consumed) >= (int)sizeof(tmp)) {
		return -1;
	}
	int fd = open(tmp, O_WRONLY | O_CREAT | O_TRUNC, 0644);
	if (fd < 0) {
		return -1;
	}
	size_t len = strlen(token);
	int ok = write(fd, token, len) == (ssize_t)len;
#ifdef F_FULLFSYNC
	ok = ok && fcntl(fd, F_FULLFSYNC) == 0;
#else
	ok = ok && fsync(fd) == 0;
#endif
	ok = (close(fd) == 0) && ok;
	if (!ok || rename(tmp, consumed) != 0) {
		unlink(tmp);
		return -1;
	}
	return 0;
}

#endif /* DROP_V2_USERLAND_H */
