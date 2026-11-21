/*
 * HEROLTE DROP v2: núcleo (ver herolte_drop_core.h y README.md).
 *
 * Formato de la zona (little-endian):
 *   bloque 0: "HERODRP2" | u32 proto=2 | u32 count | u64 bytes | u64 generation |
 *             u8 payload_sha256[32] | ... | u8 header_sha256[32] en [4064,4096)
 *   desde el bloque 1: `count` entradas, alineadas a 8:
 *             u32 path_len | u32 mode (0 = directorio) | u64 size | path | datos
 *
 * Protocolo (todo lo que modifica el volumen cuelga de .drop/ hasta el commit):
 *   TRYING -> (stage + stage.list) -> STAGED -> commit por rename -> COMMITTED -> ready
 * Cada fichero de control se reemplaza con tmp + barrera + rename. Tras un corte, STAGED
 * se completa hacia delante desde el propio staging, sin necesitar la zona.
 */
#if !defined(KERNEL) || defined(ARM64_BOARD_CONFIG_HEROLTE)

#ifdef KERNEL
#include <sys/param.h>
#include <sys/systm.h>
#include <sys/errno.h>
#include <string.h>
#else
#include <errno.h>
#include <stdio.h>
#include <string.h>
#endif

#include "herolte_drop_core.h"

#define ROOT        "/private/var/herolte"
#define PREFIX      ROOT "/"
#define PFX_LEN     21u
#define DROPDIR     ROOT "/.drop"
#define STAGE       DROPDIR "/stage"
#define TRASH       DROPDIR "/trash"
#define P_STATE     DROPDIR "/state"
#define P_LIST      DROPDIR "/stage.list"
#define P_READY     DROPDIR "/ready"
#define P_CONSUMED  DROPDIR "/consumed"
#define PATHBUF     640u
#define STATE_SIZE  88u

enum { PH_TRYING = 1, PH_STAGED = 2, PH_COMMITTED = 3, PH_FAILED = 4 };

typedef struct {
	const hdc_ops *o;
	uint8_t       *win;
	char          *list;
} hdc_ctx;

typedef struct {
	uint32_t phase, attempts;
	uint64_t gen;
	uint8_t  sha[32];
} hdc_state;

typedef struct {
	uint32_t count;
	uint64_t bytes, gen;
	uint8_t  sha[32];
} hdc_zone;

#define LOG(c, ...) do { \
		char _m[192]; \
		snprintf(_m, sizeof(_m), __VA_ARGS__); \
		(c)->o->log((c)->o->ctx, _m); \
	} while (0)

/* ------------------------------------------------------------------ little-endian */
static uint32_t
rd32(const uint8_t *p)
{
	return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}

static uint64_t
rd64(const uint8_t *p)
{
	return (uint64_t)rd32(p) | (uint64_t)rd32(p + 4) << 32;
}

static void
wr32(uint8_t *p, uint32_t v)
{
	p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); p[2] = (uint8_t)(v >> 16); p[3] = (uint8_t)(v >> 24);
}

static void
wr64(uint8_t *p, uint64_t v)
{
	wr32(p, (uint32_t)v);
	wr32(p + 4, (uint32_t)(v >> 32));
}

/* ------------------------------------------------------------------ SHA-256 (FIPS 180-4) */
typedef struct {
	uint32_t h[8];
	uint64_t total;
	uint8_t  buf[64];
	uint32_t n;
} hdc_sha;

static const uint32_t sha_k[64] = {
	0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
	0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
	0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
	0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
	0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
	0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
	0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
	0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
};

#define ROR(x, n) (((x) >> (n)) | ((x) << (32 - (n))))

static void
sha_block(uint32_t *h, const uint8_t *p)
{
	uint32_t w[64], v[8];
	for (int i = 0; i < 16; i++) {
		w[i] = (uint32_t)p[4 * i] << 24 | (uint32_t)p[4 * i + 1] << 16 |
		    (uint32_t)p[4 * i + 2] << 8 | (uint32_t)p[4 * i + 3];
	}
	for (int i = 16; i < 64; i++) {
		uint32_t s0 = ROR(w[i - 15], 7) ^ ROR(w[i - 15], 18) ^ (w[i - 15] >> 3);
		uint32_t s1 = ROR(w[i - 2], 17) ^ ROR(w[i - 2], 19) ^ (w[i - 2] >> 10);
		w[i] = w[i - 16] + s0 + w[i - 7] + s1;
	}
	for (int i = 0; i < 8; i++) {
		v[i] = h[i];
	}
	for (int i = 0; i < 64; i++) {
		uint32_t s1 = ROR(v[4], 6) ^ ROR(v[4], 11) ^ ROR(v[4], 25);
		uint32_t ch = (v[4] & v[5]) ^ (~v[4] & v[6]);
		uint32_t t1 = v[7] + s1 + ch + sha_k[i] + w[i];
		uint32_t s0 = ROR(v[0], 2) ^ ROR(v[0], 13) ^ ROR(v[0], 22);
		uint32_t mj = (v[0] & v[1]) ^ (v[0] & v[2]) ^ (v[1] & v[2]);
		uint32_t t2 = s0 + mj;
		v[7] = v[6]; v[6] = v[5]; v[5] = v[4]; v[4] = v[3] + t1;
		v[3] = v[2]; v[2] = v[1]; v[1] = v[0]; v[0] = t1 + t2;
	}
	for (int i = 0; i < 8; i++) {
		h[i] += v[i];
	}
}

static void
sha_init(hdc_sha *s)
{
	static const uint32_t iv[8] = { 0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
		                        0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19 };
	memcpy(s->h, iv, sizeof(iv));
	s->total = 0;
	s->n = 0;
}

static void
sha_update(hdc_sha *s, const void *data, size_t len)
{
	const uint8_t *p = data;
	s->total += len;
	while (len > 0) {
		size_t take = 64 - s->n;
		if (take > len) {
			take = len;
		}
		memcpy(s->buf + s->n, p, take);
		s->n += (uint32_t)take;
		p += take;
		len -= take;
		if (s->n == 64) {
			sha_block(s->h, s->buf);
			s->n = 0;
		}
	}
}

static void
sha_final(hdc_sha *s, uint8_t out[32])
{
	uint64_t bits = s->total * 8;
	uint8_t pad = 0x80, zero = 0, len[8];
	sha_update(s, &pad, 1);
	while (s->n != 56) {
		sha_update(s, &zero, 1);
	}
	for (int i = 0; i < 8; i++) {
		len[i] = (uint8_t)(bits >> (56 - 8 * i));
	}
	sha_update(s, len, 8);
	for (int i = 0; i < 8; i++) {
		out[4 * i] = (uint8_t)(s->h[i] >> 24);
		out[4 * i + 1] = (uint8_t)(s->h[i] >> 16);
		out[4 * i + 2] = (uint8_t)(s->h[i] >> 8);
		out[4 * i + 3] = (uint8_t)s->h[i];
	}
}

static void
sha_buf(const void *data, size_t len, uint8_t out[32])
{
	hdc_sha s;
	sha_init(&s);
	sha_update(&s, data, len);
	sha_final(&s, out);
}

#ifdef HDC_EXPOSE
void
hdc_sha256_buf(const void *data, size_t len, uint8_t out[32])
{
	sha_buf(data, len, out);
}
#endif

static void
hex32(const uint8_t *in, char out[65])
{
	static const char d[] = "0123456789abcdef";
	for (int i = 0; i < 32; i++) {
		out[2 * i] = d[in[i] >> 4];
		out[2 * i + 1] = d[in[i] & 15];
	}
	out[64] = 0;
}

/* ------------------------------------------------------------------ lector de payload */
static int
hdc_fill(hdc_rd *r, uint64_t off)
{
	uint64_t start = (off / HDC_BLOCK) * HDC_BLOCK;
	if (start >= HDC_MAX_PAYLOAD) {
		r->have = 0;
		return EINVAL;
	}
	uint64_t room = HDC_MAX_PAYLOAD - start;
	uint32_t n = room < HDC_CHUNK ? (uint32_t)room : HDC_CHUNK;
	int e = r->ops->zone_read(r->ops->ctx, HDC_BLOCK + start, r->buf, n);
	r->pos = start;
	r->have = e ? 0 : n;
	if (e) {
		r->io_error = 1;
	}
	return e;
}

/* ¿[off, off+len) está dentro de la ventana? Sin sumas que puedan dar la vuelta. */
static int
hdc_in(const hdc_rd *r, uint64_t off, uint32_t len)
{
	if (off < r->pos) {
		return 0;
	}
	uint64_t d = off - r->pos;
	return d <= r->have && len <= (uint64_t)(r->have - (uint32_t)d);
}

void
hdc_rd_init(hdc_rd *r, const hdc_ops *ops, uint8_t *buf, uint64_t limit)
{
	memset(r, 0, sizeof(*r));
	r->ops = ops;
	r->buf = buf;
	r->limit = limit;
}

static const uint8_t *
hdc_at(hdc_rd *r, uint64_t off, uint32_t len)
{
	if (len == 0 || len > HDC_CHUNK / 2 || off > r->limit || len > r->limit - off) {
		return NULL;
	}
	if (!hdc_in(r, off, len)) {
		if (hdc_fill(r, off) != 0 || !hdc_in(r, off, len)) {
			return NULL;
		}
	}
	return r->buf + (off - r->pos);
}

#ifdef HDC_EXPOSE
int64_t
hdc_at_off(hdc_rd *r, uint64_t off, uint32_t len)
{
	const uint8_t *p = hdc_at(r, off, len);
	return p ? (int64_t)(p - r->buf) : -1;
}

/* Réplica de la expresión de 0333, solo para demostrar el defecto en las pruebas. */
int64_t
hdc_at_off_0333(hdc_rd *r, uint64_t off, uint32_t len)
{
	if (len > HDC_CHUNK / 2 || off > r->limit || len > r->limit - off) {
		return -1;
	}
	if (off < r->pos || len > r->pos + r->have - off) {
		if (hdc_fill(r, off) || off < r->pos || len > r->pos + r->have - off) {
			return -1;
		}
	}
	return (int64_t)(off - r->pos);
}
#endif

/* ------------------------------------------------------------------ rutas y entradas */
static int
hdc_rel_ok(const char *s, uint32_t n)
{
	if (n == 0 || s[n - 1] == '/') {
		return 0;
	}
	int first = 1;
	uint32_t i = 0;
	while (i < n) {
		uint32_t j = i;
		while (j < n && s[j] != '/') {
			if (s[j] == '\\') {
				return 0;
			}
			j++;
		}
		uint32_t cl = j - i;
		if (cl == 0 || (cl == 1 && s[i] == '.') || (cl == 2 && s[i] == '.' && s[i + 1] == '.')) {
			return 0;
		}
		if (first && cl >= 5 && memcmp(s + i, ".drop", 5) == 0) {
			return 0;               /* nombres reservados del protocolo */
		}
		first = 0;
		i = j + 1;
	}
	return 1;
}

typedef struct {
	uint32_t    path_len, mode;
	uint64_t    size, data;
	int         is_dir;
	const char *rel;
	uint32_t    rel_len;
} hdc_ent;

/* Lee y valida una entrada; avanza *off. 0, EINVAL (paquete malformado) o EIO (lectura). */
static int
hdc_next(hdc_rd *r, uint64_t *off, char *path, hdc_ent *e)
{
	const uint8_t *p = hdc_at(r, *off, 16);
	if (p == NULL) {
		return r->io_error ? EIO : EINVAL;
	}
	e->path_len = rd32(p);
	e->mode = rd32(p + 4);
	e->size = rd64(p + 8);
	if (e->path_len <= PFX_LEN || e->path_len > HDC_MAX_PATH) {
		return EINVAL;
	}
	p = hdc_at(r, *off + 16, e->path_len);
	if (p == NULL) {
		return r->io_error ? EIO : EINVAL;
	}
	memcpy(path, p, e->path_len);
	path[e->path_len] = 0;
	if (strlen(path) != e->path_len || strncmp(path, PREFIX, PFX_LEN) != 0) {
		return EINVAL;                  /* NUL dentro de la ruta o fuera del prefijo */
	}
	e->rel = path + PFX_LEN;
	e->rel_len = e->path_len - PFX_LEN;
	if (!hdc_rel_ok(e->rel, e->rel_len)) {
		return EINVAL;
	}
	e->is_dir = e->mode == 0;
	if (e->is_dir ? e->size != 0 : (e->mode != 0644 && e->mode != 0755)) {
		return EINVAL;
	}
	uint64_t data = *off + ((16 + (uint64_t)e->path_len + 7) & ~7ull);
	if (data > r->limit || e->size > r->limit - data) {
		return EINVAL;
	}
	uint64_t pad = (e->size + 7) & ~7ull;           /* size <= limit: no desborda */
	if (pad > r->limit - data) {
		return EINVAL;
	}
	e->data = data;
	*off = data + pad;
	return 0;
}

static void
hdc_unit_of(const char *rel, uint32_t n, char *kind, uint32_t *ulen)
{
	*kind = 'F';
	*ulen = n;
	if (n > 5 && memcmp(rel, "apps/", 5) == 0) {
		uint32_t j = 5;
		while (j < n && rel[j] != '/') {
			j++;
		}
		if (j < n && j - 5 >= 5 && memcmp(rel + j - 4, ".app", 4) == 0) {
			*kind = 'B';
			*ulen = j;
		}
	}
}

/* ------------------------------------------------------------------ zona */
/* 0: válida; ENOENT: no hay paquete; EINVAL: cabecera inválida (se registra); EIO */
static int
hdc_zone_header(hdc_ctx *c, hdc_zone *z)
{
	uint8_t *b = c->win, h[32];
	if (c->o->zone_read(c->o->ctx, 0, b, HDC_BLOCK) != 0) {
		return EIO;
	}
	if (memcmp(b, "HERODRP1", 8) == 0) {
		LOG(c, "HEROLTE DROP: v1 package ignored (repack with tools/herolte-drop.py v2)");
		return ENOENT;
	}
	if (memcmp(b, "HERODRP2", 8) != 0) {
		return ENOENT;
	}
	sha_buf(b, HDC_BLOCK - 32, h);
	if (memcmp(h, b + HDC_BLOCK - 32, 32) != 0 || rd32(b + 8) != 2) {
		LOG(c, "HEROLTE DROP: package header invalid");
		return EINVAL;
	}
	z->count = rd32(b + 12);
	z->bytes = rd64(b + 16);
	z->gen = rd64(b + 24);
	memcpy(z->sha, b + 32, 32);
	if (z->count == 0 || z->bytes == 0 || z->bytes > HDC_MAX_PAYLOAD || (z->bytes & 7) != 0) {
		LOG(c, "HEROLTE DROP: package header has impossible sizes");
		return EINVAL;
	}
	return 0;
}

static int
hdc_verify_payload(hdc_ctx *c, const hdc_zone *z)
{
	hdc_rd r;
	hdc_sha s;
	uint8_t h[32];
	hdc_rd_init(&r, c->o, c->win, z->bytes);
	sha_init(&s);
	for (uint64_t off = 0; off < z->bytes;) {
		uint64_t left = z->bytes - off;
		uint32_t n = left < HDC_CHUNK / 2 ? (uint32_t)left : HDC_CHUNK / 2;
		const uint8_t *p = hdc_at(&r, off, n);
		if (p == NULL) {
			return r.io_error ? EIO : EINVAL;
		}
		sha_update(&s, p, n);
		off += n;
	}
	sha_final(&s, h);
	return memcmp(h, z->sha, 32) == 0 ? 0 : EINVAL;
}

/* ------------------------------------------------------------------ lista de unidades */
typedef struct {
	char    *buf;
	uint32_t len, units;
	int      fw;
	char     last_b[HDC_MAX_PATH + 1];
} hdc_list;

static int
hdc_list_add(hdc_list *l, char kind, const char *name, uint32_t n)
{
	if (l->units >= HDC_MAX_UNITS || l->len + n + 8 > HDC_LIST_MAX) {
		return EFBIG;
	}
	l->buf[l->len++] = kind;
	l->buf[l->len++] = ' ';
	memcpy(l->buf + l->len, name, n);
	l->len += n;
	l->buf[l->len++] = '\n';
	l->units++;
	return 0;
}

/* Primera línea de stage.list: identidad del paquete que se está instalando. */
static void
hdc_ident(const hdc_zone *z, char *out, size_t cap)
{
	char hex[65];
	hex32(z->sha, hex);
	snprintf(out, cap, "HDRL2 %llu %s\n", (unsigned long long)z->gen, hex);
}

/* Pase 1: valida TODO el paquete sin escribir y construye stage.list. */
static int
hdc_scan(hdc_ctx *c, const hdc_zone *z, hdc_list *l)
{
	hdc_rd r;
	uint64_t off = 0;
	char path[HDC_MAX_PATH + 1];
	hdc_ent e;
	hdc_rd_init(&r, c->o, c->win, z->bytes);
	memset(l, 0, sizeof(*l));
	l->buf = c->list;
	char hdr[160];
	hdc_ident(z, hdr, sizeof(hdr));
	l->len = (uint32_t)strlen(hdr);
	memcpy(l->buf, hdr, l->len);
	for (uint32_t i = 0; i < z->count; i++) {
		int err = hdc_next(&r, &off, path, &e);
		if (err) {
			return err;
		}
		if (e.is_dir) {
			continue;
		}
		char kind;
		uint32_t ulen;
		hdc_unit_of(e.rel, e.rel_len, &kind, &ulen);
		if (kind == 'F' && ulen == 11 && memcmp(e.rel, "wifi/fw.bin", 11) == 0) {
			l->fw = 1;                      /* el último: el kernel espera ese fichero */
			continue;
		}
		if (kind == 'B') {
			if (strlen(l->last_b) == ulen && memcmp(l->last_b, e.rel, ulen) == 0) {
				continue;
			}
			memcpy(l->last_b, e.rel, ulen);
			l->last_b[ulen] = 0;
		}
		err = hdc_list_add(l, kind, e.rel, ulen);
		if (err) {
			return err;
		}
	}
	if (off != z->bytes) {
		return EINVAL;                          /* sobran o faltan bytes */
	}
	if (l->fw && hdc_list_add(l, 'F', "wifi/fw.bin", 11)) {
		return EFBIG;
	}
	if (l->len + 8 > HDC_LIST_MAX) {
		return EFBIG;
	}
	memcpy(l->buf + l->len, "END\n", 4);
	l->len += 4;
	l->buf[l->len] = 0;
	return 0;
}

/* ------------------------------------------------------------------ sistema de ficheros */
static int
hdc_mkdir_p(hdc_ctx *c, const char *path)
{
	char t[PATHBUF];
	size_t n = strlen(path);
	if (n >= sizeof(t)) {
		return ENAMETOOLONG;
	}
	memcpy(t, path, n + 1);
	for (size_t i = 1; i < n; i++) {
		if (t[i] == '/') {
			t[i] = 0;
			int e = c->o->fs_mkdir(c->o->ctx, t);
			t[i] = '/';
			if (e) {
				return e;
			}
		}
	}
	return c->o->fs_mkdir(c->o->ctx, t);
}

static int
hdc_mkdir_parent(hdc_ctx *c, const char *path)
{
	char t[PATHBUF];
	size_t n = strlen(path);
	if (n >= sizeof(t)) {
		return ENAMETOOLONG;
	}
	memcpy(t, path, n + 1);
	char *s = strrchr(t, '/');
	if (s == NULL || s == t) {
		return EINVAL;
	}
	*s = 0;
	return hdc_mkdir_p(c, t);
}

/* Reemplazo atómico y duradero: tmp, barrera (los datos no van por el journal), rename. */
static int
hdc_put(hdc_ctx *c, const char *path, const void *data, uint32_t len)
{
	char tmp[PATHBUF];
	void *h = NULL;
	snprintf(tmp, sizeof(tmp), "%s.tmp", path);
	int e = c->o->fs_open_w(c->o->ctx, tmp, 0644, &h);
	if (e) {
		return e;
	}
	if (len > 0) {
		e = c->o->fs_write(c->o->ctx, h, 0, data, len);
	}
	int ce = c->o->fs_close_w(c->o->ctx, h);
	if (e || ce) {
		return e ? e : ce;
	}
	e = c->o->barrier(c->o->ctx);
	if (e) {
		return e;
	}
	return c->o->fs_rename(c->o->ctx, tmp, path);
}

/* ------------------------------------------------------------------ estado */
static void
hdc_state_enc(uint8_t b[STATE_SIZE], uint32_t phase, uint32_t attempts, uint64_t gen, const uint8_t *sha)
{
	memset(b, 0, STATE_SIZE);
	memcpy(b, "HDROPST2", 8);
	wr32(b + 8, phase);
	wr32(b + 12, attempts);
	wr64(b + 16, gen);
	memcpy(b + 24, sha, 32);
	sha_buf(b, 56, b + 56);
}

static int
hdc_state_put(hdc_ctx *c, uint32_t phase, uint32_t attempts, const hdc_zone *z)
{
	uint8_t b[STATE_SIZE];
	hdc_state_enc(b, phase, attempts, z->gen, z->sha);
	return hdc_put(c, P_STATE, b, STATE_SIZE);
}

/* 1 si hay un estado válido. Un estado ilegible o corrupto se trata como ausente. */
static int
hdc_state_load(hdc_ctx *c, hdc_state *st)
{
	uint8_t b[96], h[32];
	uint32_t n = 0;
	if (c->o->fs_read(c->o->ctx, P_STATE, b, sizeof(b), &n) != 0 || n != STATE_SIZE) {
		return 0;
	}
	sha_buf(b, 56, h);
	if (memcmp(b, "HDROPST2", 8) != 0 || memcmp(h, b + 56, 32) != 0) {
		return 0;
	}
	st->phase = rd32(b + 8);
	st->attempts = rd32(b + 12);
	st->gen = rd64(b + 16);
	memcpy(st->sha, b + 24, 32);
	return st->phase >= PH_TRYING && st->phase <= PH_FAILED;
}

static int
hdc_same(const hdc_state *st, const hdc_zone *z)
{
	return st->gen == z->gen && memcmp(st->sha, z->sha, 32) == 0;
}

/* ------------------------------------------------------------------ publicación */
static int
hdc_file_is(hdc_ctx *c, const char *path, const char *tok)
{
	char b[128];
	uint32_t n = 0;
	size_t want = strlen(tok);
	return c->o->fs_read(c->o->ctx, path, b, sizeof(b), &n) == 0 && n == want && memcmp(b, tok, want) == 0;
}

static int
hdc_ensure_ready(hdc_ctx *c, const hdc_state *st)
{
	char tok[128], hex[65];
	hex32(st->sha, hex);
	snprintf(tok, sizeof(tok), "%llu|%s", (unsigned long long)st->gen, hex);
	if (hdc_file_is(c, P_CONSUMED, tok) || hdc_file_is(c, P_READY, tok)) {
		return 0;
	}
	return hdc_put(c, P_READY, tok, (uint32_t)strlen(tok));
}

/* ------------------------------------------------------------------ staging y commit */
static int
hdc_stage(hdc_ctx *c, const hdc_zone *z)
{
	hdc_rd r;
	uint64_t off = 0;
	char path[HDC_MAX_PATH + 1], dst[PATHBUF];
	hdc_ent e;
	hdc_rd_init(&r, c->o, c->win, z->bytes);
	for (uint32_t i = 0; i < z->count; i++) {
		int err = hdc_next(&r, &off, path, &e);
		if (err) {
			return err;
		}
		snprintf(dst, sizeof(dst), "%s/%s", STAGE, e.rel);
		if (e.is_dir) {
			err = hdc_mkdir_p(c, dst);
		} else {
			void *h = NULL;
			err = hdc_mkdir_parent(c, dst);
			if (!err) {
				err = c->o->fs_open_w(c->o->ctx, dst, e.mode, &h);
			}
			if (!err) {
				for (uint64_t done = 0; done < e.size && !err;) {
					uint64_t left = e.size - done;
					uint32_t n = left < HDC_CHUNK / 2 ? (uint32_t)left : HDC_CHUNK / 2;
					const uint8_t *p = hdc_at(&r, e.data + done, n);
					if (p == NULL) {
						err = r.io_error ? EIO : EINVAL;
						break;
					}
					err = c->o->fs_write(c->o->ctx, h, done, p, n);
					done += n;
				}
				int ce = c->o->fs_close_w(c->o->ctx, h);
				err = err ? err : ce;
			}
		}
		if (err) {
			LOG(c, "HEROLTE DROP: staging %s: error %d", e.rel, err);
			return err;
		}
	}
	return 0;
}

static int
hdc_load_list(hdc_ctx *c, const hdc_state *st)
{
	uint32_t n = 0;
	hdc_zone z = { .gen = st->gen };
	char want[160];
	memcpy(z.sha, st->sha, 32);
	if (c->o->fs_read(c->o->ctx, P_LIST, c->list, HDC_LIST_MAX - 1, &n) != 0 || n < 8) {
		return EINVAL;
	}
	c->list[n] = 0;
	hdc_ident(&z, want, sizeof(want));
	if (strncmp(c->list, want, strlen(want)) != 0 || memcmp(c->list + n - 4, "END\n", 4) != 0) {
		return EINVAL;
	}
	return 0;
}

static int
hdc_commit(hdc_ctx *c, const hdc_state *st)
{
	char *line = strchr(c->list, '\n');
	char src[PATHBUF], dst[PATHBUF], tr[PATHBUF];
	if (line == NULL) {
		return EINVAL;
	}
	for (line++; strncmp(line, "END\n", 4) != 0;) {
		char *nl = strchr(line, '\n');
		if (nl == NULL || line[1] != ' ' || (line[0] != 'F' && line[0] != 'B')) {
			return EINVAL;
		}
		*nl = 0;
		const char *name = line + 2;
		char kind = line[0];
		if (!hdc_rel_ok(name, (uint32_t)strlen(name))) {
			return EINVAL;
		}
		snprintf(src, sizeof(src), "%s/%s", STAGE, name);
		snprintf(dst, sizeof(dst), "%s/%s", ROOT, name);
		line = nl + 1;
		if (!c->o->fs_exists(c->o->ctx, src)) {
			continue;                               /* ya hecho en un intento anterior */
		}
		int e = hdc_mkdir_parent(c, dst);
		if (e) {
			return e;
		}
		if (kind == 'B' && c->o->fs_exists(c->o->ctx, dst)) {
			const char *base = strrchr(name, '/');
			e = hdc_mkdir_p(c, TRASH);
			if (e) {
				return e;
			}
			snprintf(tr, sizeof(tr), "%s/%s.%llu", TRASH, base ? base + 1 : name, (unsigned long long)st->gen);
			e = c->o->fs_rename(c->o->ctx, dst, tr);
			if (e) {
				return e;
			}
		}
		e = c->o->fs_rename(c->o->ctx, src, dst);
		if (e) {
			return e;
		}
	}
	return 0;
}

static int
hdc_finish(hdc_ctx *c, const hdc_state *st)
{
	hdc_zone z = { .gen = st->gen };
	memcpy(z.sha, st->sha, 32);
	int e = c->o->barrier(c->o->ctx);                       /* los renames del commit, duraderos */
	if (e) {
		return e;
	}
	e = hdc_state_put(c, PH_COMMITTED, st->attempts, &z);
	if (e) {
		return e;
	}
	e = c->o->barrier(c->o->ctx);                           /* COMMITTED duradero antes de publicar */
	if (e) {
		return e;
	}
	e = hdc_ensure_ready(c, st);
	if (e) {
		return e;
	}
	(void)c->o->fs_unlink(c->o->ctx, P_LIST);               /* limpieza: best-effort */
	LOG(c, "HEROLTE DROP: package %llu ready for userland", (unsigned long long)st->gen);
	return 0;
}

/* ------------------------------------------------------------------ arranque */
int
hdc_boot(const hdc_ops *ops, uint8_t *window, char *list)
{
	hdc_ctx c = { .o = ops, .win = window, .list = list };
	hdc_state st;
	hdc_zone z;
	hdc_list l;
	int e = hdc_mkdir_p(&c, DROPDIR);
	if (e) {
		return e;
	}
	if (ops->fs_exists(ops->ctx, DROPDIR "/state.tmp")) {
		(void)ops->fs_unlink(ops->ctx, DROPDIR "/state.tmp");
	}
	int have = hdc_state_load(&c, &st);

	if (have && st.phase == PH_STAGED) {                    /* transacción interrumpida: hacia delante */
		e = hdc_load_list(&c, &st);
		if (e == 0) {
			LOG(&c, "HEROLTE DROP: resuming interrupted install of package %llu", (unsigned long long)st.gen);
			e = hdc_commit(&c, &st);
			return e ? e : hdc_finish(&c, &st);
		}
		LOG(&c, "HEROLTE DROP: STAGED without a valid stage.list; reinstalling from the zone");
		have = 0;
	}

	e = hdc_zone_header(&c, &z);
	if (e == ENOENT) {
		return 0;
	}
	if (e == EINVAL) {
		return 0;
	}
	if (e) {
		return e;
	}
	if (have && st.phase == PH_COMMITTED && hdc_same(&st, &z)) {
		return hdc_ensure_ready(&c, &st);
	}
	if (have && st.phase == PH_FAILED && hdc_same(&st, &z)) {
		LOG(&c, "HEROLTE DROP: package %llu failed %u times; waiting for a new generation",
		    (unsigned long long)z.gen, st.attempts);
		return 0;
	}
	e = hdc_verify_payload(&c, &z);
	if (e == EINVAL) {
		LOG(&c, "HEROLTE DROP: payload does not match its SHA-256; package ignored");
		return 0;
	}
	if (e) {
		return e;
	}
	e = hdc_scan(&c, &z, &l);
	if (e == EINVAL || e == EFBIG) {
		LOG(&c, "HEROLTE DROP: package rejected by validation (%d); nothing written", e);
		return 0;
	}
	if (e) {
		return e;
	}

	uint32_t attempts = (have && st.phase == PH_TRYING && hdc_same(&st, &z)) ? st.attempts + 1 : 1;
	if (attempts > HDC_MAX_TRIES) {
		(void)hdc_state_put(&c, PH_FAILED, attempts - 1, &z);
		LOG(&c, "HEROLTE DROP: package %llu abandoned after %u attempts", (unsigned long long)z.gen, attempts - 1);
		return 0;
	}
	e = hdc_state_put(&c, PH_TRYING, attempts, &z);
	if (e) {
		return e;
	}
	e = hdc_stage(&c, &z);
	if (e) {
		return e;
	}
	e = hdc_put(&c, P_LIST, c.list, l.len);                 /* la barrera de hdc_put cubre todo el staging */
	if (e) {
		return e;
	}
	e = hdc_state_put(&c, PH_STAGED, attempts, &z);
	if (e) {
		return e;
	}
	e = ops->barrier(ops->ctx);                             /* STAGED duradero antes de tocar destinos */
	if (e) {
		return e;
	}
	st.phase = PH_STAGED;
	st.attempts = attempts;
	st.gen = z.gen;
	memcpy(st.sha, z.sha, 32);
	e = hdc_load_list(&c, &st);
	if (e) {
		return e;
	}
	e = hdc_commit(&c, &st);
	return e ? e : hdc_finish(&c, &st);
}

#endif /* !KERNEL || ARM64_BOARD_CONFIG_HEROLTE */
