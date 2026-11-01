/*
 * libheroapp.dylib, in every application while it is in the drop zone (bsd/dev/herolte_gl.c). Two things:
 *
 * An application killed by an Objective-C exception (Photos) leaves only "abort" in the log: the exception's name and
 * reason go there first.
 *
 * OpenGL ES exists in backboardd alone. Anywhere else EAGLContext is Darwin's, over a Metal that is not there, with no
 * functions behind it, and CoreImage on it jumps to address 0 (Settings and Messages, from MobileIcons). So no context
 * is given, as on a device that cannot make one.
 */
#include <dlfcn.h>
#include <objc/message.h>
#include <objc/runtime.h>

extern void herodrm_log(const char *format, ...);
extern void NSSetUncaughtExceptionHandler(void (*handler)(id));
extern const char *getprogname(void);

static const char *
text_of(id object)
{
   id string = object ? ((id (*)(id, SEL))objc_msgSend)(object, sel_registerName("description")) : nil;
   const char *text = string ? ((const char *(*)(id, SEL))objc_msgSend)(string, sel_registerName("UTF8String")) : NULL;
   return text ? text : "(none)";
}

static void
uncaught(id exception)
{
   id name = ((id (*)(id, SEL))objc_msgSend)(exception, sel_registerName("name"));
   id reason = ((id (*)(id, SEL))objc_msgSend)(exception, sel_registerName("reason"));
   herodrm_log("%s: uncaught %s: %s", getprogname(), text_of(name), text_of(reason));
}

static id
no_context(id self, SEL command, unsigned long api)
{
   (void)self;
   (void)command;
   (void)api;
   herodrm_log("%s: no EAGLContext given", getprogname());
   return nil;
}

static id
no_shared_context(id self, SEL command, unsigned long api, id sharegroup)
{
   (void)sharegroup;
   return no_context(self, command, api);
}

__attribute__((constructor)) static void
install(void)
{
   NSSetUncaughtExceptionHandler(uncaught);
   dlopen("/System/Library/Frameworks/OpenGLES.framework/OpenGLES", RTLD_LAZY);
   Class context = objc_getClass("EAGLContext");
   if (context != Nil) {
      method_setImplementation(class_getInstanceMethod(context, sel_registerName("initWithAPI:")), (IMP)no_context);
      method_setImplementation(class_getInstanceMethod(context, sel_registerName("initWithAPI:sharegroup:")),
                               (IMP)no_shared_context);
   }
}
