/*
 * First OpenGL on the S7's Mali-T880: OSMesa with the Panfrost screen
 * (gpu/mesa/hero_hw.c) renders a cleared frame with a triangle into memory,
 * checks pixels and times a few hundred frames. Results go to the kernel
 * log through the libdrm stand-in (herodrm_log), like herogpu-test.
 *
 * It runs as the drop zone's autorun, with the Mesa dylibs next to it in
 * /private/var/herolte/lib (rpath). HERO_GPU=0 compares with softpipe.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#include <GL/osmesa.h>

void herodrm_log(const char *fmt, ...);

#define W 256
#define H 256
#define ERR_PATH "/private/var/herolte/osmesa-test.err"

typedef void (*PFN_V)(void);
typedef void (*PFN_E)(unsigned);
typedef void (*PFN_4F)(float, float, float, float);
typedef void (*PFN_3F)(float, float, float);
typedef void (*PFN_2F)(float, float);
typedef void (*PFN_4I)(int, int, int, int);
typedef const unsigned char *(*PFN_STR)(unsigned);
typedef unsigned (*PFN_ERR)(void);

static PFN_V glFinish_, glEnd_;
static PFN_E glClear_, glBegin_;
static PFN_4F glClearColor_;
static PFN_3F glColor3f_;
static PFN_2F glVertex2f_;
static PFN_4I glViewport_;
static PFN_STR glGetString_;
static PFN_ERR glGetError_;

static double
now_ms(void)
{
   struct timespec ts;
   clock_gettime(CLOCK_MONOTONIC, &ts);
   return ts.tv_sec * 1e3 + ts.tv_nsec / 1e6;
}

static void
frame(float t)
{
   glClearColor_(0.125f, 0.25f, 0.75f, 1.0f);
   glClear_(0x4000 /* GL_COLOR_BUFFER_BIT */);
   glBegin_(0x0004 /* GL_TRIANGLES */);
   glColor3f_(1.0f, 0.0f, 0.0f);
   glVertex2f_(-0.5f + t, -0.5f);
   glColor3f_(1.0f, 0.0f, 0.0f);
   glVertex2f_(0.5f + t, -0.5f);
   glColor3f_(1.0f, 0.0f, 0.0f);
   glVertex2f_(0.0f + t, 0.5f);
   glEnd_();
}

/* stderr (Mesa's own messages) went to a file; put its lines in the log. */
static void
flush_stderr(void)
{
   fflush(stderr);
   if (!freopen("/dev/null", "w", stderr))
      return;
   FILE *f = fopen(ERR_PATH, "r");
   if (!f)
      return;
   char line[512];
   for (int n = 0; n < 60 && fgets(line, sizeof(line), f); n++) {
      line[strcspn(line, "\n")] = 0;
      if (strncmp(line, "herodrm: ", 9) != 0)   /* already logged */
         herodrm_log("stderr: %s", line);
   }
   fclose(f);
}

#define LOAD(var, name) \
   var = (__typeof__(var))OSMesaGetProcAddress(name); \
   if (!var) { herodrm_log("no %s", name); goto out; }

int
main(void)
{
   sleep(20);
   freopen(ERR_PATH, "w", stderr);
   setenv("MESA_DEBUG", "1", 0);
   herodrm_log("osmesa-test: start, HERO_GPU=%s", getenv("HERO_GPU") ? getenv("HERO_GPU") : "(unset)");

   uint32_t *buf = calloc(W * H, 4);
   double t0 = now_ms();
   OSMesaContext ctx = OSMesaCreateContextExt(OSMESA_RGBA, 0, 0, 0, NULL);
   if (!ctx) {
      herodrm_log("OSMesaCreateContextExt failed");
      goto out;
   }
   if (!OSMesaMakeCurrent(ctx, buf, 0x1401 /* GL_UNSIGNED_BYTE */, W, H)) {
      herodrm_log("OSMesaMakeCurrent failed");
      goto out;
   }
   herodrm_log("context in %.1f ms", now_ms() - t0);

   LOAD(glFinish_, "glFinish");
   LOAD(glEnd_, "glEnd");
   LOAD(glClear_, "glClear");
   LOAD(glBegin_, "glBegin");
   LOAD(glClearColor_, "glClearColor");
   LOAD(glColor3f_, "glColor3f");
   LOAD(glVertex2f_, "glVertex2f");
   LOAD(glViewport_, "glViewport");
   LOAD(glGetString_, "glGetString");
   LOAD(glGetError_, "glGetError");

   herodrm_log("GL_RENDERER = %s", glGetString_(0x1F01));
   herodrm_log("GL_VERSION = %s", glGetString_(0x1F02));

   glViewport_(0, 0, W, H);
   t0 = now_ms();
   frame(0.0f);
   glFinish_();
   herodrm_log("first frame in %.1f ms (shader compiles included), GL error 0x%x",
               now_ms() - t0, glGetError_());

   /* OSMesa's buffer is bottom-up; RGBA bytes, so 0xAABBGGRR words. */
   uint32_t center = buf[(H / 2) * W + W / 2], corner = buf[2 * W + 2];
   int red = 0, blue = 0;
   for (int i = 0; i < W * H; i++) {
      unsigned r = buf[i] & 0xff, g = (buf[i] >> 8) & 0xff, b = (buf[i] >> 16) & 0xff;
      red += r > 200 && g < 40 && b < 40;
      blue += b > 150 && r < 60;
   }
   /* The triangle (base 128 px, height 128 px) covers 8192 pixels. */
   herodrm_log("pixels: center 0x%08x (red 0xff0000ff), corner 0x%08x (blue ~0xffbf4020), "
               "%d red, %d blue of %d -> %s",
               center, corner, red, blue, W * H,
               red > 7900 && red < 8500 && red + blue == W * H ? "OK" : "WRONG");

   const int n = 300;
   t0 = now_ms();
   for (int i = 0; i < n; i++) {
      frame((i % 50) / 100.0f);
      glFinish_();
   }
   double ms = now_ms() - t0;
   herodrm_log("%d frames %dx%d with glFinish: %.1f ms, %.2f ms/frame (%.0f fps)",
               n, W, H, ms, ms / n, n * 1000.0 / ms);

   OSMesaDestroyContext(ctx);
out:
   flush_stderr();
   herodrm_log("osmesa-test: done");
   return 0;
}
