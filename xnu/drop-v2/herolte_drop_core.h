/*
 * HEROLTE DROP v2: núcleo independiente del kernel (parser, máquina de estados, recuperación).
 *
 * Sin dependencias de XNU: todo lo que toca el sistema (zona cruda, ficheros, barrera de
 * persistencia, log) entra por la tabla hdc_ops. El mismo código se enlaza en el kernel
 * (bsd/dev/herolte_drop.c) y en el arnés de pruebas (xnu/drop-v2/test).
 *
 * Diseño y garantías: xnu/drop-v2/README.md.
 */
#ifndef HEROLTE_DROP_CORE_H
#define HEROLTE_DROP_CORE_H

#include <stdint.h>
#include <stddef.h>

#define HDC_BLOCK        4096u
#define HDC_ZONE_BLOCKS  32768u                                 /* 128 MiB */
#define HDC_MAX_PAYLOAD  ((uint64_t)(HDC_ZONE_BLOCKS - 1) * HDC_BLOCK)
#define HDC_CHUNK        (256u * HDC_BLOCK)                     /* ventana de lectura: 1 MiB */
#define HDC_LIST_MAX     65536u                                 /* tamaño de stage.list */
#define HDC_MAX_UNITS    1024u
#define HDC_MAX_TRIES    3u
#define HDC_MAX_PATH     255u

typedef struct hdc_ops {
	void *ctx;
	/* Zona cruda: byte 0 = cabecera (bloque 0), el payload empieza en HDC_BLOCK. 0 o errno. */
	int  (*zone_read)(void *ctx, uint64_t byte_off, void *dst, uint32_t len);
	/* Sistema de ficheros (rutas absolutas). 0 o errno. */
	int  (*fs_mkdir)(void *ctx, const char *path);              /* 0 también si ya existe */
	int  (*fs_exists)(void *ctx, const char *path);             /* 1 / 0 */
	int  (*fs_open_w)(void *ctx, const char *path, uint32_t mode, void **handle);   /* crea o trunca */
	int  (*fs_write)(void *ctx, void *handle, uint64_t off, const void *data, uint32_t len);
	int  (*fs_close_w)(void *ctx, void *handle);               /* fsync + chmod + close; informa errores */
	int  (*fs_read)(void *ctx, const char *path, void *dst, uint32_t cap, uint32_t *len);   /* ENOENT */
	int  (*fs_rename)(void *ctx, const char *from, const char *to);
	int  (*fs_unlink)(void *ctx, const char *path);
	/* Barrera de persistencia: F_FULLFSYNC + sync directo del dispositivo. 0 solo si ambos van bien. */
	int  (*barrier)(void *ctx);
	void (*log)(void *ctx, const char *msg);
} hdc_ops;

/*
 * Un arranque completo: recuperación de una transacción interrumpida o instalación de la
 * zona. `window` mide HDC_CHUNK bytes y `list` HDC_LIST_MAX bytes (los reserva el llamador).
 * Devuelve 0 si no hay nada que hacer, si la zona no es válida (se registra) o si todo fue
 * bien; un errno si una operación falló y el protocolo se detuvo (se reintentará).
 */
int hdc_boot(const hdc_ops *ops, uint8_t *window, char *list);

/* Lector de payload con ventana (interno; expuesto para las pruebas) */
typedef struct hdc_rd {
	const hdc_ops *ops;
	uint8_t       *buf;
	uint64_t       pos;           /* offset de payload de buf[0] */
	uint32_t       have;          /* bytes válidos en buf */
	uint64_t       limit;         /* bytes de payload */
	int            io_error;
} hdc_rd;

void    hdc_rd_init(hdc_rd *r, const hdc_ops *ops, uint8_t *buf, uint64_t limit);

/* Pruebas */
#ifdef HDC_EXPOSE
int64_t hdc_at_off(hdc_rd *r, uint64_t off, uint32_t len);        /* versión corregida: offset en buf o -1 */
int64_t hdc_at_off_0333(hdc_rd *r, uint64_t off, uint32_t len);   /* expresión de 0333 (defectuosa) */
void    hdc_sha256_buf(const void *data, size_t len, uint8_t out[32]);
#endif

#endif /* HEROLTE_DROP_CORE_H */
