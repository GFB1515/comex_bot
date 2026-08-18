# Comex Bot

Bot em Streamlit para consultar exportações por município usando a API do Comex Stat/MDIC.

## Rodar no computador

1. Instale Python 3.11 ou superior.
2. Abra o terminal nesta pasta.
3. Execute:

```bash
pip install -r requirements.txt
streamlit run app.py
```

O navegador abrirá a tela do bot.

## Filtros

- Período inicial/final
- País de destino
- Município
- SH4
- Detalhamento mensal

O resultado calcula:

US$/kg = FOB (US$) / Kg líquido

## Observação

A API do Comex Stat é atualizada mensalmente e os dados mais recentes podem depender do calendário oficial de divulgação.
