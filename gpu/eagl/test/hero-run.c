/*
 * Drop-zone autorun for any test program: waits for the UI to settle, runs
 * /private/var/herolte/test with the KEY=VALUE lines of
 * /private/var/herolte/test.env added to its environment, and puts its
 * stdout and stderr into the kernel log (through the libdrm stand-in's
 * herodrm_log), since TWRP cannot read the iOS volume. The test is killed
 * after 180 s.
 */
#include <CoreFoundation/CoreFoundation.h>
#include <dirent.h>
#include <sys/stat.h>
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
 * LaunchServices never hears of the poster extensions, which live inside frameworks: it is told of each by hand, once,
 * as root. And a wallpaper of the old kind asked of SpringBoard, which needs no poster at all.
 */
#define POSTERS_TOLD DROP_DIR "posters3.done"

static void
tell_ls_of_posters(void)
{
   static const char *const appex[] = {
      "/System/Library/PrivateFrameworks/WallpaperKit.framework/PlugIns/CollectionsPoster.appex",
      "/System/Library/PrivateFrameworks/GradientPoster.framework/PlugIns/GradientPosterExtension.appex",
      "/System/Library/PrivateFrameworks/PhotosUIPrivate.framework/PlugIns/PhotosPosterProvider.appex",
      "/System/Library/PrivateFrameworks/EmojiPoster.framework/PlugIns/EmojiPosterExtension.appex",
      "/System/Library/PrivateFrameworks/UnityPoster.framework/PlugIns/UnityPosterExtension.appex",
      "/System/Library/PrivateFrameworks/PridePoster.framework/PlugIns/PridePosterExtension.appex",
      "/Applications/Weather.app/PlugIns/WeatherPoster.appex",
   };
   if (access(POSTERS_TOLD, F_OK) == 0)
      return;
   close(open(POSTERS_TOLD, O_WRONLY | O_CREAT, 0644));
   int (*lsregister)(id, unsigned char) = (int (*)(id, unsigned char))dlsym(RTLD_DEFAULT, "LSRegisterURL");
   if (!lsregister) {
      dprintf(census_fd, "LSRegisterURL: not there\n");
      return;
   }
   for (size_t i = 0; i < sizeof(appex) / sizeof(appex[0]); i++) {
      id url = send_id((id)objc_getClass("NSURL"), "fileURLWithPath:", nsstring(appex[i]), NULL);
      time_t start = time(NULL);
      int status = lsregister(url, 1);
      dprintf(census_fd, "LSRegisterURL %s: %d, %ld s\n", appex[i], status, (long)(time(NULL) - start));
   }
}

static void
ask_for_old_wallpaper(void)
{
   static const char *const image_path =
      "/Library/Wallpaper/Collections/Clownfish~iphone.wallpaperCollection/Wallpapers/"
      "7420.Clownfish-375w-812h@3x~iphone.wallpaper/7420.Clownfish_Background-375w-812h@3x~iphone.ca/assets/Background.HEIC";
   dlopen("/System/Library/Frameworks/UIKit.framework/UIKit", RTLD_NOW);
   dlopen("/System/Library/PrivateFrameworks/SpringBoardUIServices.framework/SpringBoardUIServices", RTLD_NOW);
   int (*set_images)(id, id, int, int) = (int (*)(id, id, int, int))dlsym(RTLD_DEFAULT, "SBSUIWallpaperSetImages");
   id image = objc_getClass("UIImage") ? send_id((id)objc_getClass("UIImage"), "imageWithContentsOfFile:", nsstring(image_path), NULL) : nil;
   dprintf(census_fd, "old wallpaper: function %d, image %s\n", set_images != NULL, text_of(image));
   if (!set_images || !image)
      return;
   id images = ((id (*)(id, SEL, id, id))objc_msgSend)((id)objc_getClass("NSDictionary"),
      sel_registerName("dictionaryWithObject:forKey:"), image, nsstring("light"));
   id options = send0((id)objc_getClass("NSDictionary"), "dictionary");
   dprintf(census_fd, "old wallpaper: asked, answer %d\n", set_images(images, options, 3, 0));
}

static void run_ls_migrator(void);
static void
extension_census(void)
{
   static const char *const known[] = {
      "com.apple.WallpaperKit.CollectionsPoster",
      "com.apple.GradientPoster.GradientPosterExtension",
      "com.apple.PhotosUIPrivate.PhotosPosterProvider",
   };
   /* LaunchServices is told once of the system's bundles: DataMigration, which does it on a real phone, is skipped
    * on this image (herolte-tune-ios-root.sh). The parent marks it done when this child has lived through it.
    * Done again since the kernel answers AMFI's request 0x60: only now does LaunchServices know the extension points. */
   int first_time = access(DROP_DIR "database2.done", F_OK) != 0;
   alarm(0);
   sleep(60);
   run_ls_migrator();
   alarm(300);
   dlopen("/System/Library/Frameworks/CoreServices.framework/CoreServices", RTLD_NOW);
   tell_ls_of_posters();
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
   ask_for_old_wallpaper();
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

/*
 * The whole of DataMigration does not finish here: datamigrator waits on its plug-in wrapper, for good. So its plist
 * stays as the image has it (put back first thing, before launchd gets to the migration), and of its plug-ins only
 * the one that tells LaunchServices about the system runs, once, in this process.
 */
#define MIGRATION_PLIST "/private/var/mobile/Library/Preferences/com.apple.migration.plist"
#define MIGRATION_SAVED DROP_DIR "migration.saved"
#define LS_MIGRATOR     "/System/Library/DataClassMigrators/00LaunchServicesMigrator.migrator"
#define LS_MIGRATED     DROP_DIR "lsmigrator2.done"
#define LS_ANSWER       DROP_DIR "lsmigrator.log"

static void
migration_restore(void)
{
   if (access(MIGRATION_SAVED, F_OK) == 0)
      herodrm_log("hero-run: migration: plist put back (%d)", rename(MIGRATION_SAVED, MIGRATION_PLIST));
   herodrm_log("hero-run: migration: plist %s", access(MIGRATION_PLIST, F_OK) == 0 ? "present" : "MISSING");
}

/*
 * The services heronoexec refuses are relaunched by launchd every ten seconds for ever, and each try costs a good
 * part of a CPU (kernel_task and xpcproxy at 100% and more). launchd's own list of disabled jobs stops that from the
 * next boot on. DROP_DIR disabled.list, one job a line, adds to them with no new build: 41 at once left SpringBoard
 * waiting for ever behind a black screen, so which ones are safe is found by trying.
 */
static void
disable_refused_jobs(void)
{
   static const char *const jobs[] = {
      "com.apple.bluetoothd", "com.apple.ReportCrash", "com.apple.analyticsd", "com.apple.aggregated",
      "com.apple.homed", "com.apple.cloudd", "com.apple.searchd", "com.apple.voicemail.vmd",
   };
   size_t count = sizeof(jobs) / sizeof(jobs[0]);
   mkdir("/private/var/db/com.apple.xpc.launchd", 0755);
   FILE *f = fopen("/private/var/db/com.apple.xpc.launchd/disabled.plist", "w");
   if (!f) {
      herodrm_log("hero-run: cannot write launchd's disabled jobs");
      return;
   }
   fputs("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<plist version=\"1.0\">\n<dict>\n", f);
   for (size_t i = 0; i < count; i++)
      fprintf(f, "\t<key>%s</key>\n\t<true/>\n", jobs[i]);
   FILE *extra = fopen(DROP_DIR "disabled.list", "r");
   char job[256];
   while (extra && fgets(job, sizeof(job), extra)) {
      job[strcspn(job, " \t\r\n")] = 0;
      if (job[0] && job[0] != '#') {
         fprintf(f, "\t<key>%s</key>\n\t<true/>\n", job);
         count++;
      }
   }
   if (extra)
      fclose(extra);
   fputs("</dict>\n</plist>\n", f);
   fclose(f);
   herodrm_log("hero-run: %zu jobs in launchd's disabled list", count);
}

/* In the census child, as root, before it becomes mobile. */
static void
run_ls_migrator(void)
{
   char said[1024];
   int old = open(LS_ANSWER, O_RDONLY);
   ssize_t got = old >= 0 ? read(old, said, sizeof(said) - 1) : 0;
   if (old >= 0)
      close(old);
   if (got > 0) {
      said[got] = 0;
      dprintf(census_fd, "LS migrator, last time:\n%s", said);
   }
   if (access(LS_MIGRATED, F_OK) == 0)
      return;
   close(open(LS_MIGRATED, O_WRONLY | O_CREAT, 0644));
   int answer = open(LS_ANSWER, O_WRONLY | O_CREAT | O_TRUNC, 0644);
   id bundle = ((id (*)(id, SEL, id))objc_msgSend)((id)objc_getClass("NSBundle"), sel_registerName("bundleWithPath:"),
      nsstring(LS_MIGRATOR));
   BOOL loaded = bundle ? ((BOOL (*)(id, SEL))objc_msgSend)(bundle, sel_registerName("load")) : NO;
   id cls = bundle ? send0(bundle, "principalClass") : nil;
   dprintf(census_fd, "LS migrator: bundle %s, loaded %d, class %s\n", text_of(bundle), loaded, text_of(cls));
   dprintf(answer, "LS migrator: bundle %s, loaded %d, class %s\n", text_of(bundle), loaded, text_of(cls));
   if (!cls)
      return;
   id migrator = send0(send0(cls, "alloc"), "init");
   time_t start = time(NULL);
   BOOL done = ((BOOL (*)(id, SEL))objc_msgSend)(migrator, sel_registerName("performMigration"));
   dprintf(census_fd, "LS migrator: performMigration %d, %ld s\n", done, (long)(time(NULL) - start));
   dprintf(answer, "LS migrator: performMigration %d, %ld s\n", done, (long)(time(NULL) - start));
}

/*
 * LaunchServices builds its database by walking the system when it finds none: HakiOS has an empty /private/var at
 * every boot and its posters are there. Ours keeps the first one, which has none of them. Once, it goes: the next
 * start of lsd makes it anew. Nothing says where it lives on this root, so all of /private/var is looked through.
 */
#define LS_DB_GONE DROP_DIR "lsdb2.gone"

static int
remove_ls_db_in(const char *dir, int depth)
{
   int removed = 0;
   DIR *d = opendir(dir);
   struct dirent *e;
   while (d && (e = readdir(d))) {
      char path[1024];
      struct stat st;
      if (e->d_name[0] == '.' && (e->d_name[1] == 0 || e->d_name[1] == '.'))
         continue;
      snprintf(path, sizeof(path), "%s/%s", dir, e->d_name);
      if (strstr(e->d_name, ".csstore")) {
         int gone = unlink(path);
         herodrm_log("hero-run: LS database %s: removed (%d)", path, gone);
         removed += gone == 0;
      } else if (depth > 0 && strcmp(path, "/private/var/herolte") && lstat(path, &st) == 0 && S_ISDIR(st.st_mode)) {
         removed += remove_ls_db_in(path, depth - 1);
      }
   }
   if (d)
      closedir(d);
   return removed;
}

static void
remove_ls_db_once(void)
{
   if (access(LS_DB_GONE, F_OK) == 0)
      return;
   close(open(LS_DB_GONE, O_WRONLY | O_CREAT, 0644));
   time_t start = time(NULL);
   int removed = remove_ls_db_in("/private/var", 9);
   herodrm_log("hero-run: LS database: %d files removed in %ld s; the NEXT boot has it made anew", removed,
      (long)(time(NULL) - start));
}

/*
 * BTAudioHALPlugin keeps asking the bluetoothd that heronoexec refuses, over XPC: on the S9 port that was most of
 * launchd's and half of mediaserverd's CPU (idle 460% -> 52% without it). Out of the way, from the next boot on.
 */
static void
disable_bluetooth_audio(void)
{
   const char *from = "/System/Library/Audio/Plug-Ins/HAL/BTAudioHALPlugin.driver";
   if (access(from, F_OK) != 0)
      return;
   mkdir("/System/Library/Audio/Plug-Ins/HAL.disabled", 0755);
   int moved = rename(from, "/System/Library/Audio/Plug-Ins/HAL.disabled/BTAudioHALPlugin.driver");
   herodrm_log("hero-run: BTAudioHALPlugin moved away: %d", moved);
}

/*
 * reduce.transparency in the drop zone: Settings' Reduce Transparency, whose Accessibility page crashes here (CoreImage,
 * from MobileIcons). No blurs, the GPU's heaviest work; SpringBoard reads it at its next start, so from the next boot on.
 */
static void
reduce_transparency(void)
{
   struct stat st;
   if (stat("/private/var/herolte/reduce.transparency", &st) != 0)
      return;
   CFPreferencesSetValue(CFSTR("EnhancedBackgroundContrastEnabled"), kCFBooleanTrue, CFSTR("com.apple.Accessibility"),
                         CFSTR("mobile"), kCFPreferencesAnyHost);
   CFPreferencesSynchronize(CFSTR("com.apple.Accessibility"), CFSTR("mobile"), kCFPreferencesAnyHost);
}

/* The plug-in of the sound (gpu/hakios-audio) where mediaserverd looks: it loads plug-ins as it starts, so from the next boot on. */
static void
copy_audio_file(const char *from, const char *to, mode_t mode)
{
   char buffer[65536];
   ssize_t n;
   int in = open(from, O_RDONLY), out = in >= 0 ? open(to, O_WRONLY | O_CREAT | O_TRUNC, mode) : -1;
   while (out >= 0 && (n = read(in, buffer, sizeof(buffer))) > 0) {
      if (write(out, buffer, (size_t)n) != n)
         break;
   }
   if (out >= 0) {
      fchmod(out, mode);
      close(out);
   }
   if (in >= 0)
      close(in);
   herodrm_log("hero-run: audio plug-in: %s: %s", to, out >= 0 ? "put" : "not put");
}

static void
install_audio_plugin(void)
{
   struct stat from, to;
   const char *driver = "/System/Library/Audio/Plug-Ins/HAL/HakiosAudio.driver/HakiosAudio";
   int have = stat(DROP_DIR "audio/HakiosAudio", &from) == 0, there = stat(driver, &to) == 0;
   herodrm_log("hero-run: audio plug-in: drop zone %lld bytes, HAL %lld bytes", have ? (long long)from.st_size : -1, there ? (long long)to.st_size : -1);
   if (!have || (there && to.st_size == from.st_size && to.st_mtime >= from.st_mtime))
      return;
   mkdir("/System/Library/Audio/Plug-Ins/HAL/HakiosAudio.driver", 0755);
   copy_audio_file(DROP_DIR "audio/HakiosAudio", driver, 0755);
   copy_audio_file(DROP_DIR "audio/Info.plist", "/System/Library/Audio/Plug-Ins/HAL/HakiosAudio.driver/Info.plist", 0644);
}

int
main(void)
{
   disable_bluetooth_audio();
   install_audio_plugin();
   reduce_transparency();
   remove_ls_db_once();
   wallpapers_for_this_screen();
   migration_restore();
   disable_refused_jobs();
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
         close(open(DROP_DIR "database2.done", O_WRONLY | O_CREAT, 0644));
      }
   }
   return 0;
}
