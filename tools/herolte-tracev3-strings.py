# Reads strings out of the phone's own unified log: decompresses the LZ4 (bv41) blocks of .tracev3 files (pulled with tools/herolte-hfs-read.py pullr) and prints printable strings containing any given word. Usage: herolte-tracev3-strings.py "Persist/*.tracev3" word [word...]. Needs the lz4 module.
import sys,re,struct,glob,os
import lz4.block
def blocks(b):
    i=0
    while True:
        i=b.find(b'bv41',i)
        if i<0: return
        if i+12>len(b): return
        u,c=struct.unpack('<II',b[i+4:i+12])
        if 0<c<1<<22 and 0<u<1<<24 and b[i+12+c:i+16+c]==b'bv4$':
            try: yield lz4.block.decompress(b[i+12:i+12+c],uncompressed_size=u)
            except Exception: pass
            i+=16+c
        else: i+=4
pat=re.compile(rb'[\x20-\x7e]{6,}')
words=[w.encode() for w in sys.argv[2:]]
for f in sorted(glob.glob(sys.argv[1])):
    n=0
    for d in blocks(open(f,'rb').read()):
        for m in pat.finditer(d):
            s=m.group(0)
            if any(w in s for w in words):
                print(os.path.basename(f), s.decode('latin1')[:240]); n+=1
