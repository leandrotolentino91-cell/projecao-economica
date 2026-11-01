# Painel Projeção Econômica – Brasil

Painel online que compara **projeções do Boletim Focus e do Itaú BBA com o realizado** e combina as duas fontes
numa "projeção do painel", ponderada pela precisão histórica de cada uma.

## Como funciona
| Parte | O que faz |
|---|---|
| `index.html` | O painel (GitHub Pages). Lê os arquivos de `data/`. |
| `scripts/update_focus.py` | Baixa as medianas do Focus pela API Olinda do BCB. |
| `scripts/update_realizado.py` | Baixa Selic, IPCA, PIB e câmbio realizados no SGS/BCB. |
| `scripts/update_itau.py` | Procura novos PDFs do Cenário Macro Brasil no site do Itaú e lê a tabela "Dados e projeções" de todos os PDFs em `itau/`. |
| `.github/workflows/atualizar.yml` | Roda tudo sozinho: segunda 09:40 (Focus) e dias úteis 18:15 (Itaú), e sempre que você envia um PDF. |

## Publicar (uma vez)
1. Em github.com clique em **New repository** → nome `projecao-economica` → Public → Create.
2. Na página do repositório: **uploading an existing file** → arraste todo o conteúdo desta pasta (inclusive `.github`) → Commit.
3. **Settings → Pages** → Source: *Deploy from a branch* → Branch `main` / `(root)` → Save.
4. **Actions** → habilite os workflows → *Atualizar dados* → **Run workflow** (a 1ª execução troca a semente pelos dados oficiais do BCB).
5. O painel fica em `https://SEU-USUARIO.github.io/projecao-economica/`.

## Incluir histórico do Itaú
Os PDFs do Itaú ficam só no seu computador (o relatório proíbe redistribuição). Coloque-os em `itau/`,
rode `python scripts/update_itau.py --sem-download` e suba apenas os arquivos de `data/`.
Projeções sem PDF podem ser coladas em `data/itau_manual.csv`.

Painel de estudo pessoal. Não é recomendação de investimento.
