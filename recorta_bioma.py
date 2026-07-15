"""Recorta as microbacias pelo limite do bioma.

Por que não usar `ogr2ogr -clipsrc`: ele roda a intersecção completa em TODAS as
feições, inclusive nas que estão inteiramente dentro do bioma e não precisam de
corte. Contra um limite de 350 mil vértices isso mediu ~12 KB/s -> +8 horas.

Aqui: um índice espacial (STRtree) separa as feições em três grupos e só o
terceiro — as poucas que cruzam a borda — paga o custo da intersecção.
"""
import shutil, sqlite3, struct, time
import shapely
from shapely import wkb
from shapely.strtree import STRtree

ORIG, SAIDA = "apcac_web.gpkg", "apcac_bioma.gpkg"
CAB = 40  # cabeçalho GPKG: 8 (magic/flags/srs) + 32 (envelope xmin,xmax,ymin,ymax)
t0 = time.time()
L = lambda m: print(f"[{time.time()-t0:6.1f}s] {m}", flush=True)


def para_blob(g, srs=4326):
    x0, y0, x1, y1 = g.bounds
    return (b"GP" + bytes([0, 0b00000011]) + struct.pack("<i", srs)
            + struct.pack("<4d", x0, x1, y0, y1) + shapely.to_wkb(g))


bioma = wkb.loads(sqlite3.connect("bioma_tmp.gpkg").execute(
    "select geom from b").fetchone()[0][CAB:])
L(f"bioma carregado: {len(shapely.get_coordinates(bioma)):,} vértices, válido={bioma.is_valid}")
if not bioma.is_valid:
    bioma = bioma.buffer(0)
    L("bioma reparado com buffer(0)")

shutil.copy(ORIG, SAIDA)
c = sqlite3.connect(SAIDA)
fids, geoms = [], []
for fid, blob in c.execute("select fid, geom from apcac"):
    fids.append(fid)
    geoms.append(wkb.loads(blob[CAB:]))
L(f"{len(fids):,} microbacias carregadas")

arvore = STRtree(geoms)
dentro = set(arvore.query(bioma, predicate="contains").tolist())
toca = set(arvore.query(bioma, predicate="intersects").tolist())
cruza = toca - dentro
fora = set(range(len(fids))) - toca
L(f"dentro (sem corte): {len(dentro):,} | cruzam a borda (cortar): {len(cruza):,} | fora (remover): {len(fora):,}")

# só as que cruzam pagam a intersecção
novos, vazias = [], []
for i, idx in enumerate(cruza):
    g = geoms[idx].intersection(bioma)
    if g.is_empty:
        vazias.append(idx)
        continue
    if g.geom_type == "GeometryCollection":
        ps = [p for p in g.geoms if p.geom_type in ("Polygon", "MultiPolygon")]
        if not ps:
            vazias.append(idx); continue
        g = shapely.union_all(ps)
    novos.append((para_blob(g), fids[idx]))
    if (i + 1) % 2000 == 0:
        L(f"   cortadas {i+1:,}/{len(cruza):,}")
L(f"cortadas {len(novos):,} | resultaram vazias: {len(vazias):,}")

# rtree usa ST_* (indisponíveis no sqlite puro): remover, editar, reconstruir
trg = {n: s for n, s in c.execute(
    "select name,sql from sqlite_master where type='trigger' and name like 'rtree_apcac%'")}
for n in trg:
    c.execute(f'drop trigger "{n}"')

remover = [(fids[i],) for i in fora | set(vazias)]
c.executemany("delete from apcac where fid=?", remover)
c.executemany("update apcac set geom=? where fid=?", novos)
c.execute("update gpkg_geometry_columns set geometry_type_name='GEOMETRY' where table_name='apcac'")
L(f"removidas {len(remover):,} | geometrias atualizadas {len(novos):,}")

# reconstrói o índice espacial a partir das geometrias finais
c.execute("delete from rtree_apcac_geom")
c.execute("""insert into rtree_apcac_geom(id,minx,maxx,miny,maxy)
             select fid,
                    cast(substr(geom,9,8) as blob), cast(substr(geom,17,8) as blob),
                    cast(substr(geom,25,8) as blob), cast(substr(geom,33,8) as blob)
             from apcac where 0""")  # placeholder: preenchido abaixo em Python
linhas = [(fid, *struct.unpack("<4d", blob[8:40]))
          for fid, blob in c.execute("select fid, geom from apcac")]
c.executemany("insert into rtree_apcac_geom(id,minx,maxx,miny,maxy) values (?,?,?,?,?)",
              [(f, x0, x1, y0, y1) for f, x0, x1, y0, y1 in linhas])
for n, s in trg.items():
    c.execute(s)

n = c.execute("select count(*) from apcac").fetchone()[0]
c.execute("update gpkg_ogr_contents set feature_count=? where lower(table_name)='apcac'", (n,))
xs = [r[1] for r in linhas] + [r[2] for r in linhas]
ys = [r[3] for r in linhas] + [r[4] for r in linhas]
c.execute("update gpkg_contents set min_x=?,max_x=?,min_y=?,max_y=? where table_name='apcac'",
          (min(xs), max(xs), min(ys), max(ys)))
c.commit()
c.execute("vacuum")
L(f"FIM: {n:,} feições | bbox ({min(xs):.4f},{min(ys):.4f})-({max(xs):.4f},{max(ys):.4f})")
