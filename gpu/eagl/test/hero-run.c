/*
 * Drop-zone autorun for any test program: waits for the UI to settle, runs
 * /private/var/herolte/test with the KEY=VALUE lines of
 * /private/var/herolte/test.env added to its environment, and puts its
 * stdout and stderr into the kernel log (through the libdrm stand-in's
 * herodrm_log), since TWRP cannot read the iOS volume. The test is killed
 * after 180 s.
 */
#include <dirent.h>
#include <dlfcn.h>
#include <fcntl.h>
#include <objc/message.h>
extern void *objc_autoreleasePoolPush(void);
extern void objc_autoreleasePoolPop(void *pool);
extern void NSSetUncaughtExceptionHandler(void (*handler)(id));
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

/* A forked child has no mach ports, so no log of its own: it writes here and the parent logs it. */
static int census_fd = -1;

static id
send0(id target, const char *selector)
{
   return ((id (*)(id, SEL))objc_msgSend)(target, sel_registerName(selector));
}

/* What LaunchServices knows of the plug-ins the wallpaper and the widgets need. */
static void
plugins_census(id workspace)
{
   id plugins = send0(workspace, "installedPlugins");
   size_t count = plugins ? ((size_t (*)(id, SEL))objc_msgSend)(plugins, sel_registerName("count")) : 0;
   dprintf(census_fd, "plug-ins known: %zu\n", count);
   /* That list may be only what this process may see: ask for the poster extensions by name too. */
   static const char *const posters[] = {
      "com.apple.WallpaperKit.CollectionsPoster",
      "com.apple.GradientPoster.GradientPosterExtension",
      "com.apple.PhotosUIPrivate.PhotosPosterProvider",
   };
   Class proxies = objc_getClass("LSPlugInKitProxy");
   for (size_t i = 0; proxies && i < sizeof(posters) / sizeof(posters[0]); i++) {
      id proxy = ((id (*)(id, SEL, id))objc_msgSend)((id)proxies, sel_registerName("pluginKitProxyForIdentifier:"),
         nsstring(posters[i]));
      dprintf(census_fd, "proxy %s: %s\n", posters[i], text_of(proxy));
   }
   for (size_t i = 0; i < count; i++) {
      id plugin = ((id (*)(id, SEL, size_t))objc_msgSend)(plugins, sel_registerName("objectAtIndex:"), i);
      const char *name = text_of(send0(plugin, "bundleIdentifier"));
      if (strstr(name, "oster") || strstr(name, "idget"))
         dprintf(census_fd, "plug-in %s\n", name);
   }
}

/*
 * iOS's own log says why PosterBoard shows nothing and why the widgets wait, and TWRP cannot read it. As root, late
 * in the boot, the lines of those processes (and any on the subject) go into the census.
 */
static void
log_census_exception(id exception)
{
   dprintf(census_fd, "log reader: exception %s\n", text_of(exception));
   _exit(0);
}

static void
log_census(void)
{
   enum { MAX_LOG_LINES = 250, MAX_SECONDS = 90 };
   alarm(280);
   sleep(170);
   NSSetUncaughtExceptionHandler(log_census_exception);
   dlopen("/System/Library/Frameworks/OSLog.framework/OSLog", RTLD_NOW);
   Class stores = objc_getClass("OSLogStore");
   id error = nil;
   id store = stores ? send_id((id)stores, "localStoreAndReturnError:", (id)&error, NULL) : nil;
   dprintf(census_fd, "log store %s; error %s\n", text_of(store), text_of(error));
   id entries = store ? send_id(store, "entriesEnumeratorAndReturnError:", (id)&error, NULL) : nil;
   time_t start = time(NULL);
   int lines = 0;
   id entry;
   SEL has = sel_registerName("respondsToSelector:");
   while (entries && lines < MAX_LOG_LINES && time(NULL) - start < MAX_SECONDS) {
      void *pool = objc_autoreleasePoolPush();
      entry = send0(entries, "nextObject");
      if (!entry) {
         objc_autoreleasePoolPop(pool);
         break;
      }
      if (((BOOL (*)(id, SEL, SEL))objc_msgSend)(entry, has, sel_registerName("process"))) {
         const char *process = text_of(send0(entry, "process"));
         const char *message = text_of(send0(entry, "composedMessage"));
         int wanted = strcmp(process, "PosterBoard") == 0 || strcmp(process, "chronod") == 0;
         int subject = strstr(message, "oster") || strstr(message, "idget") || strstr(message, "xtension");
         int failing = strstr(message, "rror") || strstr(message, "ail") || strstr(message, "denied") || strstr(message, "not ");
         if ((wanted && failing) || (subject && failing)) {
            dprintf(census_fd, "log %s: %.240s\n", process, message);
            lines++;
         }
      }
      objc_autoreleasePoolPop(pool);
   }
   dprintf(census_fd, "log: %d lines, %ld s; error %s\n", lines, (long)(time(NULL) - start), text_of(error));
}

/*
 * LaunchServices answers -10814 (not found) for the poster extensions: the plug-ins inside the system's frameworks
 * are not registered, and PosterBoard has nothing to offer or to draw. On a phone that comes with DataMigration,
 * which this image skips. Each one is registered by its URL, once; the wallpaper needs the next boot to see them.
 */
static int
register_plugins_in(id workspace, const char *frameworks)
{
   int done = 0;
   DIR *all = opendir(frameworks);
   struct dirent *f, *p;
   while (all && (f = readdir(all))) {
      char dir[1024];
      snprintf(dir, sizeof(dir), "%s/%s/PlugIns", frameworks, f->d_name);
      DIR *plugins = opendir(dir);
      while (plugins && (p = readdir(plugins))) {
         char path[2048];
         size_t n = strlen(p->d_name);
         if (n < 6 || strcmp(p->d_name + n - 6, ".appex") != 0)
            continue;
         snprintf(path, sizeof(path), "%s/%s", dir, p->d_name);
         void *pool = objc_autoreleasePoolPush();
         id url = ((id (*)(id, SEL, id))objc_msgSend)((id)objc_getClass("NSURL"), sel_registerName("fileURLWithPath:"),
            nsstring(path));
         BOOL ok = ((BOOL (*)(id, SEL, id))objc_msgSend)(workspace, sel_registerName("registerPlugin:"), url);
         done += ok;
         if (!ok || strstr(p->d_name, "Poster"))
            dprintf(census_fd, "register %s: %d\n", p->d_name, ok);
         objc_autoreleasePoolPop(pool);
      }
      if (plugins)
         closedir(plugins);
   }
   if (all)
      closedir(all);
   return done;
}

static void
register_system_plugins(id workspace)
{
   int done = register_plugins_in(workspace, "/System/Library/PrivateFrameworks") +
      register_plugins_in(workspace, "/System/Library/Frameworks");
   dprintf(census_fd, "plug-ins registered: %d\n", done);
   BOOL synced = ((BOOL (*)(id, SEL))objc_msgSend)(workspace, sel_registerName("_LSPrivateSyncWithMobileInstallation"));
   dprintf(census_fd, "sync with installd: %d\n", synced);
}

static void
extension_census(void)
{
   static const char *const known[] = {
      "com.apple.WallpaperKit.CollectionsPoster",
      "com.apple.GradientPoster.GradientPosterExtension",
      "com.apple.PhotosUIPrivate.PhotosPosterProvider",
   };
   pid_t reader = fork();
   if (reader == 0) {
      log_census();
      _exit(0);
   }
   /* LaunchServices is told once of the system's bundles: DataMigration, which does it on a real phone, is skipped
    * on this image (herolte-tune-ios-root.sh). The parent marks it done when this child has lived through it. */
   int first_time = access(DROP_DIR "database.done", F_OK) != 0;
   alarm(300);
   sleep(60);
   if (setgid(501) != 0 || setuid(501) != 0)
      dprintf(census_fd, "cannot become mobile\n");
   dlopen("/System/Library/Frameworks/CoreServices.framework/CoreServices", RTLD_NOW);
   id workspace = objc_getClass("LSApplicationWorkspace") ?
      ((id (*)(id, SEL))objc_msgSend)((id)objc_getClass("LSApplicationWorkspace"), sel_registerName("defaultWorkspace")) : nil;
   dprintf(census_fd, "workspace %s; first time %d\n", text_of(workspace), first_time);
   if (workspace && first_time) {
      BOOL rebuilt = ((BOOL (*)(id, SEL, BOOL, BOOL, BOOL))objc_msgSend)(workspace,
         sel_registerName("_LSPrivateRebuildApplicationDatabasesForSystemApps:internal:user:"), YES, YES, YES);
      dprintf(census_fd, "database rebuilt: %d\n", rebuilt);
   }
   if (workspace && access(DROP_DIR "plugins.done", F_OK) != 0)
      register_system_plugins(workspace);
   Class records = objc_getClass("LSApplicationExtensionRecord");
   for (size_t i = 0; records && i < sizeof(known) / sizeof(known[0]); i++) {
      id error = nil;
      id record = send_id(((id (*)(id, SEL))objc_msgSend)((id)records, sel_registerName("alloc")),
         "initWithBundleIdentifier:error:", nsstring(known[i]), &error);
      dprintf(census_fd, "record %s: %s; error %s\n", known[i], text_of(record), text_of(error));
   }
   id attributes = ((id (*)(id, SEL, id, id))objc_msgSend)((id)objc_getClass("NSDictionary"),
      sel_registerName("dictionaryWithObject:forKey:"), nsstring("com.apple.posterkit.provider"),
      nsstring("NSExtensionPointName"));
   id error = nil;
   id found = send_id((id)objc_getClass("NSExtension"), "extensionsWithMatchingAttributes:error:", attributes, &error);
   dprintf(census_fd, "of the poster point: %s; error %s\n", text_of(found), text_of(error));
   if (workspace)
      plugins_census(workspace);
   if (reader > 0)
      waitpid(reader, NULL, 0);
}

/* The complete lines the child has written since the last call go to the log. */
static void
census_drain(void)
{
   static off_t done;
   char text[8192];
   ssize_t n = pread(census_fd, text, sizeof(text) - 1, done);
   if (n <= 0)
      return;
   text[n] = 0;
   char *line = text, *end;
   while ((end = strchr(line, '\n'))) {
      *end = 0;
      herodrm_log("hero-run: extensions: %s", line);
      done += (end - line) + 1;
      line = end + 1;
   }
}

int
main(void)
{
   wallpapers_for_this_screen();
   census_fd = open(DROP_DIR "census.out", O_RDWR | O_CREAT | O_TRUNC, 0644);
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
   if (census > 0) {
      /* Line by line as they come: the phone may go to TWRP before the child ends. */
      int census_status = 0;
      pid_t ended = 0;
      while (ended == 0) {
         ended = waitpid(census, &census_status, WNOHANG);
         census_drain();
         if (ended == 0)
            sleep(3);
      }
      census_drain();
      herodrm_log("hero-run: extensions: the child ended with status %#x", census_status);
      if (WIFEXITED(census_status) && WEXITSTATUS(census_status) == 0) {
         close(open(DROP_DIR "database.done", O_WRONLY | O_CREAT, 0644));
         close(open(DROP_DIR "plugins.done", O_WRONLY | O_CREAT, 0644));
      }
   }
   return 0;
}
