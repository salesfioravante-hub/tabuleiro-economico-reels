# tools/: publicar e medir pela API oficial da Meta

- `meta_ig.py`: cliente (Reels, imagens, carrosséis, cota, métricas). `contas.json`: IDs das 3 contas.
- `publicar_calendarios.py`: publica o devido a partir de `calendarios/<conta>.csv` (simulação por padrão; `--executar` publica).
- `relatorio_semanal.py`: relatório por conta em `relatorios/`.
Sem token no código: o proxy da sessão injeta a credencial de graph.facebook.com. Fora daqui, use a variável META_TOKEN.
Testado só com transporte simulado até a primeira credencial real.
