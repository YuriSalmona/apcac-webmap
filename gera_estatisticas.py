"""Estatísticas por território de análise, para o dashboard.

Área: geodésica, calculada sobre o polígono JÁ RECORTADO pelo bioma.
NÃO usar `nuareacont` — ele é a área de contribuição original e não foi
recalculado no recorte, então microbacias cortadas na borda reportam a área
inteira (mede +4% no total do bioma).

Um território por escala:
  cerrado -> 1 (o bioma), classificado por cd_cerrado
  rhi     -> uma por Região Hidrográfica, por cd_rhi
  uph     -> uma por UPH, por cd_uph
O escopo define ao mesmo tempo QUAL território e QUAL classificação — por isso
as estatísticas não são intercambiáveis entre escalas.
"""
import json, sqlite3, time
from pyproj import Geod
from shapely import wkb

CAB = 40
GEOD = Geod(ellps="WGS84")
t0 = time.time()
L = lambda m: print(f"[{time.time()-t0:6.1f}s] {m}", flush=True)

b = sqlite3.connect("apcac_bioma.gpkg")
u = sqlite3.connect("a/apcac_uph.gpkg/apcac_uph.gpkg")
r = sqlite3.connect("c/apcac_rhi.gpkg/apcac_rhi.gpkg")
leg = json.load(open("legenda.json", encoding="utf-8"))
# IX/IXR/IIX/IIXR não são PINTADAS no mapa, mas ocupam ~27% do território:
# entram nas estatísticas para os gráficos somarem 100%. O dashboard as mostra
# como uma categoria sem preenchimento, contorno cinza e sem nome.
# (A XC — "Regular com risco de aridez" — é pintada e é uma classe normal aqui.)
OCULTAS = {"IX", "IXR", "IIX", "IIXR"}

# nomes dos territórios
nome_rhi = {int(cd): nm for cd, nm in r.execute("select rhi_cd, rhi_nm from snirh_rhi")}
nome_uph = {int(cd): nm for cd, nm in
            u.execute("select cdUPH, coalesce(nullif(nmUPH,''), sgUPH) from snirh_uph")}

# --- normalizacao dos nomes de territorio (04/09/2026) --------------------
# A base do SNIRH traz nomes truncados (campo curto) e em CAIXA ALTA sem
# acentuacao. Normalizamos aqui para que uma regeneracao nao desfaca a
# correcao publicada. Grafias confirmadas por Yuri Salmona.
import re as _re
_UF = {'AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA',
       'PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO'}
_MANTEM = _UF | {'SF'}                      # SF = Sao Francisco
_CONECTORES = {'de','do','da','das','dos','e','a','o','em','no','na','ao','aos'}
_ACENTOS = {'Medio':'Médio','Guacu':'Guaçu','Sao':'São','Jose':'José',
            'Paranaiba':'Paranaíba','Jatai':'Jataí','Parnaiba':'Parnaíba',
            'Piaui':'Piauí','Goias':'Goiás','Ceara':'Ceará'}
_CORRECOES = {                              # nomes truncados na base -> grafia correta
    842:'Médio Paranapanema (PR)',
    904:'Difusas da Barragem de Boa Esperança',
    905:'Difusas do Alto Parnaíba',
    906:'Difusas do Médio Parnaíba',
    1020:'Médio e Baixo Gorutuba',
    1021:'Médio Verde Grande',               # 1021 e 1022 sao fragmentos da MESMA UPH
    1022:'Médio Verde Grande',
    1023:'Margem Esquerda do Lago de Sobradinho',
}

def _caixa_titulo(nome):
    nome = _re.sub(r'\s+', ' ', nome).strip()
    saida, primeira = [], True
    for p in _re.split(r'([ /\-])', nome):
        if p in (' ', '/', '-') or p == '':
            saida.append(p); continue
        nucleo = _re.sub(r'[^A-Za-zÀ-ÿ]', '', p)
        sigla = (nucleo.isupper() and len(nucleo) <= 4
                 and not _re.search(r'[AEIOUÁÉÍÓÚÂÊÔÃÕÀ]', nucleo))   # PCJ, SF...
        if (nucleo.upper() in _MANTEM and len(nucleo) <= 3) or sigla:
            saida.append(p.upper())
        elif not primeira and nucleo.lower() in _CONECTORES:
            saida.append(p.lower())
        else:
            saida.append(p[:1].upper() + p[1:].lower())
        primeira = False
    return ''.join(saida)

def normaliza_nome(escala, cod, nome):
    if escala == 'uph' and int(cod) in _CORRECOES:
        return _CORRECOES[int(cod)]
    arrumado = _caixa_titulo(nome)
    return _re.sub('[A-Za-zÀ-ÿ]+',
                   lambda m: _ACENTOS.get(m.group(0), m.group(0)), arrumado)

nome_rhi = {cd: normaliza_nome('rhi', cd, nm) for cd, nm in nome_rhi.items()}
nome_uph = {cd: normaliza_nome('uph', cd, nm) for cd, nm in nome_uph.items()}
# -------------------------------------------------------------------------


L("calculando área geodésica de cada microbacia recortada…")
linhas = []
for i, (fid, geom, cc, cr, cu, iu, ir) in enumerate(b.execute(
        "select fid, geom, cd_cerrado, cd_rhi, cd_uph, id_uph, id_rhi from apcac")):
    g = wkb.loads(geom[CAB:])
    ha = abs(GEOD.geometry_area_perimeter(g)[0]) / 10_000.0   # m² -> ha
    linhas.append((cc, cr, cu, iu, ir, ha))
    if (i + 1) % 25000 == 0:
        L(f"   {i+1:,}/122.314")
L(f"{len(linhas):,} microbacias | área total: {sum(x[5] for x in linhas)/1e6:,.2f} milhões de ha")

def acumula(chave_idx, classe_idx, nomes, escala):
    terr = {}
    for x in linhas:
        k = x[chave_idx]
        cd = x[classe_idx]
        t = terr.setdefault(k, {"nome": nomes.get(k, f"({escala} {k})"), "classes": {}})
        t["classes"][cd] = t["classes"].get(cd, 0.0) + x[5]
    return terr

est = {
    "cerrado": {"BIOMA": {"nome": "Bioma Cerrado",
                          "classes": {}}},
    "rhi": acumula(4, 1, nome_rhi, "RHI"),
    "uph": acumula(3, 2, nome_uph, "UPH"),
}
for x in linhas:                      # o bioma inteiro, por cd_cerrado
    c = est["cerrado"]["BIOMA"]["classes"]
    c[x[0]] = c.get(x[0], 0.0) + x[5]

# arredonda para ha inteiro (é como o dashboard exibe)
for escala in est.values():
    for t in escala.values():
        t["classes"] = {k: round(v) for k, v in sorted(t["classes"].items(),
                                                       key=lambda kv: -kv[1])}
        t["total_ha"] = sum(t["classes"].values())

for esc, d in est.items():
    L(f"{esc:8}: {len(d):3} territórios | maior: "
      f"{max(d.values(), key=lambda t: t['total_ha'])['nome']}")

json.dump(est, open("estatisticas.json", "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
import os
L(f"estatisticas.json -> {os.path.getsize('estatisticas.json')/1024:.0f} KB")

# conferências
cls_leg = {e["cd"] for e in leg}
for esc, d in est.items():
    fora = {c for t in d.values() for c in t["classes"] if c not in cls_leg}
    assert not fora, f"{esc}: classe fora da legenda: {fora}"
L("OK: nenhuma classe fora da legenda")
tot_bioma = est["cerrado"]["BIOMA"]["total_ha"]
tot_rhi = sum(t["total_ha"] for t in est["rhi"].values())
tot_uph = sum(t["total_ha"] for t in est["uph"].values())
L(f"total por escala (ha): cerrado={tot_bioma:,} rhi={tot_rhi:,} uph={tot_uph:,}")
# Agora que nada é excluído, as três escalas cobrem o MESMO território — os
# totais têm de bater. Não exatamente: cada território arredonda suas classes
# para ha inteiro, e somar 143 UPHs acumula mais resíduo que somar 1 bioma.
# Medido: 9 ha em 198 milhões. A tolerância cresce com o nº de territórios.
for esc, tot in (("rhi", tot_rhi), ("uph", tot_uph)):
    folga = 2 * len(est[esc]) * len(leg)      # ±1 ha por (território × classe)
    assert abs(tot - tot_bioma) <= folga, \
        f"{esc} soma {tot:,} ha vs bioma {tot_bioma:,} — diferença além do arredondamento"
L(f"OK: as 3 escalas somam a mesma área (resíduo de arredondamento: "
  f"rhi {tot_rhi-tot_bioma:+} ha, uph {tot_uph-tot_bioma:+} ha)")
oc = sum(v for t in est["cerrado"]["BIOMA"]["classes"].items() for k, v in [t] if k in OCULTAS)
xc = est["cerrado"]["BIOMA"]["classes"].get("XC", 0)
L(f"no bioma: Regular sem nome (oculta no mapa) = {oc:,} ha ({100*oc/tot_bioma:.1f}%)")
L(f"          Regular com risco de aridez (XC)  = {xc:,} ha ({100*xc/tot_bioma:.1f}%)")
