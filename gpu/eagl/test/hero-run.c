/*
 * Drop-zone autorun for any test program: waits for the UI to settle, runs
 * /private/var/herolte/test with the KEY=VALUE lines of
 * /private/var/herolte/test.env added to its environment, and puts its
 * stdout and stderr into the kernel log (through the libdrm stand-in's
 * herodrm_log), since TWRP cannot read the iOS volume. The test is killed
 * after 180 s.
 */
#include <dirent.h>
#include <fcntl.h>
#include <objc/message.h>
#include <objc/runtime.h>
#include <signal.h>
#include <spawn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#define DROP_DIR "/private/var/herolte/"
#define OUT DROP_DIR "test.out"
#define MAX_LINES 400

extern char **environ;
void herodrm_log(const char *fmt, ...);

static void
load_env(void)
{
   FILE *f = fopen(DROP_DIR "test.env", "r");
   char line[512];
   while (f && fgets(line, sizeof(line), f)) {
      line[strcspn(line, "\r\n")] = 0;
      char *eq = strchr(line, '=');
      if (line[0] == '#' || !eq)
         continue;
      *eq = 0;
      setenv(line, eq + 1, 1);
      herodrm_log("hero-run: %s=%s", line, eq + 1);
   }
   if (f)
      fclose(f);
}

/*
 * WallpaperKit keeps only the wallpapers whose Wallpaper.plist names this
 * screen's class. Ours is 480w-853h@3x~iphone (1440x2560 at scale 3) and the
 * image has 375w-812h, 393w-852h and 430w-932h: none is offered and PosterBoard
 * has nothing to draw. The 375w-812h bundles are given our class, in place:
 * the two names have the same length, so the plist's offsets still hold.
 */
#define SCREEN_FROM "375w-812h@3x~iphone"
#define SCREEN_TO   "480w-853h@3x~iphone"
#define COLLECTIONS "/Library/Wallpaper/Collections"

static int
wallpaper_class_set(const char *path)
{
   char data[65536];
   int fd = open(path, O_RDWR);
   if (fd < 0)
      return 0;
   ssize_t n = read(fd, data, sizeof(data));
   int done = 0;
   for (ssize_t i = 0; i + (ssize_t)strlen(SCREEN_FROM) <= n; i++) {
      if (memcmp(data + i, SCREEN_FROM, strlen(SCREEN_FROM)) == 0 &&
          pwrite(fd, SCREEN_TO, strlen(SCREEN_TO), i) == (ssize_t)strlen(SCREEN_TO))
         done++;
   }
   if (done)
      fsync(fd);
   close(fd);
   return done;
}

static void
wallpapers_for_this_screen(void)
{
   int bundles = 0, changed = 0;
   DIR *collections = opendir(COLLECTIONS);
   struct dirent *c, *w;
   while (collections && (c = readdir(collections))) {
      char path[1024];
      snprintf(path, sizeof(path), COLLECTIONS "/%s/Wallpapers", c->d_name);
      DIR *wallpapers = opendir(path);
      while (wallpapers && (w = readdir(wallpapers))) {
         char plist[2048];
         if (!strstr(w->d_name, "375w-812h"))
            continue;
         snprintf(plist, sizeof(plist), "%s/%s/Wallpaper.plist", path, w->d_name);
         bundles++;
         changed += wallpaper_class_set(plist) > 0;
         if (bundles == 1) {
            /* Is it ours by now (from this boot or an earlier one)? */
            char text[65536];
            int fd = open(plist, O_RDONLY);
            ssize_t n = fd >= 0 ? read(fd, text, sizeof(text)) : -1;
            int ours = n > 0 && memmem(text, (size_t)n, SCREEN_TO, strlen(SCREEN_TO)) != NULL;
            if (fd >= 0)
               close(fd);
            herodrm_log("hero-run: wallpapers: %s: %zd bytes, %s", w->d_name, n, ours ? "has our class" : "does not have our class");
         }
      }
      if (wallpapers)
         closedir(wallpapers);
   }
   if (collections)
      closedir(collections);
   herodrm_log("hero-run: wallpapers: %d bundles of 375w-812h, %d given our class now", bundles, changed);
}

/*
 * The "Add New Wallpaper" gallery is empty and no poster extension is ever
 * launched. A child running as mobile, as PosterBoard does, asks the system
 * which extensions of that point it knows, 60 s after boot, into the log.
 */
static id
send_id(id target, const char *selector, id a, void *b)
{
   return ((id (*)(id, SEL, id, void *))objc_msgSend)(target, sel_registerName(selector), a, b);
}

static id
nsstring(const char *text)
{
   return ((id (*)(id, SEL, const char *))objc_msgSend)((id)objc_getClass("NSString"),
      sel_registerName("stringWithUTF8String:"), text);
}

static const char *
text_of(id object)
{
   if (!object)
      return "(nil)";
   id description = ((id (*)(id, SEL))objc_msgSend)(object, sel_registerName("description"));
   return ((const char *(*)(id, SEL))objc_msgSend)(description, sel_registerName("UTF8String"));
}

static void
extension_census(void)
{
   static const char *const known[] = {
      "com.apple.WallpaperKit.CollectionsPoster",
      "com.apple.GradientPoster.GradientPosterExtension",
      "com.apple.PhotosUIPrivate.PhotosPosterProvider",
   };
   alarm(120);
   sleep(60);
   if (setgid(501) != 0 || setuid(501) != 0)
      herodrm_log("hero-run: extensions: cannot become mobile");
   Class records = objc_getClass("LSApplicationExtensionRecord");
   for (size_t i = 0; records && i < sizeof(known) / sizeof(known[0]); i++) {
      id error = nil;
      id record = send_id(((id (*)(id, SEL))objc_msgSend)((id)records, sel_registerName("alloc")),
         "initWithBundleIdentifier:error:", nsstring(known[i]), &error);
      herodrm_log("hero-run: extensions: record %s: %s; error %s", known[i], text_of(record), text_of(error));
   }
   id attributes = ((id (*)(id, SEL, id, id))objc_msgSend)((id)objc_getClass("NSDictionary"),
      sel_registerName("dictionaryWithObject:forKey:"), nsstring("com.apple.posterkit.provider"),
      nsstring("NSExtensionPointName"));
   id error = nil;
   id found = send_id((id)objc_getClass("NSExtension"), "extensionsWithMatchingAttributes:error:", attributes, &error);
   herodrm_log("hero-run: extensions: of the poster point: %s; error %s", text_of(found), text_of(error));
}

int
main(void)
{
   wallpapers_for_this_screen();
   pid_t census = fork();
   if (census == 0) {
      extension_census();
      _exit(0);
   }
   sleep(20);
   load_env();
   posix_spawn_file_actions_t fa;
   posix_spawn_file_actions_init(&fa);
   posix_spawn_file_actions_addopen(&fa, 1, OUT, O_WRONLY | O_CREAT | O_TRUNC, 0644);
   posix_spawn_file_actions_adddup2(&fa, 1, 2);
   char *argv[] = { DROP_DIR "test", NULL };
   pid_t pid;
   struct timespec t0, t1;
   clock_gettime(CLOCK_MONOTONIC, &t0);
   int err = posix_spawn(&pid, argv[0], &fa, NULL, argv, environ);
   if (err) {
      herodrm_log("hero-run: spawn %s: error %d", argv[0], err);
      return 1;
   }
   herodrm_log("hero-run: test started, pid %d", pid);
   int status = 0;
   for (int i = 0; i < 1800; i++) {
      if (waitpid(pid, &status, WNOHANG) == pid)
         break;
      if (i == 1799) {
         herodrm_log("hero-run: test still running after 180 s, killing it");
         kill(pid, SIGKILL);
         waitpid(pid, &status, 0);
      }
      usleep(100000);
   }
   clock_gettime(CLOCK_MONOTONIC, &t1);

   FILE *f = fopen(OUT, "r");
   char line[700];
   int n = 0;
   while (f && fgets(line, sizeof(line), f) && n < MAX_LINES) {
      line[strcspn(line, "\n")] = 0;
      if (strncmp(line, "herodrm: ", 9) == 0)     /* already in the log */
         continue;
      herodrm_log("| %s", line);
      n++;
   }
   if (f)
      fclose(f);
   if (WIFSIGNALED(status))
      herodrm_log("hero-run: test killed by signal %d after %.1f s", WTERMSIG(status),
                  (t1.tv_sec - t0.tv_sec) + (t1.tv_nsec - t0.tv_nsec) / 1e9);
   else
      herodrm_log("hero-run: test exited with %d after %.1f s", WEXITSTATUS(status),
                  (t1.tv_sec - t0.tv_sec) + (t1.tv_nsec - t0.tv_nsec) / 1e9);
   if (census > 0)
      waitpid(census, NULL, 0);
   return 0;
}
