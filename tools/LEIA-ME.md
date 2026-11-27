# tools/: publicar e medir pela API oficial da Meta

- `meta_ig.py`: cliente (Reels, imagens, carrosséis, cota, métricas). `contas.json`: IDs das 3 contas.
- `publicar_calendarios.py`: publica o devido a partir de `calendarios/<conta>.csv` (simulação por padrão; `--executar` publica).
- `relatorio_semanal.py`: relatório por conta em `relatorios/`.
Sem token no código: o proxy da sessão injeta a credencial de graph.facebook.com. Fora daqui, use a variável META_TOKEN.
Testado só com transporte simulado até a primeira credencial real.

## Cadência (desde 27/11/2026): 3 posts por semana
- **Segunda, quarta e sexta, 18:55 BRT** (gatilho único): 2 Reels de economia atemporal (fila, na ordem do id) + 1 notícia de alto impacto.
- A notícia da semana é uma linha com `quando` = `AAAA-MM-DD 18:00` (quarta). Ela sai antes da fila e não consome o limite da fila.
- Fluxo da notícia: terça de manhã pesquisa e 3 candidatas, aprovação do tema, do roteiro e do vídeo, agenda para quarta, reconferência às 10:00 da quarta (status mais recente do fato: sanção, votação, cotação).
- Sem notícia agendada, o disparo da quarta publica o próximo Reel da fila.
- Disparo com mais de 3 h de atraso (depois das 22:00 BRT) não publica: avisa.
