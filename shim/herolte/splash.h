/* SPDX-License-Identifier: GPL-2.0-only */
#pragma once
#include <stddef.h>
#include <stdint.h>

/*
 * Boot image for the herolte loader (docs/herolte-splash.md).
 *
 * Blob made by tools/herolte-make-splash.py, little endian:
 *   "HSPL" | u16 width | u16 height | u16 flags | u16 reserved | u32 payload_len | payload
 * flags bit 0: payload is RLE. Pixels are RGB565, row-major.
 * RLE token: control byte c; c & 0x80 -> repeat the next pixel (c & 0x7f) + 1 times,
 *            otherwise c + 1 literal pixels follow.
 *
 * The image is scaled by the integer factors that fit and centred on a black screen.
 * Runs with the MMU off, so there are only aligned 32-bit stores and loads (the blob is
 * read byte by byte); no libc, no stack buffers, no globals.
 */
#define HERO_SPLASH_HDR 16U

/* 0 on success. Negative if the blob is malformed: the header is checked before anything is drawn (-1..-3);
 * a payload that ends early (-4) is only noticed while drawing, so the picture may be partial. */
int hero_splash_blit(volatile uint32_t *fb, unsigned fb_w, unsigned fb_h,
                     const uint8_t *blob, size_t len);
