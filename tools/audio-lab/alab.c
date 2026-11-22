/*
 * alab: ALSA by hand, for finding out in TWRP (Linux, Cronos kernel) what the S7's codec and amplifier need, before
 * doing it from XNU. Static aarch64; talks to the kernel's ioctls directly.
 *
 *   alab list                        every mixer control, with its value
 *   alab set "Control name" value    number, or enumerated item name
 *   alab tone DEVICE SECONDS [LEVEL] 48 kHz stereo 16-bit sine at 440 Hz, LEVEL in 1/1000 of full scale (default 50)
 */
#include <errno.h>
#include <fcntl.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <time.h>
#include <unistd.h>
#include <sound/asound.h>

#define CTL "/dev/snd/controlC0"

static int
open_ctl(void)
{
   int fd = open(CTL, O_RDWR);
   if (fd < 0) {
      perror(CTL);
      exit(1);
   }
   return fd;
}

static void
print_value(int fd, struct snd_ctl_elem_info *info)
{
   struct snd_ctl_elem_value v;
   memset(&v, 0, sizeof(v));
   v.id = info->id;
   if (ioctl(fd, SNDRV_CTL_IOCTL_ELEM_READ, &v) < 0) {
      printf("(unreadable: %s)", strerror(errno));
      return;
   }
   for (unsigned i = 0; i < info->count && i < 8; i++) {
      if (info->type == SNDRV_CTL_ELEM_TYPE_ENUMERATED) {
         struct snd_ctl_elem_info item = *info;
         item.value.enumerated.item = v.value.enumerated.item[i];
         ioctl(fd, SNDRV_CTL_IOCTL_ELEM_INFO, &item);
         printf("%s%s", i ? "," : "", item.value.enumerated.name);
      } else if (info->type == SNDRV_CTL_ELEM_TYPE_INTEGER || info->type == SNDRV_CTL_ELEM_TYPE_BOOLEAN) {
         printf("%s%ld", i ? "," : "", v.value.integer.value[i]);
      } else {
         printf("(type %d)", info->type);
         return;
      }
   }
}

static void
list(void)
{
   int fd = open_ctl();
   struct snd_ctl_elem_list l;
   memset(&l, 0, sizeof(l));
   ioctl(fd, SNDRV_CTL_IOCTL_ELEM_LIST, &l);
   l.space = l.count;
   l.pids = calloc(l.count, sizeof(*l.pids));
   ioctl(fd, SNDRV_CTL_IOCTL_ELEM_LIST, &l);
   for (unsigned i = 0; i < l.used; i++) {
      struct snd_ctl_elem_info info;
      memset(&info, 0, sizeof(info));
      info.id = l.pids[i];
      if (ioctl(fd, SNDRV_CTL_IOCTL_ELEM_INFO, &info) < 0)
         continue;
      printf("%s = ", info.id.name);
      print_value(fd, &info);
      printf("\n");
   }
}

static int
set(const char *name, const char *text)
{
   int fd = open_ctl();
   struct snd_ctl_elem_info info;
   memset(&info, 0, sizeof(info));
   info.id.iface = SNDRV_CTL_ELEM_IFACE_MIXER;
   strncpy((char *)info.id.name, name, sizeof(info.id.name) - 1);
   if (ioctl(fd, SNDRV_CTL_IOCTL_ELEM_INFO, &info) < 0) {
      printf("%s: no such control\n", name);
      return 1;
   }
   struct snd_ctl_elem_value v;
   memset(&v, 0, sizeof(v));
   v.id = info.id;
   if (info.type == SNDRV_CTL_ELEM_TYPE_ENUMERATED) {
      unsigned found = info.value.enumerated.items;
      for (unsigned i = 0; i < info.value.enumerated.items; i++) {
         struct snd_ctl_elem_info item = info;
         item.value.enumerated.item = i;
         ioctl(fd, SNDRV_CTL_IOCTL_ELEM_INFO, &item);
         if (strcmp(item.value.enumerated.name, text) == 0)
            found = i;
      }
      if (found == info.value.enumerated.items) {
         printf("%s: no item %s\n", name, text);
         return 1;
      }
      for (unsigned i = 0; i < info.count; i++)
         v.value.enumerated.item[i] = found;
   } else {
      for (unsigned i = 0; i < info.count && i < 128; i++)
         v.value.integer.value[i] = atol(text);
   }
   if (ioctl(fd, SNDRV_CTL_IOCTL_ELEM_WRITE, &v) < 0) {
      printf("%s: write failed: %s\n", name, strerror(errno));
      return 1;
   }
   printf("%s = ", name);
   print_value(fd, &info);
   printf("\n");
   return 0;
}

static void
mask_set(struct snd_pcm_hw_params *p, int which, unsigned bit)
{
   struct snd_mask *m = &p->masks[which - SNDRV_PCM_HW_PARAM_FIRST_MASK];
   memset(m, 0, sizeof(*m));
   m->bits[bit / 32] = 1u << (bit % 32);
}

static void
interval_set(struct snd_pcm_hw_params *p, int which, unsigned value)
{
   struct snd_interval *i = &p->intervals[which - SNDRV_PCM_HW_PARAM_FIRST_INTERVAL];
   i->min = i->max = value;
   i->integer = 1;
}

static void
params_any(struct snd_pcm_hw_params *p)
{
   memset(p, 0, sizeof(*p));
   for (int i = 0; i <= SNDRV_PCM_HW_PARAM_LAST_MASK - SNDRV_PCM_HW_PARAM_FIRST_MASK; i++)
      memset(&p->masks[i], 0xff, sizeof(p->masks[i]));
   for (int i = 0; i <= SNDRV_PCM_HW_PARAM_LAST_INTERVAL - SNDRV_PCM_HW_PARAM_FIRST_INTERVAL; i++)
      p->intervals[i].max = ~0u;
   p->rmask = ~0u;
}

static int
tone(int device, int seconds, int level)
{
   char path[64];
   snprintf(path, sizeof(path), "/dev/snd/pcmC0D%dp", device);
   int fd = open(path, O_RDWR);
   if (fd < 0) {
      perror(path);
      return 1;
   }
   struct snd_pcm_hw_params p;
   params_any(&p);
   mask_set(&p, SNDRV_PCM_HW_PARAM_ACCESS, SNDRV_PCM_ACCESS_RW_INTERLEAVED);
   mask_set(&p, SNDRV_PCM_HW_PARAM_FORMAT, SNDRV_PCM_FORMAT_S16_LE);
   mask_set(&p, SNDRV_PCM_HW_PARAM_SUBFORMAT, SNDRV_PCM_SUBFORMAT_STD);
   interval_set(&p, SNDRV_PCM_HW_PARAM_CHANNELS, 2);
   interval_set(&p, SNDRV_PCM_HW_PARAM_RATE, 48000);
   interval_set(&p, SNDRV_PCM_HW_PARAM_PERIOD_SIZE, 1024);
   interval_set(&p, SNDRV_PCM_HW_PARAM_PERIODS, 4);
   if (ioctl(fd, SNDRV_PCM_IOCTL_HW_PARAMS, &p) < 0) {
      perror("HW_PARAMS");
      return 1;
   }
   struct snd_pcm_sw_params s;
   memset(&s, 0, sizeof(s));
   s.avail_min = 1024;
   s.start_threshold = 1024;
   s.stop_threshold = 4096;
   s.xfer_align = 1;
   ioctl(fd, SNDRV_PCM_IOCTL_SW_PARAMS, &s);
   if (ioctl(fd, SNDRV_PCM_IOCTL_PREPARE) < 0) {
      perror("PREPARE");
      return 1;
   }
   static short buffer[2048];
   double phase = 0, amplitude = 32767.0 * level / 1000.0;
   unsigned long frames = 0, end = 48000ul * seconds;
   unsigned xruns = 0;
   printf("playing on %s, level %d/1000, %d s\n", path, level, seconds);
   fflush(stdout);
   while (frames < end) {
      for (int i = 0; i < 1024; i++) {
         short sample = (short)(sin(phase) * amplitude);
         phase += 2 * M_PI * 440.0 / 48000.0;
         buffer[2 * i] = buffer[2 * i + 1] = sample;
      }
      struct snd_xferi x = { .buf = buffer, .frames = 1024 };
      if (ioctl(fd, SNDRV_PCM_IOCTL_WRITEI_FRAMES, &x) < 0) {
         if (errno == EPIPE) {
            xruns++;
            ioctl(fd, SNDRV_PCM_IOCTL_PREPARE);
            continue;
         }
         perror("WRITEI");
         return 1;
      }
      frames += 1024;
   }
   ioctl(fd, SNDRV_PCM_IOCTL_DRAIN);
   printf("done, %lu frames, %u xruns\n", frames, xruns);
   return 0;
}

int
main(int argc, char **argv)
{
   if (argc >= 2 && strcmp(argv[1], "list") == 0) {
      list();
      return 0;
   }
   if (argc == 4 && strcmp(argv[1], "set") == 0)
      return set(argv[2], argv[3]);
   if (argc >= 4 && strcmp(argv[1], "tone") == 0)
      return tone(atoi(argv[2]), atoi(argv[3]), argc > 4 ? atoi(argv[4]) : 50);
   fprintf(stderr, "alab list | set NAME VALUE | tone DEVICE SECONDS [LEVEL]\n");
   return 2;
}
