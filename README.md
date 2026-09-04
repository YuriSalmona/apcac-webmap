# APIAC — Áreas Prioritárias da Conservação de Água do Cerrado

Webmap estático das APIAC. Instituto Cerrados, solicitação IC26017 (apresentação MMA).

## Como funciona

Site estático puro — sem servidor de aplicação, sem build. Os dados vêm em **PMTiles**,
que o navegador consulta por **HTTP Range requests**: só os bytes dos tiles visíveis são
baixados. A abertura do mapa custa ~40 KB, não os 45 MB do repositório.

> **O host precisa suportar Range requests** e servir o MIME correto. GitHub Pages
> suporta. Um host que ignore o cabeçalho `Range` e devolva o arquivo inteiro quebra o
> mapa silenciosamente.

| Arquivo | Zoom | Conteúdo |
|---|---|---|
| `cerrado_raster.pmtiles` | 3–9 | visão geral, ranking contra o Cerrado inteiro |
| `rhi_raster.pmtiles` | 3–9 | visão geral, ranking por Região Hidrográfica |
| `uph_raster.pmtiles` | 3–9 | visão geral, ranking por UPH |
| `apcac_detalhe.pmtiles` | 10 | microbacias clicáveis, com as 3 classificações |
| `limites.pmtiles` | 3–10 | limites de análise (bioma, RHI, UPH): contorno + alvo de clique |
| `legenda.json` | — | 20 classes: cor, prioridade, ação, risco |
| `estatisticas.json` | — | área (ha) por classe, para cada um dos 154 territórios |

**Raster na visão geral, vetor no detalhe:** no zoom 4 cada microbacia tem ~2 pixels;
201 mil polígonos vetoriais custariam ~3 MB por tile (o piso por feição do MVT) e
travariam o navegador. O raster desenha o mesmo por ~15 KB. A partir do z10 o vetor
assume e as feições ficam clicáveis. O z10 tem precisão de ~9 m — sub-pixel até o z13,
então o MapLibre faz overzoom sem perda visível e não há tiles z11+.

`limites.pmtiles` traz **polígonos**, não linhas: o `line` desenha o contorno e um
`fill` invisível recebe o clique (não se clica numa linha).

## Os três escopos

Os três rasters são a **mesma geometria**. Muda só o recorte contra o qual a importância
hidrológica é ranqueada (quantis 5/5/30/60 → A/B/C/X): o Cerrado inteiro (limiares
globais, cores comparáveis entre regiões — é o padrão), cada Região Hidrográfica, ou
cada UPH. Por isso é **um** mapa com seletor, e não três mapas.

> **Cuidado com as contagens.** No dado recortado pelo bioma há **10 Regiões
> Hidrográficas** e **143 UPHs**. Não confundir com o universo nacional da ANA que vem
> nas camadas de referência (`snirh_rhi`, `snirh_uph`): lá são 13 linhas / 12 regiões e
> 456 linhas / 455 UPHs — os dois têm feições multipart explodidas em linhas repetidas,
> com os atributos (inclusive a área total) duplicados.

## Recortes e o que é apresentado

- **Limite do bioma Cerrado** (`Cerrado_2019`): 201.499 → 122.314 microbacias.
- **Prioridade Regular não é pintada**, exceto a classe `XC` ("Conjunto de Ações
  Diversas"). O filtro é **por escopo** — uma microbacia pode ser Regular no Cerrado e
  Alta na sua UPH. Do dado só saíram as ocultas nos três escopos ao mesmo tempo.
- **O dashboard conta tudo.** As classes ocultas no mapa são 33,4% da área e entram nas
  estatísticas como uma categoria sem preenchimento e sem nome — senão os gráficos
  descreveriam a parte pintada do território, não o território.

## Áreas

Em hectares, **geodésicas**, calculadas sobre o polígono já recortado. **Não usar
`nuareacont`**: é a área de contribuição original, não recalculada no recorte, então
microbacias cortadas na borda reportam a área inteira (mede +4% no total do bioma).

## Regerar

Os três scripts assumem os GeoPackages de origem nos caminhos do `scratchpad`; são
referência de método, não rodam a partir deste repositório.

- `gera_legenda.py` — extrai a legenda do QML embutido no GeoPackage, aplica o
  agrupamento por ação prioritária e a terminologia do Instituto. Tem asserções que
  falham alto se o dado de origem mudar (inclusive um cruzamento entre o rótulo do QML e
  a coluna `cd_apcac_a`).
- `recorta_bioma.py` — recorte pelo bioma via índice espacial (6 min; o
  `ogr2ogr -clipsrc` levaria mais de 8 horas).
- `gera_estatisticas.py` — área geodésica por classe, por território.

## Créditos de terceiros

Mapa de fundo claro © OpenStreetMap © CARTO · Imagens de satélite © Esri, Maxar,
Earthstar Geographics · Renderização: MapLibre GL JS · Formato: PMTiles (Protomaps).
