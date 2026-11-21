#!/usr/bin/env python3
"""Publica o que está no ponto, para cada conta, a partir de calendarios/<conta>.csv, pela API oficial da Meta.

Colunas: id,tipo,quando,arquivos,legenda,thumb_offset_ms,status,data_postagem,media_id,container_id,obs
  tipo: reel | imagem | carrossel      arquivos: URLs públicas separadas por | (carrossel: 2 a 10; .mp4 = vídeo)
  quando: 'AAAA-MM-DD HH:MM' (Brasília) ou vazio = fila (1 por dia, na ordem do id)
  status: pendente | postado | incerto | arquivado
Regras de segurança: nunca publica se a conta tem linha 'incerto'; grava o container antes de publicar;
em timeout/erro de rede marca 'incerto' e consulta o container na próxima execução (sem duplicar).
Uso:  python3 tools/publicar_calendarios.py            (simulação: só mostra o que faria)
      python3 tools/publicar_calendarios.py --executar [--conta tuca]
"""
import csv
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import meta_ig as M

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAMPOS = ['id', 'tipo', 'quando', 'arquivos', 'legenda', 'thumb_offset_ms', 'status', 'data_postagem', 'media_id', 'container_id', 'obs']
BRT = dt.timezone(dt.timedelta(hours=-3))


def agora():
    return dt.datetime.now(BRT)


def ler(conta):
    p = os.path.join(RAIZ, 'calendarios', f'{conta}.csv')
    if not os.path.exists(p):
        return p, []
    return p, list(csv.DictReader(open(p, encoding='utf-8')))


def gravar(p, linhas):
    w = csv.DictWriter(open(p, 'w', newline='', encoding='utf-8'), fieldnames=CAMPOS, lineterminator='\n')
    w.writeheader()
    w.writerows([{k: l.get(k, '') for k in CAMPOS} for l in linhas])


def devida(l, agora_):
    if l['status'] != 'pendente':
        return False
    if l.get('quando'):
        return dt.datetime.strptime(l['quando'], '%Y-%m-%d %H:%M').replace(tzinfo=BRT) <= agora_
    return True


def resolver_incertos(linhas):
    """incerto com container: consulta o status; PUBLISHED => marca postado (sem republicar)"""
    for l in linhas:
        if l['status'] == 'incerto' and l.get('container_id'):
            try:
                s = M.status_container(l['container_id'])
            except M.MetaErro:
                continue
            if s.get('status_code') == 'PUBLISHED':
                l.update(status='postado', data_postagem=l.get('data_postagem') or agora().strftime('%Y-%m-%d'), obs='confirmado pelo container')
            elif s.get('status_code') in ('ERROR', 'EXPIRED'):
                l.update(status='pendente', obs=f'container {s.get("status_code")}: republicar')


def rodar(conta, executar):
    ig = M.ig_id(conta)
    p, linhas = ler(conta)
    if not linhas:
        return f'{conta}: calendário vazio'
    resolver_incertos(linhas)
    gravar(p, linhas)
    if any(l['status'] == 'incerto' for l in linhas):
        gravar(p, linhas)
        return f'{conta}: há post incerto sem resolução: nada publicado'
    hoje = agora().strftime('%Y-%m-%d')
    fila_feita = any(l['status'] == 'postado' and l['data_postagem'] == hoje and not l.get('quando') for l in linhas)
    # limite de 1 por dia vale só para a fila; posts com horário fixo ('quando') ignoram o limite
    pend = sorted([l for l in linhas if devida(l, agora()) and (l.get('quando') or not fila_feita)], key=lambda l: (l.get('quando') or '9999', int(l['id']) if str(l['id']).isdigit() else 0))
    if not pend and fila_feita:
        return f'{conta}: já publicou a fila de hoje'
    if not pend:
        return f'{conta}: nada devido agora ({sum(l["status"] == "pendente" for l in linhas)} pendentes)'
    l = pend[0]
    if not executar:
        return f'{conta}: [simulação] publicaria {l["tipo"]} id={l["id"]}: {l["legenda"].splitlines()[0][:60]}'
    arq = [a for a in l['arquivos'].split('|') if a]

    def gravar_container(c):
        l['container_id'] = c
        gravar(p, linhas)
    try:
        if l['tipo'] == 'reel':
            r = M.publicar_reel(ig, arq[0], l['legenda'], int(l['thumb_offset_ms']) if l.get('thumb_offset_ms') else None, on_container=gravar_container)
        elif l['tipo'] == 'imagem':
            r = M.publicar_imagem(ig, arq[0], l['legenda'], on_container=gravar_container)
        else:
            r = M.publicar_carrossel(ig, [(a, 'VIDEO' if a.lower().split('?')[0].endswith(('.mp4', '.mov')) else 'IMAGE') for a in arq], l['legenda'], on_container=gravar_container)
    except (TimeoutError, OSError) as e:       # resultado desconhecido: não repetir
        l.update(status='incerto', data_postagem=hoje, obs=f'timeout/rede: {e}')
        gravar(p, linhas)
        return f'{conta}: id={l["id"]} INCERTO ({e}); container {l.get("container_id")}'
    except M.MetaErro as e:
        l['obs'] = f'erro: {e}'
        gravar(p, linhas)
        return f'{conta}: id={l["id"]} ERRO {e}'
    l.update(status='postado', data_postagem=hoje, media_id=r['media_id'], container_id=r['container_id'], obs=r.get('permalink', ''))
    gravar(p, linhas)
    return f'{conta}: id={l["id"]} POSTADO {r["media_id"]} {r.get("permalink")}'


def main(a):
    executar = '--executar' in a
    contas = [a[a.index('--conta') + 1]] if '--conta' in a else [c for c, v in M.carregar_contas().items() if v.get('ig_id') and os.path.exists(os.path.join(RAIZ, 'calendarios', f'{c}.csv'))]
    for c in contas:
        print(rodar(c, executar))


if __name__ == '__main__':
    main(sys.argv[1:])
