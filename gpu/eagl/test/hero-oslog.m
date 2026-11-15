/*
 * hero-oslog: what iOS's own log says, for the kernel's log. Run as hero-run's test (DROP_DIR test): from its start for
 * HERO_OSLOG_SECONDS it follows logd's live stream (LoggingSupport's OSLogEventLiveStore/OSLogEventLiveStream, what
 * `log stream` uses; looked up at run time, private) and prints the events of the processes in PROCS whose message
 * matches one of WORDS; hero-run puts its standard output in the log.
 *
 *   environment: HERO_OSLOG_SECONDS (default 80), HERO_OSLOG_PROCS (comma separated, default
 *   "mediaserverd,audiomxd,springboard,backboardd,autorun"), HERO_OSLOG_WORDS (comma separated, case-insensitive,
 *   default "haptic,actuator,vibrat,vad,chain,route,systemsound"), HERO_OSLOG_MAX (default 300 lines)
 *
 * The first use: boot-happrobe, AudioServicesPlaySystemSound(4095) asked three times and mediaserverd never started
 * the audio plug-in's Actuator. OSLogStore (the public API) has no system-wide store on iOS (boot-oslog: nil, no error).
 */
#import <Foundation/Foundation.h>
#include <dlfcn.h>
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

static id
call0(id target, NSString *selector)
{
	SEL s = NSSelectorFromString(selector);
	if (![target respondsToSelector:s]) {
		return nil;
	}
	return ((id (*)(id, SEL))[target methodForSelector:s])(target, s);
}

static void
call1(id target, NSString *selector, id argument)
{
	SEL s = NSSelectorFromString(selector);
	if ([target respondsToSelector:s]) {
		((void (*)(id, SEL, id))[target methodForSelector:s])(target, s, argument);
	} else {
		printf("hero-oslog: %s does not answer %s\n", [NSStringFromClass([target class]) UTF8String], selector.UTF8String);
	}
}

int
main(void)
{
	@autoreleasepool {
		int seconds = number("HERO_OSLOG_SECONDS", 80), max = number("HERO_OSLOG_MAX", 300);
		/* boot-oslog2: 153581 events and none of mediaserverd's matched: every process now ("*"), with a count by process */
		NSArray *procs = list("HERO_OSLOG_PROCS", "*");
		NSArray *words = list("HERO_OSLOG_WORDS", "haptic,actuator,vibrat,systemsound,taptic,4095");
		setvbuf(stdout, NULL, _IOLBF, 0);
		printf("hero-oslog: following the live log for %d s; processes %s; words %s\n", seconds,
		    [procs componentsJoinedByString:@","].UTF8String, [words componentsJoinedByString:@","].UTF8String);

		if (!dlopen("/System/Library/PrivateFrameworks/LoggingSupport.framework/LoggingSupport", RTLD_NOW)) {
			printf("hero-oslog: no LoggingSupport: %s\n", dlerror());
			return 1;
		}
		Class storeClass = NSClassFromString(@"OSLogEventLiveStore"), streamClass = NSClassFromString(@"OSLogEventLiveStream");
		if (!storeClass || !streamClass) {
			printf("hero-oslog: no OSLogEventLiveStore/OSLogEventLiveStream\n");
			return 1;
		}
		id store = call0(storeClass, @"liveLocalStore");
		if (!store) {
			printf("hero-oslog: no live local store\n");
			return 1;
		}
		__block int seen = 0, shown = 0;
		NSMutableDictionary<NSString *, NSNumber *> *counts = [NSMutableDictionary dictionary];
		__block id stream = nil;
		NSDateFormatter *clock = [[NSDateFormatter alloc] init];
		clock.dateFormat = @"HH:mm:ss.SSS";
		dispatch_semaphore_t ready = dispatch_semaphore_create(0);
		void (^prepared)(id) = ^(id source) {
			if (!source) {
				printf("hero-oslog: the store gave no source\n");
				dispatch_semaphore_signal(ready);
				return;
			}
			SEL init = NSSelectorFromString(@"initWithLiveSource:");
			id fresh = [streamClass alloc];
			stream = ((id (*)(id, SEL, id))[fresh methodForSelector:init])(fresh, init, source);
			call1(stream, @"setEventHandler:", ^(id event) {
				@synchronized (clock) {
					seen++;
					if (shown >= max) {
						return;
					}
					NSString *process = call0(event, @"process");
					NSString *message = call0(event, @"composedMessage");
					if (process) {
						counts[process] = @([counts[process] intValue] + 1);
					}
					if (!process || !message || (![procs containsObject:@"*"] && ![procs containsObject:process.lowercaseString])) {
						return;
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
						return;
					}
					NSDate *date = call0(event, @"date");
					NSString *subsystem = call0(event, @"subsystem");
					printf("hero-oslog: %s %s [%s] %.600s\n", date ? [clock stringFromDate:date].UTF8String : "-",
					    process.UTF8String, subsystem ? subsystem.UTF8String : "", message.UTF8String);
					shown++;
				}
			});
			call1(stream, @"setInvalidationHandler:", ^(NSUInteger reason) {
				printf("hero-oslog: the stream ended (reason %lu)\n", (unsigned long)reason);
			});
			call0(stream, @"activate");
			printf("hero-oslog: the stream is on\n");
			dispatch_semaphore_signal(ready);
		};
		call1(store, @"prepareWithCompletionHandler:", prepared);
		if (dispatch_semaphore_wait(ready, dispatch_time(DISPATCH_TIME_NOW, 10 * NSEC_PER_SEC)) != 0) {
			printf("hero-oslog: the store was not ready in 10 s\n");
		}
		[[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:seconds]];
		call0(stream, @"invalidate");
		@synchronized (clock) {
			printf("hero-oslog: %d events seen, %d shown\n", seen, shown);
			NSArray *busiest = [counts keysSortedByValueUsingComparator:^NSComparisonResult(NSNumber *a, NSNumber *b) {
				return [b compare:a];
			}];
			NSMutableString *top = [NSMutableString string];
			for (NSUInteger i = 0; i < busiest.count && i < 40; i++) {
				[top appendFormat:@" %@ %@", busiest[i], counts[busiest[i]]];
			}
			printf("hero-oslog: by process:%.1500s\n", top.UTF8String);
		}
	}
	return 0;
}
