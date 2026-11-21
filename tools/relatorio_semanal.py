#!/usr/bin/env python3
"""Relatório semanal de métricas das contas (API oficial da Meta). Grava relatorios/AAAA-MM-DD_<conta>.md e .json.
Uso: python3 tools/relatorio_semanal.py [--dias 7] [--conta tuca]"""
import datetime as dt
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import meta_ig as M

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def fmt_ms(v):
    return f'{v / 1000:.1f}s' if isinstance(v, (int, float)) else '-'


def relatorio(conta, dias=7):
    ig = M.ig_id(conta)
    c = M.conta(ig, dias)
    ms = M.midias(ig, dias)
    hoje = dt.date.today().isoformat()
    pasta = os.path.join(RAIZ, 'relatorios')
    os.makedirs(pasta, exist_ok=True)
    ant = sorted(glob.glob(os.path.join(pasta, f'*_{conta}.json')))
    anterior = json.load(open(ant[-1], encoding='utf-8')) if ant else None
    seg = c['info'].get('followers_count')
    delta = f' ({seg - anterior["seguidores"]:+d} desde {anterior["data"]})' if anterior and seg is not None else ''
    linhas = [f'# {conta} (@{c["info"].get("username")}): semana até {hoje}', '',
              f'- Seguidores: **{seg}**{delta} · Publicações: {c["info"].get("media_count")}',
              '- Conta nos últimos %d dias: ' % dias + ', '.join(f'{k} = {v}' for k, v in c['metricas'].items()), '',
              '| Data | Tipo | Views | Alcance | Tempo médio | Curtidas | Coment. | Salvos | Envios | Link |', '|---|---|---|---|---|---|---|---|---|---|']
    for m in sorted(ms, key=lambda m: m['timestamp']):
        i = m['insights']
        linhas.append(f'| {m["timestamp"][:10]} | {m.get("media_product_type", m["media_type"])} | {i.get("views", "-")} | {i.get("reach", "-")} | {fmt_ms(i.get("ig_reels_avg_watch_time"))} | {i.get("likes", m.get("like_count", "-"))} | {i.get("comments", m.get("comments_count", "-"))} | {i.get("saved", "-")} | {i.get("shares", "-")} | {m["permalink"]} |')
    if ms:
        melhor = max(ms, key=lambda m: m['insights'].get('reach') or 0)
        linhas += ['', f'Maior alcance: {melhor["permalink"]} ({melhor["insights"].get("reach")}).']
    txt = '\n'.join(linhas) + '\n'
    open(os.path.join(pasta, f'{hoje}_{conta}.md'), 'w', encoding='utf-8').write(txt)
    json.dump(dict(data=hoje, seguidores=seg, conta=c, midias=ms), open(os.path.join(pasta, f'{hoje}_{conta}.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    return txt


if __name__ == '__main__':
    a = sys.argv[1:]
    dias = int(a[a.index('--dias') + 1]) if '--dias' in a else 7
    contas = [a[a.index('--conta') + 1]] if '--conta' in a else [k for k, v in M.carregar_contas().items() if v.get('ig_id')]
    for k in contas:
        print(relatorio(k, dias))
