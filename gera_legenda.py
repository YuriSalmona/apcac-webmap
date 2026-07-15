"""Gera o legenda.json que alimenta o webmap, a partir do QML embutido no GPKG.

Fonte da verdade: tabela `layer_styles` do apcac_cerrado.gpkg (RuleRenderer, 20 regras).
Os três GPKGs têm a MESMA legenda — conferido classe a classe.

Rodar de novo é seguro: reaplica o agrupamento e a troca de termo.
"""
import json, re, sqlite3

GPKG = "d/apcac_cerrado.gpkg/apcac_cerrado.gpkg"
SAIDA = "legenda.json"

# Terminologia definida pelo Instituto, sobrepõe o texto do QML.
TERMOS = {"risco de déficit hídrico": "risco de aridez"}

# Prioridade Hidrológica: lida da coluna `cd_apcac_a` do próprio dado, não deduzida
# do código. A letra do código NÃO serve: no `XC` o "C" é o sufixo de aridez, e a
# prioridade é X (Regular). Mapeamento conferido: 1:1 e idêntico nos 3 escopos.
PRIORIDADE = {"A": "Extremamente Alta", "B": "Muito Alta", "C": "Alta", "X": "Regular"}

# Agrupamento por ação prioritária + risco predominante (definido pelo Instituto;
# NÃO está no QML). Note que o sufixo "R" ("alto risco" no rótulo do QML) significa
# coisas diferentes conforme a predominância: desmatamento nas naturais (I*R),
# degradação do solo nas antrópicas (II*R). Daí o risco ser do grupo, não da classe.
GRUPOS = [
    ("Comando e Controle",                   "Risco de Desmatamento",        ["IAR", "IBR", "ICR", "IXR"]),
    ("Proteção",                             "Risco de Desmatamento",        ["IA", "IB", "IC", "IX"]),
    ("Restauração Ecológica",                "Risco de Degradação do Solo",  ["IIAR", "IIBR", "IICR", "IIXR"]),
    ("Restauração Ecológica",                "Risco Padrão",                 ["IIA", "IIB", "IIC", "IIX"]),
    ("Manejo do Solo e Revezamento Hídrico", "Risco de Aridez",              ["IIAC", "IIBC", "IICC"]),
    ("Conjunto de Ações Diversas",           "Risco de Aridez",              ["XC"]),
]

con = sqlite3.connect(GPKG)
qml = con.execute(
    "select styleQML from layer_styles where f_table_name='apcac_bho5k'").fetchone()[0]

# cd_apcac -> cd_apcac_a, direto da tabela de feições
cd_a = {}
for cd, a in con.execute("select cd_apcac, cd_apcac_a from apcac_bho5k group by 1, 2"):
    assert cd not in cd_a, f"{cd} tem mais de um cd_apcac_a — mapeamento ambíguo"
    cd_a[cd] = a

cores = {}
for m in re.finditer(r'<symbol[^>]*name="([^"]+)"[^>]*>(.*?)</symbol>', qml, re.S):
    c = re.search(r'name="color" value="([^"]+)"', m.group(2))
    if c:
        cores[m.group(1)] = "#%02x%02x%02x" % tuple(int(v) for v in c.group(1).split(",")[:3])

# Decompor pelo TEXTO do rótulo, não pelo código: a regra "letra = importância"
# quebra no XC (o rótulo diz "regular, déficit hídrico"; a regra daria "alta, sem risco").
bruto = {}
for m in re.finditer(r'<rule label="([^"]*)"[^>]*symbol="([^"]+)"', qml):
    lab, sym = m.groups()
    cd, desc = lab.split(" - ", 1)
    for de, para in TERMOS.items():
        desc = desc.replace(de, para)
    p = [x.strip() for x in desc.split(",")]
    importancia = re.sub(r'^importância hidro(lógica)?\.? ', '', p[1])
    prioridade = PRIORIDADE[cd_a[cd]]
    # o rótulo do QML e a coluna cd_apcac_a são fontes independentes: se
    # divergirem, uma das duas está errada e é melhor saber agora.
    assert importancia.lower() == prioridade.lower(), \
        f"{cd}: rótulo do QML diz '{importancia}' mas cd_apcac_a='{cd_a[cd]}' -> '{prioridade}'"
    bruto[cd] = {
        "cd": cd, "cor": cores[sym],
        "predominancia": p[0].replace("Predominância ", ""),
        "prioridade": prioridade,          # <- é isto que a legenda mostra
        "cd_apcac_a": cd_a[cd],
        "risco": p[2] if len(p) > 2 else None,
        "rotulo": desc,                    # texto completo, usado no popup
    }

legenda = []
for acao, risco_pred, cds in GRUPOS:
    for cd in cds:
        legenda.append({**bruto[cd], "acao": acao, "risco_predominante": risco_pred})

faltando = set(bruto) - {e["cd"] for e in legenda}
assert not faltando, f"classes sem grupo: {faltando}"
assert len(legenda) == 20, f"esperava 20 classes, obtive {len(legenda)}"
assert len({e["cd"] for e in legenda}) == 20, "classe repetida em mais de um grupo"
assert not any("déficit hídrico" in json.dumps(e, ensure_ascii=False) for e in legenda), \
    "termo antigo sobreviveu"

json.dump(legenda, open(SAIDA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{len(legenda)} classes -> {SAIDA}  (rótulo do QML confere com cd_apcac_a em todas)\n")
for acao, risco_pred, cds in GRUPOS:
    print(f"{acao} / {risco_pred}")
    for cd in cds:
        e = bruto[cd]
        print(f"   {e['cor']}  {cd:5} — {e['prioridade']:18} (cd_apcac_a={e['cd_apcac_a']})")
