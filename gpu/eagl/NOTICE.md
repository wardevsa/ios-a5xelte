# gpu/eagl third-party notice

`src/eagl.m`, `src/eagl_private.h`, `src/gl_resolve.c`, `src/gl_tab.h`, `src/gl_unimpl.c`,
`src/macro_ctx.c`, `src/macro_ctx.h`, `src/macro_slots.c`, `src/osm.h`, `tools/gen_gl_stubs.py` and
`test/eagl_ca_test.m` are Bergamota's EAGL shim (https://github.com/ry-diffusion/Bergamota, branch
`gpu-eagl`, `gpu/eagl/`), MIT, copied with their SPDX headers. Changes, each marked "Galaxy S7 port" in the
source: a crash reporter at the top of `main()` in `eagl_ca_test.m`; an `EAGL_TRACE_ON` switch in `macro_ctx.c`;
and `eagl_macro_ensure()` (`eagl.m`, called by every macro-context forwarder in `gen_gl_stubs.py` and
`macro_ctx.c`), which makes the context a macro call names current on the calling thread, because iOS 16's
render server draws from a thread where its context is not current. `src/osm.c` is based on theirs.
Thanks to the Bergamota authors: their shim is what lets CoreAnimation's GLES renderer run on Mesa.

The `macro_slots.c` offsets were derived from iOS 18 (22H352); the same offsets were checked against this
port's iOS 16 OpenGLES.framework (all 457 entry points match). Unlike iOS 18, iOS 16's render server
still falls back to `CA::OGL::GLESContext` by itself when Metal is unavailable (it creates an
`EAGLContext` with `initWithAPI:3 properties:`), so Bergamota's QuartzCore hook is not needed here.



