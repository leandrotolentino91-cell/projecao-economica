"""Coleta manchetes de mercado (Google News RSS) por indicador e classifica o sinal de cada uma.
Grava data/noticias.json. Sinal: +1 pressiona o indicador para cima, -1 para baixo, 0 neutro."""
import json, re, sys, unicodedata, datetime as dt, email.utils
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote
import requests

OUT = Path(__file__).resolve().parents[1] / "data" / "noticias.json"
BUSCAS = {
    "ipca":   ["IPCA inflação", "inflação Brasil expectativa", "preço gasolina Petrobras reajuste"],
    "selic":  ["Selic Copom", "Banco Central juros Galípolo", "curva de juros DI"],
    "pib":    ["PIB Brasil atividade econômica", "IBC-Br varejo indústria serviços"],
    "cambio": ["dólar real câmbio", "dólar fecha"],
    "fiscal": ["arcabouço fiscal déficit dívida pública", "Haddad meta fiscal"],
}
SINAIS = {
    "ipca": (["acima do esperado", "acelera", "sobe", "alta da inflacao", "press", "reajuste", "aumento", "dispara", "desancor", "piora", "encarece", "revisa inflacao para cima", "inflacao de ate", "mais cara"],
             ["abaixo do esperado", "desacelera", "inflacao recua", "inflacao cai", "queda da inflacao", "queda de preco", "deflacao", "alivio", "arrefece", "mais barat", "reducao no preco"]),
    "selic": (["alta da selic", "eleva a selic", "aperto", "manutencao", "mantem", "pausa", "interromp", "fim do ciclo", "cautela", "conservador"],
              ["corte", "reduz a selic", "queda da selic", "afrouxamento", "flexibiliz", "cortar", "baixa a selic"]),
    "pib":   (["cresce", "acima do esperado", "avanca", "surpreende positiv", "forte", "expansao", "alta de"],
              ["recua", "contrai", "abaixo do esperado", "recessao", "desacelera", "queda", "fraco", "perde folego", "retracao", "para baixo", "pressiona"]),
    "cambio":(["dolar sobe", "dolar dispara", "dolar avanca", "alta do dolar", "dolar fecha em alta", "real se desvaloriza", "real perde", "maior alta", "dolar tem alta", "dolar a r$ 5,5", "dolar a r$ 6"],
              ["dolar cai", "dolar recua", "queda do dolar", "dolar fecha em queda", "real se valoriza", "real ganha"]),
    "fiscal":(["deficit", "piora", "rombo", "gasto", "estoura", "dispara", "risco fiscal"],
              ["superavit", "ajuste", "corte de gastos", "melhora", "cumpre a meta", "receita recorde"]),
}

def norm(t):
    t = unicodedata.normalize("NFKD", t.lower())
    return "".join(c for c in t if not unicodedata.combining(c))

def sinal(ind, titulo):
    t = " " + norm(titulo) + " "
    up = sum(w in t for w in SINAIS[ind][0]); dn = sum(w in t for w in SINAIS[ind][1])
    return (up > dn) - (dn > up)

def rss(q):
    url = f"https://news.google.com/rss/search?q={quote(q + ' when:7d')}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    r = requests.get(url, timeout=30); r.raise_for_status()
    for it in ET.fromstring(r.content).iter("item"):
        tit = it.findtext("title") or ""
        fonte = it.findtext("source") or (tit.rsplit(" - ", 1)[-1] if " - " in tit else "")
        tit = tit.rsplit(" - ", 1)[0] if " - " in tit else tit
        try: d = email.utils.parsedate_to_datetime(it.findtext("pubDate")).astimezone(dt.timezone.utc)
        except Exception: continue
        yield {"t": tit.strip(), "fonte": fonte.strip(), "data": d.isoformat(timespec="minutes"), "link": it.findtext("link")}

def main():
    agora = dt.datetime.now(dt.timezone.utc)
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"indicadores": {}}
    out = {"atualizado": agora.isoformat(timespec="minutes"), "fonte": "Google News (RSS), últimos 7 dias", "indicadores": {}}
    for ind, qs in BUSCAS.items():
        itens = {x["t"]: x for x in old.get("indicadores", {}).get(ind, {}).get("itens", [])}
        for q in qs:
            try:
                for x in rss(q): itens.setdefault(x["t"], x)
            except Exception as e:
                print(f"[noticias] falha {q}: {e}", file=sys.stderr)
        lim = (agora - dt.timedelta(days=7)).isoformat()
        lista = sorted((x for x in itens.values() if x["data"] >= lim), key=lambda x: x["data"], reverse=True)[:80]
        for x in lista: x["sinal"] = sinal(ind, x["t"])
        # índice ponderado pela recência (meia-vida de 2 dias), entre -1 e 1
        num = den = 0.0
        for x in lista:
            idade = (agora - dt.datetime.fromisoformat(x["data"])).total_seconds() / 86400
            w = 0.5 ** (idade / 2); num += w * x["sinal"]; den += w
        out["indicadores"][ind] = {"indice": round(num / den, 3) if den else 0, "n": len(lista),
                                   "alta": sum(x["sinal"] > 0 for x in lista), "baixa": sum(x["sinal"] < 0 for x in lista), "itens": lista}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("[noticias] ok", {k: (v["n"], v["indice"]) for k, v in out["indicadores"].items()})

if __name__ == "__main__":
    main()
