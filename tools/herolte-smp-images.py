#!/usr/bin/env python3
"""Map slid addresses from the kernel SMP sampler (log lines "SMP ... bt 0x...") to the dyld shared cache image and offset.

  herolte-smp-images.py SLIDE_HEX ADDR_HEX...

Reads the main dyld_shared_cache_arm64 file extracted with `7z x systemos.dmg System/Library/Caches/com.apple.dyld/*` (path C below).
Image names only: the symbol tables (.symbols, .dyldlinkedit) are APFS-compressed and 7-Zip cannot read them.
"""
import struct, sys, bisect, re
C='/media/pioxi/F20C31440C31055F/IOS-S7-work/dyld-cache/System/Library/Caches/com.apple.dyld/dyld_shared_cache_arm64'
d=open(C,'rb').read()
(magic,mapOff,mapCnt,imgOff,imgCnt,dyldBase)=struct.unpack_from('<16sIIIIQ',d,0)
# newer header: imagesOffset at 0x1c0, count at 0x1c4 when imagesOffsetOld==0
imgOffNew,imgCntNew=struct.unpack_from('<II',d,0x1c0)
if imgCnt==0: imgOff,imgCnt=imgOffNew,imgCntNew
imgs=[]
for i in range(imgCnt):
    addr,mod,ino,pathoff,pad=struct.unpack_from('<QQQII',d,imgOff+i*32)
    e=d.index(b'\0',pathoff); imgs.append((addr,d[pathoff:e].decode()))
imgs.sort()
addrs=[a for a,_ in imgs]
def lookup(a):
    i=bisect.bisect_right(addrs,a)-1
    return (imgs[i][1],a-imgs[i][0]) if i>=0 else ('?',0)
if __name__=='__main__':
    slide=int(sys.argv[1],16)
    for t in sys.argv[2:]:
        a=int(t,16)-slide
        n,off=lookup(a); print(hex(int(t,16)),n.split('/')[-1],'+0x%x'%off)
