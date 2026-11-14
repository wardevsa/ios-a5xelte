/* Prueba del lado userland de DROP v2 (gpu/eagl/test/drop_v2_userland.h) en el anfitrión.
 *   cc -Wall -Wextra -Werror -o /tmp/tu xnu/drop-v2/test/test_userland.c && /tmp/tu
 * Trabaja solo en un directorio temporal propio. */
#include "../../../gpu/eagl/test/drop_v2_userland.h"
#include <stdlib.h>

static int failures;
#define CHECK(c) do { if (!(c)) { printf("  [FALLA] %s (línea %d)\n", #c, __LINE__); failures++; } else { printf("  [OK] %s\n", #c); } } while (0)

static void put(const char *p, const char *s) { FILE *f = fopen(p, "w"); fputs(s, f); fclose(f); }

int main(void)
{
	char dir[] = "/tmp/dropv2-user-XXXXXX", ready[256], consumed[256], tok[DROPV2_TOKEN_MAX], cur[DROPV2_TOKEN_MAX];
	if (!mkdtemp(dir)) { return 2; }
	snprintf(ready, sizeof ready, "%s/ready", dir);
	snprintf(consumed, sizeof consumed, "%s/consumed", dir);

	CHECK(dropv2_pending(ready, consumed, tok, sizeof tok) == -1);             /* kernel sin v2 / aún sin publicar */
	put(ready, "1|abc");
	CHECK(dropv2_pending(ready, consumed, tok, sizeof tok) == 1 && strcmp(tok, "1|abc") == 0);
	CHECK(dropv2_mark_consumed(consumed, tok) == 0);
	CHECK(dropv2_read(consumed, cur, sizeof cur) == 5 && strcmp(cur, "1|abc") == 0);
	CHECK(dropv2_pending(ready, consumed, tok, sizeof tok) == 0);              /* ya consumido: nada pendiente */
	put(ready, "2|abc");                                                       /* otra generación, mismo hash */
	CHECK(dropv2_pending(ready, consumed, tok, sizeof tok) == 1);
	put(ready, "1|abcd");                                                      /* prefijo/longitud distinta */
	CHECK(dropv2_pending(ready, consumed, tok, sizeof tok) == 1);
	put(ready, "");                                                            /* ready vacío: no es válido */
	CHECK(dropv2_pending(ready, consumed, tok, sizeof tok) == -1);
	put(ready, "1|abc");
	put(consumed, "1|ab");                                                     /* consumed truncado: pendiente */
	CHECK(dropv2_pending(ready, consumed, tok, sizeof tok) == 1);
	CHECK(dropv2_mark_consumed(consumed, "9|z") == 0 && dropv2_read(consumed, cur, sizeof cur) == 3);
	char tmp[300];
	snprintf(tmp, sizeof tmp, "%s.tmp", consumed);
	CHECK(access(tmp, F_OK) != 0);                                             /* sin restos del tmp */
	CHECK(dropv2_mark_consumed("/nonexistent-dir/consumed", "x") == -1);       /* error, no cuelga */
	printf(failures ? "\nFALLAN %d\n" : "\ntodo correcto\n", failures);
	char cmd[300];
	snprintf(cmd, sizeof cmd, "rm -rf %s", dir);
	return system(cmd) | (failures != 0);
}
