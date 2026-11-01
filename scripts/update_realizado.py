"""Baixa os valores realizados no SGS/BCB e grava data/realizado.json.
Séries: 432 Meta Selic (fim de ano), 13522 IPCA 12m (dezembro), 7326 PIB real % a.a., 3696 R$/US$ fim de período (dezembro)."""
import json, datetime as dt, sys, time, requests
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "realizado.json"
SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{}/dados"
INICIO = 2005

def sgs(cod, ini, fim):
    for t in range(4):
        try:
            r = requests.get(SGS.format(cod), params={"formato": "json", "dataInicial": ini, "dataFinal": fim}, timeout=120)
            r.raise_for_status(); break
        except Exception:
            if t == 3: raise
            time.sleep(8)
    return [(dt.datetime.strptime(x["data"], "%d/%m/%Y").date(), float(x["valor"])) for x in r.json()]

def em_blocos(cod):
    hoje = dt.date.today(); pts = []
    for a in range(INICIO, hoje.year + 1, 5):  # séries diárias aceitam no máx. 10 anos por consulta
        pts += sgs(cod, f"01/01/{a}", f"31/12/{min(a+4, hoje.year)}")
    return pts

def fim_de_ano(pts, so_dezembro=False):
    res = {}
    for d, v in sorted(pts):
        if so_dezembro and d.month != 12: continue
        res[str(d.year)] = round(v, 4)
    return res

def main():
    hoje = dt.date.today()
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    out = {"atualizado": hoje.isoformat(), "fonte": "BCB/SGS (432, 13522, 7326, 3696)"}
    tarefas = {
        "selic":  lambda: fim_de_ano([p for p in em_blocos(432)]),
        "ipca":   lambda: fim_de_ano(sgs(13522, f"01/01/{INICIO}", hoje.strftime("%d/%m/%Y")), so_dezembro=True),
        "pib":    lambda: {str(d.year): round(v, 2) for d, v in sgs(7326, f"01/01/{INICIO}", hoje.strftime("%d/%m/%Y"))},
        "cambio": lambda: fim_de_ano(sgs(3696, f"01/01/{INICIO}", hoje.strftime("%d/%m/%Y")), so_dezembro=True),
    }
    for k, f in tarefas.items():
        try:
            serie = f()
            if k == "selic":  # ano corrente ainda não fechou: guarda como 'parcial'
                serie.pop(str(hoje.year), None) if hoje.month < 12 or hoje.day < 31 else None
            out[k] = serie
        except Exception as e:
            print(f"[realizado] falha em {k}: {e}", file=sys.stderr)
            out[k] = old.get(k, {})
    # Trajetória observada (para comparar com as revisões das projeções ao longo do tempo)
    ini = f"01/01/{hoje.year-4}"; fim = hoje.strftime("%d/%m/%Y")
    traj = old.get("trajetoria", {})
    def tenta(chave, f):
        try: traj[chave] = f()
        except Exception as e: print(f"[realizado] trajetória {chave} falhou: {e}", file=sys.stderr)
    tenta("cambio", lambda: [[d.isoformat(), round(v, 4)] for d, v in sgs(1, ini, fim)])
    def selic_passos():
        pts, ult = [], None
        for d, v in sgs(432, ini, fim):
            if v != ult: pts.append([d.isoformat(), v]); ult = v
        if pts and pts[-1][0] != hoje.isoformat(): pts.append([hoje.isoformat(), ult])
        return pts
    tenta("selic", selic_passos)
    tenta("ipca", lambda: [[d.isoformat(), round(v, 2)] for d, v in sgs(13522, ini, fim)])
    def pib_4t():
        r = requests.get("https://apisidra.ibge.gov.br/values/t/5932/n1/all/v/6562/p/all/c11255/90707", timeout=120)
        r.raise_for_status(); pts = []
        for x in r.json()[1:]:
            per = x.get("D3C", ""); v = x.get("V")
            if len(per) != 6 or v in (None, "...", "-"): continue
            a, t = int(per[:4]), int(per[4:])
            if a < hoje.year - 4: continue
            fimtri = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}[t]
            pts.append([f"{a}-{fimtri}", float(v)])
        return pts
    tenta("pib", pib_4t)
    out["trajetoria"] = traj
    out["parcial"] = {k: (v[-1] if v else None) for k, v in traj.items()}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("[realizado] ok")

if __name__ == "__main__":
    main()
