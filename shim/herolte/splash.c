/* SPDX-License-Identifier: GPL-2.0-only */
#include "splash.h"

struct rd {
    const uint8_t *p, *end;
    unsigned run, lit;      /* pixels left in the current run / literal group */
    uint16_t val;           /* run value */
    int rle, bad;
};

static unsigned u16(const uint8_t *p) { return (unsigned)p[0] | ((unsigned)p[1] << 8); }
static uint32_t u32(const uint8_t *p) { return u16(p) | ((uint32_t)u16(p + 2) << 16); }

static uint32_t argb(uint16_t c)
{
    uint32_t r = (c >> 11) & 31U, g = (c >> 5) & 63U, b = c & 31U;
    r = (r << 3) | (r >> 2);
    g = (g << 2) | (g >> 4);
    b = (b << 3) | (b >> 2);
    return 0xff000000U | (r << 16) | (g << 8) | b;
}

static uint16_t next(struct rd *s)
{
    if (!s->rle) {
        if (s->end - s->p < 2) { s->bad = 1; return 0; }
        uint16_t v = (uint16_t)u16(s->p);
        s->p += 2;
        return v;
    }
    if (!s->run && !s->lit) {
        if (s->p >= s->end) { s->bad = 1; return 0; }
        unsigned c = *s->p++;
        if (c & 0x80U) {
            if (s->end - s->p < 2) { s->bad = 1; return 0; }
            s->val = (uint16_t)u16(s->p);
            s->p += 2;
            s->run = (c & 0x7fU) + 1U;
        } else {
            s->lit = c + 1U;
        }
    }
    if (s->run) {
        s->run--;
        return s->val;
    }
    if (s->end - s->p < 2) { s->bad = 1; return 0; }
    uint16_t v = (uint16_t)u16(s->p);
    s->p += 2;
    s->lit--;
    return v;
}

int hero_splash_blit(volatile uint32_t *fb, unsigned fb_w, unsigned fb_h,
                     const uint8_t *blob, size_t len)
{
    if (len < HERO_SPLASH_HDR || blob[0] != 'H' || blob[1] != 'S' || blob[2] != 'P' || blob[3] != 'L')
        return -1;
    unsigned w = u16(blob + 4), h = u16(blob + 6), flags = u16(blob + 8);
    uint32_t plen = u32(blob + 12);
    if (!w || !h || w > fb_w || h > fb_h || (flags & ~1U) || plen > len - HERO_SPLASH_HDR)
        return -2;
    if (!(flags & 1U) && plen != (uint32_t)w * h * 2U)
        return -3;
    unsigned sx = fb_w / w, sy = fb_h / h;
    unsigned scale = sx < sy ? sx : sy;          /* same factor in both axes: no distortion */
    unsigned offx = (fb_w - w * scale) / 2U, offy = (fb_h - h * scale) / 2U;

    struct rd s = { blob + HERO_SPLASH_HDR, blob + HERO_SPLASH_HDR + plen, 0, 0, 0, (int)(flags & 1U), 0 };
    for (unsigned y = 0; y < fb_h; ++y) {
        volatile uint32_t *row = fb + (size_t)y * fb_w;
        if (y < offy || y >= offy + h * scale) {
            for (unsigned x = 0; x < fb_w; ++x)
                row[x] = 0xff000000U;
        } else if ((y - offy) % scale == 0) {     /* first line of a source row: decode it */
            unsigned x = 0;
            for (; x < offx; ++x)
                row[x] = 0xff000000U;
            for (unsigned i = 0; i < w; ++i) {
                uint32_t px = argb(next(&s));
                for (unsigned k = 0; k < scale; ++k)
                    row[x++] = px;
            }
            for (; x < fb_w; ++x)
                row[x] = 0xff000000U;
        } else {                                   /* repeat the line above */
            volatile uint32_t *prev = row - fb_w;
            for (unsigned x = 0; x < fb_w; ++x)
                row[x] = prev[x];
        }
        if (s.bad)
            return -4;
    }
    return 0;
}
