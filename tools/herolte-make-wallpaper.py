# The default wallpaper of the drop zone: a gradient of our own.
import sys
from PIL import Image, ImageFilter
import math
W,H=720,1280
im=Image.new('RGB',(W,H))
p=im.load()
for y in range(H):
    for x in range(W):
        t=y/H; a=x/W
        r=int(25+60*t+60*math.sin(a*3+t*2)**2); g=int(20+40*(1-t)+50*math.sin(t*4+a)**2); b=int(90+120*(1-t)+40*math.cos(a*2-t*3)**2)
        p[x,y]=(min(r,255),min(g,255),min(b,255))
im=im.filter(ImageFilter.GaussianBlur(6)); im.save(sys.argv[1],optimize=True)
