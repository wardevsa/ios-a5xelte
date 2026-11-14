/*
 * hero-oslog: what iOS's own log says, for the kernel's log. Run as hero-run's test (DROP_DIR test): it waits until
 * WAIT seconds after its start, then reads logd's store (OSLogStore, the whole system: hero-run's entitlements
 * com.apple.logging.local-store and com.apple.private.logging.admin) back SPAN seconds and prints the entries of the
 * processes in PROCS whose message matches one of WORDS; hero-run puts its standard output in the log.
 *
 *   environment: HERO_OSLOG_WAIT (default 75), HERO_OSLOG_SPAN (default 70), HERO_OSLOG_PROCS (comma separated, default
 *   "mediaserverd,audiomxd,SpringBoard,backboardd,hero-run"), HERO_OSLOG_WORDS (comma separated, case-insensitive,
 *   default "haptic,actuator,vibrat,vad,chain,route,systemsound,hapt"), HERO_OSLOG_MAX (default 300 lines)
 *
 * The first use: boot-happrobe, AudioServicesPlaySystemSound(4095) asked three times and mediaserverd never started
 * the audio plug-in's Actuator. Not linked against OSLog's classes: looked up at run time (OSLogStoreSystem is not
 * in the iOS SDK).
 */
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

static NSArray<NSString *> *
list(const char *name, const char *fallback)
{
	const char *v = getenv(name);
	NSString *s = [NSString stringWithUTF8String:v && *v ? v : fallback];
	NSMutableArray *out = [NSMutableArray array];
	for (NSString *part in [s componentsSeparatedByString:@","]) {
		NSString *t = [part stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceCharacterSet]];
		if (t.length) {
			[out addObject:t.lowercaseString];
		}
	}
	return out;
}

static int
number(const char *name, int fallback)
{
	const char *v = getenv(name);
	return v && *v ? atoi(v) : fallback;
}

int
main(void)
{
	@autoreleasepool {
		int wait = number("HERO_OSLOG_WAIT", 75), span = number("HERO_OSLOG_SPAN", 70), max = number("HERO_OSLOG_MAX", 300);
		NSArray *procs = list("HERO_OSLOG_PROCS", "mediaserverd,audiomxd,SpringBoard,backboardd,hero-run");
		NSArray *words = list("HERO_OSLOG_WORDS", "haptic,actuator,vibrat,vad,chain,route,systemsound,hapt");
		setvbuf(stdout, NULL, _IOLBF, 0);
		printf("hero-oslog: waiting %d s, then %d s back; processes %s; words %s\n", wait, span,
		    [procs componentsJoinedByString:@","].UTF8String, [words componentsJoinedByString:@","].UTF8String);
		sleep((unsigned)wait);

		Class storeClass = NSClassFromString(@"OSLogStore");
		if (!storeClass) {
			[[NSBundle bundleWithPath:@"/System/Library/Frameworks/OSLog.framework"] load];
			storeClass = NSClassFromString(@"OSLogStore");
		}
		if (!storeClass) {
			printf("hero-oslog: no OSLogStore\n");
			return 1;
		}
		NSError *error = nil;
		id store = nil;
		SEL local = NSSelectorFromString(@"localStoreAndReturnError:");
		if ([storeClass respondsToSelector:local]) {
			store = ((id (*)(id, SEL, NSError **))[storeClass methodForSelector:local])(storeClass, local, &error);
		}
		if (!store) {
			SEL scoped = NSSelectorFromString(@"storeWithScope:error:");
			store = ((id (*)(id, SEL, NSInteger, NSError **))[storeClass methodForSelector:scoped])(storeClass, scoped, 0, &error);
		}
		if (!store) {
			printf("hero-oslog: no store: %s\n", error.description.UTF8String);
			return 1;
		}
		id position = [store performSelector:NSSelectorFromString(@"positionWithDate:")
		    withObject:[NSDate dateWithTimeIntervalSinceNow:-span]];
		SEL entriesSel = NSSelectorFromString(@"entriesEnumeratorWithOptions:position:predicate:error:");
		NSEnumerator *entries = ((id (*)(id, SEL, NSUInteger, id, id, NSError **))[store methodForSelector:entriesSel])(store,
		    entriesSel, 0, position, nil, &error);
		if (!entries) {
			printf("hero-oslog: no entries: %s\n", error.description.UTF8String);
			return 1;
		}
		NSDateFormatter *clock = [[NSDateFormatter alloc] init];
		clock.dateFormat = @"HH:mm:ss.SSS";
		int seen = 0, shown = 0;
		for (id entry in entries) {
			seen++;
			if (![entry respondsToSelector:NSSelectorFromString(@"process")]) {
				continue;
			}
			NSString *process = [entry valueForKey:@"process"];
			NSString *message = [entry valueForKey:@"composedMessage"];
			if (!process || !message || ![procs containsObject:process.lowercaseString]) {
				continue;
			}
			NSString *low = message.lowercaseString;
			BOOL hit = NO;
			for (NSString *w in words) {
				if ([low containsString:w]) {
					hit = YES;
					break;
				}
			}
			if (!hit) {
				continue;
			}
			NSString *subsystem = [entry respondsToSelector:NSSelectorFromString(@"subsystem")] ? [entry valueForKey:@"subsystem"] : @"";
			NSString *line = [NSString stringWithFormat:@"%@ %@ [%@] %@", [clock stringFromDate:[entry valueForKey:@"date"]],
			    process, subsystem ?: @"", message];
			printf("hero-oslog: %.600s\n", line.UTF8String);
			if (++shown >= max) {
				break;
			}
		}
		printf("hero-oslog: %d entries read, %d shown\n", seen, shown);
	}
	return 0;
}
