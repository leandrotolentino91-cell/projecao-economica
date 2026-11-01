"""Itaú BBA - Cenário Macro Brasil.
1) Tenta baixar automaticamente novos PDFs do Cenário Macro publicados pelo Itaú.
2) Lê todos os PDFs da pasta itau/ (você também pode subir PDFs ali manualmente, inclusive antigos)
   e extrai a tabela "Dados e projeções".
Grava data/itau_historico.json (uma 'safra' por relatório) e data/itau_ultimo.json (tabela completa do mais recente)."""
import json, re, subprocess, sys, datetime as dt
from pathlib import Path
import requests

RAIZ = Path(__file__).resolve().parents[1]
PASTA = RAIZ / "itau"
HIST = RAIZ / "data" / "itau_historico.json"
ULT = RAIZ / "data" / "itau_ultimo.json"
PAGINAS = [
    "https://www.itau.com.br/itaubba-pt/analises-economicas/projecoes",
    "https://www.itau.com.br/itaubba-pt/analises-economicas/publicacoes/macro-brasil",
    "https://www.itau.com.br/itaubba-pt/analises-economicas",
]
LINK = re.compile(r'https://macroattachment\.cloud\.itau\.com\.br/attachments/[\w-]+/[^"\'\s<>]+?\.pdf', re.I)
MESES = {m: i+1 for i, m in enumerate("janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro".split())}
MESES_EN = {m: i+1 for i, m in enumerate("january february march april may june july august september october november december".split())}
CHAVES = [  # (chave, regex do rótulo da linha em PT ou EN)
    ("pib",        r"(Crescimento real do PIB|Real GDP growth)"),
    ("ipca",       r"^\s*IPCA\b"),
    ("igpm",       r"IGP.M"),
    ("selic",      r"Selic"),
    ("cambio",     r"BRL\s*/\s*USD\s*-\s*(final|end|eop)"),
    ("cambio_med", r"BRL\s*/\s*USD\s*-\s*(média|average)"),
    ("desemprego", r"(Desemprego.*fim|Unemployment rate.*(year-end|end|eop))"),
    ("primario",   r"(Resultado primário|Primary balance)"),
    ("divida",     r"(Dívida bruta|Gross public debt)"),
]

def baixa_novos():
    PASTA.mkdir(exist_ok=True)
    vistos = {p.name for p in PASTA.glob("*.pdf")}
    hdr = {"User-Agent": "Mozilla/5.0 (painel-projecao-economica)"}
    for url in PAGINAS:
        try:
            html = requests.get(url, headers=hdr, timeout=60).text
        except Exception as e:
            print(f"[itau] não consegui abrir {url}: {e}", file=sys.stderr); continue
        for link in set(LINK.findall(html)):
            nome = link.rsplit("/", 1)[-1]
            if not re.search(r"(CenarioMacro|MacroScenario).*(BRASIL|BRAZIL)", nome, re.I): continue
            if nome in vistos: continue
            try:
                r = requests.get(link, headers=hdr, timeout=120); r.raise_for_status()
                (PASTA / nome).write_bytes(r.content); vistos.add(nome)
                print(f"[itau] novo relatório baixado: {nome}")
            except Exception as e:
                print(f"[itau] falha ao baixar {link}: {e}", file=sys.stderr)

def num(s, en=False):
    s = s.strip().replace("\u2212", "-")
    if en: return float(s.replace(",", ""))
    return float(s.replace(".", "").replace(",", "."))

def data_relatorio(txt):
    m = re.search(r"(\d{1,2}) de ([a-zç]+) de (\d{4})", txt[:600], re.I)
    if m and m.group(2).lower() in MESES: return dt.date(int(m.group(3)), MESES[m.group(2).lower()], int(m.group(1)))
    m = re.search(r"([A-Z][a-z]+) (\d{1,2}), (\d{4})", txt[:600])
    if m and m.group(1).lower() in MESES_EN: return dt.date(int(m.group(3)), MESES_EN[m.group(1).lower()], int(m.group(2)))
    return None

def le_pdf(caminho):
    txt = subprocess.run(["pdftotext", "-layout", str(caminho), "-"], capture_output=True, text=True).stdout
    data = data_relatorio(txt)
    en = bool(re.match(r"\s*Macro scenario", txt)) or (not re.match(r"\s*Cen[aá]rio", txt) and bool(re.search(r"Current\s+Previous", txt)))
    linhas = txt.splitlines()
    # cabeçalho de anos: linha com vários 20xx e pelo menos um 20xxP/E
    ini = next((i for i, l in enumerate(linhas) if len(re.findall(r"\b20\d\d[PEF]?\b", l)) >= 4 and re.search(r"20\d\d[PEF]", l)), None)
    if ini is None or data is None: return None
    anos = re.findall(r"\b(20\d\d)([PEF]?)\b", linhas[ini])
    hist = [int(a) for a, p in anos if not p]; proj = [int(a) for a, p in anos if p]
    bloco = "\n".join(linhas[ini: ini+40])
    en = len(re.findall(r"\d\.\d{1,2}(?!\d)", bloco)) > len(re.findall(r"\d,\d{1,2}(?!\d)", bloco))
    tabela, proj_out = [], {}
    for l in linhas[ini+1: ini+80]:
        if re.match(r"\s*(Fonte|Source)", l): break
        m = re.match(r"^\s*(.+?)\s{2,}((?:-?[\d.,]+|-)(?:\s+(?:-?[\d.,]+|-))+)\s*$", l)
        if not m:
            r = l.strip()
            if r and not re.search(r"\d", r) and len(r) < 40 and r not in ("Atual Anterior", "Current Previous"):
                tabela.append({"secao": r})
            continue
        rot = m.group(1).strip()
        try: vals = [None if v == "-" else num(v, en) for v in m.group(2).split()]
        except ValueError: continue
        nh, np_ = len(hist), len(proj)
        if len(vals) == nh + 2*np_:
            h, p = vals[:nh], vals[nh:]; atual = p[0::2]; ant = p[1::2]
        elif len(vals) == nh + np_:
            h, atual, ant = vals[:nh], vals[nh:], [None]*np_
        elif len(vals) == nh + 2*np_ - 1:   # último ano projetado só com "Atual"
            h, p = vals[:nh], vals[nh:] + [None]; atual = p[0::2]; ant = p[1::2]
        else:
            continue
        tabela.append({"rotulo": rot, "hist": h, "atual": atual, "anterior": ant})
        for chave, rx in CHAVES:
            if chave not in proj_out and re.search(rx, rot, re.I):
                proj_out[chave] = {str(a): v for a, v in zip(proj, atual) if v is not None}
                proj_out.setdefault("_realizado", {})[chave] = {str(a): v for a, v in zip(hist, h)}
    # Layout antigo (2024–25): rótulos em inglês sobrepostos quebram as linhas. Pega os últimos 2*n números do bloco.
    np_ = len(proj)
    for chave, rx in CHAVES:
        if chave in proj_out: continue
        for i, l in enumerate(linhas[ini+1: ini+90]):
            if re.match(r"\s*(Fonte|Source)", l): break
            if re.search(rx, l, re.I):
                for l2 in linhas[ini+1+i: ini+1+i+4]:
                    toks = re.findall(r"(?<![\w.,])-?\d{1,3}(?:[.,]\d{1,3})*(?![\w])", l2)
                    if len(toks) >= 2*np_:
                        try: vals = [num(t, en) for t in toks[-2*np_:]]
                        except ValueError: continue
                        proj_out[chave] = {str(a): v for a, v in zip(proj, vals[0::2])}
                        break
                break
    if not proj_out: return None
    return {"data": data.isoformat(), "arquivo": caminho.name, "anos_hist": hist, "anos_proj": proj,
            "proj": {k: v for k, v in proj_out.items() if not k.startswith("_")},
            "realizado_no_relatorio": proj_out.get("_realizado", {}), "tabela": tabela}

def main():
    if "--sem-download" not in sys.argv: baixa_novos()
    hist = json.loads(HIST.read_text(encoding="utf-8")) if HIST.exists() else {"safras": []}
    por_data = {s["data"]: s for s in hist["safras"]}
    ultimo = None
    for pdf in sorted(PASTA.glob("*.pdf")):
        try: r = le_pdf(pdf)
        except Exception as e:
            print(f"[itau] erro lendo {pdf.name}: {e}", file=sys.stderr); continue
        if not r:
            print(f"[itau] {pdf.name}: tabela não encontrada (ignorado)"); continue
        # relatório PT tem prioridade sobre a versão EN da mesma data
        if r["data"] in por_data and por_data[r["data"]].get("origem") == "pdf" and re.search(r"(Scenario|BRAZIL)", pdf.name): continue
        por_data[r["data"]] = {"data": r["data"], "origem": "pdf", "arquivo": r["arquivo"], "proj": r["proj"]}
        if not ultimo or r["data"] >= ultimo["data"]: ultimo = r
    csvp = RAIZ / "data" / "itau_manual.csv"
    if csvp.exists():
        import csv
        linhas = [l for l in csvp.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
        for row in csv.DictReader(linhas):
            try:
                d = row["data"].strip(); v = float(row["valor"].replace(",", "."))
            except Exception: continue
            s = por_data.setdefault(d, {"data": d, "origem": "csv", "proj": {}})
            if s.get("origem") == "pdf": continue
            s["proj"].setdefault(row["indicador"].strip(), {})[row["ano"].strip()] = v
    hist["safras"] = sorted(por_data.values(), key=lambda s: s["data"])
    hist["atualizado"] = dt.date.today().isoformat()
    HIST.write_text(json.dumps(hist, ensure_ascii=False, indent=1), encoding="utf-8")
    if ultimo:
        ant = json.loads(ULT.read_text(encoding="utf-8")) if ULT.exists() else {}
        if ultimo["data"] >= ant.get("data", ""):
            ULT.write_text(json.dumps(ultimo, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[itau] {len(hist['safras'])} safras no histórico")

if __name__ == "__main__":
    main()
