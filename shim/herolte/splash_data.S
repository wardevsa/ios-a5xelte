/* Boot image blob for xnu_boot.c (docs/herolte-splash.md). Empty unless build.sh finds shim/herolte/splash.bin. */
    .section .rodata
    .balign 4
    .global hero_splash_blob
hero_splash_blob:
#ifdef HERO_SPLASH_FILE
    .incbin HERO_SPLASH_FILE
#endif
    .balign 4
    .global hero_splash_blob_end
hero_splash_blob_end:
