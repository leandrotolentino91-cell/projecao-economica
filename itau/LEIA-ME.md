# Relatórios Itaú BBA

Os PDFs do Itaú não são versionados (o relatório proíbe redistribuição e o repositório é público).
O robô baixa o Cenário Macro novo, extrai os números para `data/` e descarta o PDF.
Relatórios antigos: rode `python scripts/update_itau.py --sem-download` localmente com os PDFs nesta pasta,
ou cole os números em `data/itau_manual.csv`. Só os JSON de `data/` sobem para o GitHub.
