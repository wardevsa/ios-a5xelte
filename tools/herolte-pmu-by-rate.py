import re,sys,statistics as st,collections
L=open(sys.argv[1] if len(sys.argv)>1 else 'min111-herolog.txt',errors='replace').read().splitlines()
start=next(i for i,l in enumerate(L) if 'SCEN: bench starts' in l)
end=next((i for i,l in enumerate(L) if 'SCEN: bench finished' in l),len(L))
P=re.compile(r"cpu(\d) cyc (\d+) inst (\d+) l1r (\d+) l2r (\d+) bus (\d+)")
M=re.compile(r"HEROLTE PMU: mhz (\d+)")
agg=collections.defaultdict(lambda: dict(n=0,cyc=0,inst=0,l1=0,l2=0,bus=0,ipcs=[]))
for l in L[start:end]:
    m=M.search(l)
    if not m or "cpu" not in l: continue
    f=int(m.group(1)); 
    for c in P.finditer(l):
        cyc,inst,l1,l2,bus=[int(c.group(k)) for k in range(2,7)]
        if cyc<2e6 or inst>cyc*4: continue
        a=agg[f]; a['n']+=1; a['cyc']+=cyc; a['inst']+=inst; a['l1']+=l1; a['l2']+=l2; a['bus']+=bus; a['ipcs'].append(inst/cyc)
print("mhz   filas   IPC(agregado)  mediana   Ginst/s(todos los nucleos grandes, por ventana de 2 s)   Gciclos/s   L2 refills/kinst   ciclos por cada 1000 instr")
for f in sorted(agg):
    a=agg[f]; ventanas=a['n']/4.0
    print(f"{f:5} {a['n']:5} {a['inst']/a['cyc']:8.3f} {st.median(a['ipcs']):8.3f}   {a['inst']/ventanas/2/1e9:6.3f}   {a['cyc']/ventanas/2/1e9:6.3f}   {1000*a['l2']/a['inst']:6.2f}   {1000*a['cyc']/a['inst']:7.0f}")
