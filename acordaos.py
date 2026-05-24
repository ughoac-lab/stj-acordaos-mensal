"""Coleta acórdãos tributários do STJ (1ª Turma, 2ª Turma, 1ª Seção) via
Dados Abertos do STJ e gera uma página HTML mensal.

Fonte: dadosabertos.web.stj.jus.br (datasets "Espelhos de acórdãos"),
em JSON mensal por turma/seção. Sem scraping, sem proteção anti-robô.

Estratégia:
- Baixa o arquivo mensal MAIS RECENTE de cada um dos 3 órgãos.
- Mantém só os acórdãos cuja EMENTA é tributária (contém "tribut...").
- Página com filtros laterais por Órgão e por Tributo (client-side).
"""

from __future__ import annotations

import datetime
import html
import re
import sys
from collections import Counter
from pathlib import Path

import requests

CKAN = "https://dadosabertos.web.stj.jus.br"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
OUTPUT_FILE = Path(__file__).parent / "index.html"
LINK_MONOCRATICAS = "https://ughoac-lab.github.io/stj-monitor/"

DATASETS = {
    "1ª Turma": "espelhos-de-acordaos-primeira-turma",
    "2ª Turma": "espelhos-de-acordaos-segunda-turma",
    "1ª Seção": "espelhos-de-acordaos-primeira-secao",
}

# Âncora: ementa tributária. \btribut casa tributário/tributária/tributo/
# tributação, mas NÃO contribuição (que nem contém "tribut").
ANCHOR_RE = re.compile(r"\btribut", re.I)

# Tributos para o filtro lateral (mesma lista do robô de monocráticas).
TERMS = [
    ("IRPJ", re.compile(r"\bIRPJ\b", re.I)),
    ("CSLL", re.compile(r"\bCSLL\b", re.I)),
    ("PIS", re.compile(r"\bPIS\b", re.I)),
    ("COFINS", re.compile(r"\bCOFINS\b", re.I)),
    ("ITBI", re.compile(r"\bITBI\b", re.I)),
    ("ISS", re.compile(r"\bISS\b|\bISSQN\b", re.I)),
    ("ICMS", re.compile(r"\bICMS\b", re.I)),
    ("Imposto de Renda", re.compile(r"imposto\s+de\s+renda", re.I)),
    ("CIDE", re.compile(r"\bCIDE\b", re.I)),
    ("IRRF", re.compile(r"\bIRRF\b", re.I)),
    ("IRPF", re.compile(r"\bIRPF\b", re.I)),
    ("IPI", re.compile(r"\bIPI\b", re.I)),
    ("Imposto de Importação",
     re.compile(r"imposto\s+(?:de|sobre\s+a)\s+importa[çc][ãa]o", re.I)),
    ("Contribuição Previdenciária", re.compile(r"contribui[çc][ãa]o\s+previdenci", re.I)),
    ("IOF", re.compile(r"\bIOF\b", re.I)),
    ("ITCMD", re.compile(r"\bITCMD\b|\bITCM\b", re.I)),
    ("IPTU", re.compile(r"\bIPTU\b", re.I)),
]

MESES = ["", "janeiro", "fevereiro", "março", "abril", "maio", "junho",
         "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


def latest_resource(slug: str) -> dict | None:
    api = f"{CKAN}/api/3/action/package_show?id={slug}"
    r = requests.get(api, headers=HEADERS, timeout=60)
    r.raise_for_status()
    res = r.json()["result"]["resources"]
    jsons = [x for x in res if (x.get("format") or "").upper() == "JSON"
             and re.match(r"\d{8}\.json", x.get("name") or "")]
    jsons.sort(key=lambda x: x["name"], reverse=True)
    return jsons[0] if jsons else None


def parse_pub_date(raw: str | None) -> datetime.date | None:
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", raw or "")
    if not m:
        return None
    try:
        return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def match_terms(ementa: str) -> list[str]:
    out = []
    for label, rx in TERMS:
        if label not in out and rx.search(ementa or ""):
            out.append(label)
    return out


def fetch() -> tuple[list[dict], str]:
    acordaos: list[dict] = []
    mes_yyyymm = ""
    for nome, slug in DATASETS.items():
        res = latest_resource(slug)
        if not res:
            print(f"  {nome}: sem arquivo")
            continue
        mes_yyyymm = max(mes_yyyymm, res["name"][:6])
        recs = requests.get(res["url"], headers=HEADERS, timeout=120).json()
        n = 0
        for rec in recs:
            ementa = rec.get("ementa") or ""
            if not ANCHOR_RE.search(ementa):
                continue
            rec["_orgao"] = rec.get("nomeOrgaoJulgador") or nome
            rec["_data"] = parse_pub_date(rec.get("dataPublicacao"))
            rec["_terms"] = match_terms(ementa)
            acordaos.append(rec)
            n += 1
        print(f"  {nome} ({res['name']}): {len(recs)} acórdãos, {n} tributários")
    return acordaos, mes_yyyymm


CSS = """
    body { font-family: -apple-system, system-ui, Segoe UI, sans-serif;
           max-width: 1150px; margin: 2em auto; padding: 0 1em; color: #222; line-height: 1.5; }
    h1 { border-bottom: 2px solid #155; padding-bottom: 0.3em; margin-bottom: 0.2em; }
    .topo { font-size: 0.9em; margin: 0.3em 0 0.8em; }
    .topo a { color: #0a6b3b; }
    .status { background: #f6f8fa; border: 1px solid #e1e4e8; border-radius: 6px;
              padding: 0.7em 1em; margin: 0.8em 0; font-size: 0.92em; color: #444; }
    .status div { margin: 0.15em 0; }
    .layout { display: flex; gap: 1.5em; align-items: flex-start; }
    .filtros { flex: 0 0 210px; position: sticky; top: 1em; font-size: 0.9em;
               max-height: calc(100vh - 2em); overflow-y: auto; }
    .conteudo { flex: 1; min-width: 0; }
    .filtros .grupo { margin-bottom: 1.3em; }
    .filtros h4 { margin: 0 0 0.4em; font-size: 0.95em; color: #333;
                  border-bottom: 1px solid #eee; padding-bottom: 0.2em; }
    .filtros ul { list-style: none; padding: 0; margin: 0; }
    .filtros li { padding: 0.3em 0.5em; border-radius: 4px; cursor: pointer; color: #0a6b3b; }
    .filtros li:hover { background: #e7f6ee; }
    .filtros li.ativo { background: #1a7f4b; color: #fff; }
    .filtros li span { color: #999; font-size: 0.85em; }
    .filtros li.ativo span { color: #cfe9da; }
    .filtros li.todos { color: #666; font-style: italic; }
    h2.data { margin-top: 1.4em; font-size: 1.1em; color: #333;
              border-bottom: 1px solid #eee; padding-bottom: 0.2em; }
    h2.data .qtd { color: #999; font-weight: normal; font-size: 0.85em; }
    .empty { color: #999; font-style: italic; padding: 2em 0; text-align: center; }
    .acordao { border: 1px solid #ddd; border-radius: 6px; padding: 1em 1.2em;
               margin: 1em 0; background: #fafafa; }
    .acordao h3 { margin: 0 0 0.3em 0; font-size: 1.0em; }
    .acordao .meta { color: #555; font-size: 0.88em; }
    .acordao .tags { margin: 0.4em 0; }
    .tag { display: inline-block; background: #e7f0ff; color: #0a4ea3; font-size: 0.78em;
           padding: 0.05em 0.55em; border-radius: 10px; margin: 0.15em 0.2em 0.15em 0; }
    .tag.org { background: #eee9ff; color: #5b3aa3; }
    .acordao .rotulo { font-weight: bold; color: #555; font-size: 0.85em; margin-top: 0.6em; }
    .acordao .texto { white-space: pre-wrap; font-size: 0.92em; color: #333; margin-top: 0.2em; }
    a { color: #0366d6; text-decoration: none; }
    a:hover { text-decoration: underline; }
    @media (max-width: 760px) { .layout { flex-direction: column; } .filtros { position: static; flex-basis: auto; } }
"""

JS = """
function aplicar(){
  var fo=document.querySelector('.f-orgao.ativo'); fo=fo?fo.getAttribute('data-val'):null;
  var ft=document.querySelector('.f-tributo.ativo'); ft=ft?ft.getAttribute('data-val'):null;
  var cards=document.querySelectorAll('.acordao');
  for(var i=0;i<cards.length;i++){
    var c=cards[i];
    var org=c.getAttribute('data-orgao')||'';
    var tr=(c.getAttribute('data-tributos')||'').split('|');
    var okO=!fo||org===fo; var okT=!ft||tr.indexOf(ft)>=0;
    c.style.display=(okO&&okT)?'':'none';
  }
  var hs=document.querySelectorAll('h2.data');
  for(var j=0;j<hs.length;j++){var h=hs[j],el=h.nextElementSibling,vis=false;
    while(el&&el.tagName!=='H2'){if(el.className&&(''+el.className).indexOf('acordao')>=0&&el.style.display!=='none')vis=true;el=el.nextElementSibling;}
    h.style.display=vis?'':'none';}
}
function toggle(el,cls){var a=el.classList.contains('ativo');var t=document.querySelectorAll('.'+cls);
  for(var i=0;i<t.length;i++)t[i].classList.remove('ativo');if(!a)el.classList.add('ativo');aplicar();}
function limpar(cls){var t=document.querySelectorAll('.'+cls);for(var i=0;i<t.length;i++)t[i].classList.remove('ativo');aplicar();}
"""


def render_item(rec: dict) -> str:
    e = html.escape
    classe = e(rec.get("descricaoClasse") or rec.get("siglaClasse") or "Acórdão")
    proc = e(str(rec.get("numeroProcesso") or rec.get("numeroRegistro") or "?"))
    orgao = e(rec.get("_orgao") or "")
    relator = e(rec.get("ministroRelator") or "?")
    ementa = e((rec.get("ementa") or "").strip())
    decisao = e((rec.get("decisao") or "").strip())
    terms = rec.get("_terms") or []
    tags = (f'<span class="tag org">{orgao}</span>'
            + "".join(f'<span class="tag">{e(t)}</span>' for t in terms))
    data_t = e("|".join(terms))
    dec_html = (f'<div class="rotulo">Decisão</div><div class="texto">{decisao}</div>'
                if decisao else "")
    return f"""<article class="acordao" data-orgao="{orgao}" data-tributos="{data_t}">
  <header>
    <h3>{classe} — {proc}</h3>
    <div class="meta">{orgao} · Relator(a): {relator}</div>
    <div class="tags">{tags}</div>
  </header>
  <div class="rotulo">Ementa</div>
  <div class="texto">{ementa}</div>
  {dec_html}
</article>"""


def _sidebar(titulo: str, counter: Counter, cls: str) -> str:
    e = html.escape
    itens = "".join(
        f'<li class="{cls}" data-val="{e(k)}" onclick="toggle(this,\'{cls}\')">'
        f'{e(k)} <span>({v})</span></li>' for k, v in counter.most_common())
    return (f'<div class="grupo"><h4>{titulo}</h4><ul>'
            f'<li class="todos" onclick="limpar(\'{cls}\')">Todos</li>{itens}</ul></div>')


def render_html(acordaos: list[dict], mes_yyyymm: str, now: datetime.datetime) -> str:
    org_counter: Counter = Counter()
    trib_counter: Counter = Counter()
    for a in acordaos:
        org_counter[a.get("_orgao") or "?"] += 1
        for t in a.get("_terms") or []:
            trib_counter[t] += 1

    groups: dict[datetime.date | None, list[dict]] = {}
    for a in acordaos:
        groups.setdefault(a.get("_data"), []).append(a)
    ordered = sorted([d for d in groups if d], reverse=True)
    if None in groups:
        ordered.append(None)

    sections = []
    for d in ordered:
        titulo = (f"{d.day} de {MESES[d.month]} de {d.year}" if d else "(sem data)")
        items = "\n".join(render_item(a) for a in groups[d])
        sections.append(f'<h2 class="data">{titulo} '
                        f'<span class="qtd">({len(groups[d])})</span></h2>\n{items}')
    body = ("\n".join(sections) if sections
            else '<p class="empty">Nenhum acórdão tributário no mês.</p>')

    if mes_yyyymm and len(mes_yyyymm) == 6:
        mes_nome = f"{MESES[int(mes_yyyymm[4:6])]}/{mes_yyyymm[:4]}"
    else:
        mes_nome = "?"
    sidebar = (_sidebar("Órgão julgador", org_counter, "f-orgao")
               + _sidebar("Tributo", trib_counter, "f-tributo")) if acordaos else ""
    now_str = now.strftime("%d/%m/%Y às %H:%M")
    return f"""<!DOCTYPE html>
<html lang="pt-br">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Acórdãos Tributários — STJ (mensal)</title>
  <style>{CSS}</style>
</head>
<body>
  <h1>Acórdãos Tributários — STJ</h1>
  <div class="topo">→ <a href="{LINK_MONOCRATICAS}">Ver decisões monocráticas (diário)</a></div>
  <div class="status">
    <div>📅 Mês de referência: <b>{mes_nome}</b> · <b>{len(acordaos)}</b> acórdãos tributários (1ª/2ª Turma + 1ª Seção).</div>
    <div>🤖 Atualizado em {now_str} · fonte: Dados Abertos do STJ.</div>
    <div>🪟 Acórdãos publicados mensalmente (com ~2-3 semanas de atraso). Use os filtros à esquerda.</div>
  </div>
  <div class="layout">
    <aside class="filtros">{sidebar}</aside>
    <main class="conteudo">{body}</main>
  </div>
  <script>{JS}</script>
</body>
</html>"""


def main() -> None:
    print("Baixando Dados Abertos do STJ (acórdãos)...")
    acordaos, mes = fetch()
    print(f"Total de acórdãos tributários: {len(acordaos)} (mês {mes})")
    now = datetime.datetime.now()
    OUTPUT_FILE.write_text(render_html(acordaos, mes, now), encoding="utf-8")
    print(f"HTML salvo: {OUTPUT_FILE}")
    import os
    import webbrowser
    if not os.environ.get("CI"):
        webbrowser.open(OUTPUT_FILE.as_uri())


if __name__ == "__main__":
    main()
