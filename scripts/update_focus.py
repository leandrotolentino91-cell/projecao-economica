"""Baixa as expectativas anuais do Boletim Focus (API Olinda/BCB) e grava data/focus.json."""
import json, datetime as dt, sys, time, requests
from pathlib import Path

BASE = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativasMercadoAnuais"
# chave do painel -> nomes possíveis do indicador no Focus (o BCB mudou alguns nomes ao longo do tempo)
IND = {
    "ipca":   ["IPCA"],
    "selic":  ["Selic", "Meta para taxa over-selic"],
    "pib":    ["PIB Total"],
    "cambio": ["Câmbio", "Taxa de câmbio"],
}
OUT = Path(__file__).resolve().parents[1] / "data" / "focus.json"

def baixa(nome):
    from urllib.parse import quote
    linhas, skip, passo = [], 0, 50000
    filtro = quote(f"Indicador eq '{nome}'")
    while True:
        url = (f"{BASE}?$format=json&$top={passo}&$skip={skip}&$filter={filtro}"
               "&$select=Indicador,IndicadorDetalhe,Data,DataReferencia,Mediana,baseCalculo")
        for tentativa in range(3):
            try:
                r = requests.get(url, timeout=180); r.raise_for_status(); break
            except Exception:
                if tentativa == 2: raise
                time.sleep(5)
        lote = r.json().get("value", [])
        linhas += [l for l in lote if not l.get("IndicadorDetalhe")]
        if len(lote) < passo: return linhas
        skip += passo

def main():
    hoje = dt.date.today(); ano = hoje.year
    out = {"atualizado": hoje.isoformat(), "fonte": "BCB - Sistema de Expectativas (Focus), mediana, base 30 dias", "indicadores": {}}
    ultima_data = ""
    for chave, nomes in IND.items():
        porano = {}  # ano_ref -> {data: mediana}
        for prioridade, nome in enumerate(nomes):
            try:
                linhas = baixa(nome)
            except Exception as e:
                print(f"[focus] falha em {nome}: {e}", file=sys.stderr); continue
            for l in linhas:
                if l.get("baseCalculo", 0) not in (0, None) or l.get("Mediana") is None: continue
                try: ref = int(str(l["DataReferencia"])[:4])
                except Exception: continue
                d = l["Data"][:10]
                slot = porano.setdefault(ref, {})
                if d not in slot or prioridade == 0:   # o nome principal prevalece
                    slot[d] = round(float(l["Mediana"]), 4)
        if not porano:
            print(f"[focus] sem dados para {chave}", file=sys.stderr); continue
        anual, semanal, ultimo = {}, {}, {}
        for ref, serie in porano.items():
            datas = sorted(serie)
            h0 = next((serie[d] for d in datas if d >= f"{ref}-01-01"), None)
            h1 = next((serie[d] for d in datas if d >= f"{ref-1}-01-01"), None)
            anual[str(ref)] = {"h0": h0, "h1": h1}
            if ano <= ref <= ano + 3:
                pts = [[d, serie[d]] for d in datas if d >= f"{ano-1}-01-01"]
                # reduz para 1 ponto por semana (última leitura de cada semana ISO)
                sem = {}
                for d, v in pts:
                    y, w, _ = dt.date.fromisoformat(d).isocalendar(); sem[(y, w)] = [d, v]
                semanal[str(ref)] = [sem[k] for k in sorted(sem)]
                ultimo[str(ref)] = serie[datas[-1]]
                ultima_data = max(ultima_data, datas[-1])
        out["indicadores"][chave] = {"anual": anual, "semanal": semanal, "ultimo": ultimo}
    if not out["indicadores"]:
        sys.exit("[focus] nenhum indicador baixado; mantendo arquivo anterior")
    out["data_pesquisa"] = ultima_data
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[focus] ok, pesquisa de {ultima_data}")

if __name__ == "__main__":
    main()
