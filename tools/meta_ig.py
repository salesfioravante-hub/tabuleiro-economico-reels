#!/usr/bin/env python3
"""Cliente mínimo da API oficial da Meta (Instagram Graph API) para as 3 contas.

Publica Reels, imagens e carrosséis; lê limite de publicação e métricas (mídias e conta).
Autenticação: o token vem do proxy da sessão (credencial salva para graph.facebook.com, cabeçalho
Authorization: Bearer) ou, fora daqui, da variável de ambiente META_TOKEN. NUNCA coloque token em arquivo.

Uso rápido:
  python3 tools/meta_ig.py descobrir                 # lista Páginas e contas do Instagram e grava contas.json
  python3 tools/meta_ig.py limite tabuleiro          # cota de publicações das últimas 24 h
  python3 tools/meta_ig.py conta tabuleiro 7         # seguidores e métricas da conta nos últimos 7 dias
  python3 tools/meta_ig.py midias tabuleiro 14       # métricas por publicação nos últimos 14 dias
  python3 tools/meta_ig.py reel tabuleiro URL "legenda" [thumb_offset_ms]
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

VERSAO = os.environ.get('META_API_VERSION', 'v23.0')
BASE = f'https://graph.facebook.com/{VERSAO}'
AQUI = os.path.dirname(os.path.abspath(__file__))
CONTAS = os.path.join(AQUI, 'contas.json')


class MetaErro(Exception):
    def __init__(self, resp, status=None):
        e = (resp or {}).get('error', {}) if isinstance(resp, dict) else {}
        self.codigo, self.sub, self.status = e.get('code'), e.get('error_subcode'), status
        self.mensagem = e.get('message') or str(resp)
        super().__init__(f'[{self.status} code={self.codigo} sub={self.sub}] {self.mensagem}')


def _transporte(metodo, url, dados, cabecalhos):
    """troque em testes: devolve (status, dict)"""
    corpo = urllib.parse.urlencode(dados).encode() if (dados and metodo == 'POST') else None
    if dados and metodo == 'GET':
        url += ('&' if '?' in url else '?') + urllib.parse.urlencode(dados)
    req = urllib.request.Request(url, data=corpo, method=metodo, headers=cabecalhos)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read().decode() or '{}')
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or '{}')
        except Exception:
            return e.code, {'error': {'message': str(e)}}


TRANSPORTE = _transporte


def api(metodo, caminho, dados=None):
    url = caminho if caminho.startswith('http') else f'{BASE}/{caminho.lstrip("/")}'
    cab = {}
    tok = os.environ.get('META_TOKEN')
    if tok:
        cab['Authorization'] = f'Bearer {tok}'
    status, resp = TRANSPORTE(metodo, url, dados or {}, cab)
    if status >= 400 or (isinstance(resp, dict) and 'error' in resp):
        raise MetaErro(resp, status)
    return resp


# ------------------------------------------------------------------ contas
def carregar_contas():
    if os.path.exists(CONTAS):
        return json.load(open(CONTAS, encoding='utf-8'))
    return {}


def ig_id(conta):
    c = carregar_contas().get(conta)
    if not c or not c.get('ig_id'):
        raise SystemExit(f'conta "{conta}" sem ig_id: rode "descobrir" antes')
    return c['ig_id']


def descobrir():
    """lista as Páginas que o token enxerga e a conta do Instagram ligada a cada uma"""
    r = api('GET', 'me/accounts', {'fields': 'id,name,instagram_business_account{id,username,followers_count}', 'limit': '50'})
    achadas = {}
    for p in r.get('data', []):
        ig = p.get('instagram_business_account')
        if ig:
            achadas[ig['username']] = dict(handle=ig['username'], ig_id=ig['id'], page_id=p['id'], page_nome=p['name'], seguidores=ig.get('followers_count'))
    return achadas


# ------------------------------------------------------------------ publicação
def _esperar(container, timeout=600, intervalo=5):
    t0 = time.time()
    while True:
        s = api('GET', container, {'fields': 'status_code,status'})
        sc = s.get('status_code')
        if sc in ('FINISHED', 'PUBLISHED'):
            return sc
        if sc in ('ERROR', 'EXPIRED'):
            raise MetaErro({'error': {'message': f'container {container} em {sc}: {s.get("status")}'}}, 200)
        if time.time() - t0 > timeout:
            raise TimeoutError(f'container {container} ainda em {sc} após {timeout}s')
        time.sleep(intervalo)


def _publicar(ig, container, intervalo=5):
    _esperar(container, intervalo=intervalo)
    r = api('POST', f'{ig}/media_publish', {'creation_id': container})
    info = api('GET', r['id'], {'fields': 'permalink,timestamp,media_product_type'})
    return dict(media_id=r['id'], permalink=info.get('permalink'), container_id=container)


def publicar_reel(ig, video_url, legenda, thumb_offset_ms=None, share_to_feed=True, colaboradores=None, intervalo=5, on_container=None):
    d = {'media_type': 'REELS', 'video_url': video_url, 'caption': legenda, 'share_to_feed': 'true' if share_to_feed else 'false'}
    if thumb_offset_ms is not None:
        d['thumb_offset'] = str(int(thumb_offset_ms))
    if colaboradores:
        d['collaborators'] = json.dumps(colaboradores)
    c = api('POST', f'{ig}/media', d)['id']
    if on_container:
        on_container(c)          # grava o container ANTES de publicar, para recuperar se der timeout
    return _publicar(ig, c, intervalo)


def publicar_imagem(ig, image_url, legenda, intervalo=5, on_container=None):
    c = api('POST', f'{ig}/media', {'image_url': image_url, 'caption': legenda})['id']
    if on_container:
        on_container(c)
    return _publicar(ig, c, intervalo)


def publicar_carrossel(ig, itens, legenda, intervalo=5, on_container=None):
    """itens: lista de (url, 'IMAGE'|'VIDEO'), de 2 a 10"""
    if not 2 <= len(itens) <= 10:
        raise ValueError('carrossel precisa de 2 a 10 itens')
    filhos = []
    for url, tipo in itens:
        d = {'is_carousel_item': 'true'}
        if tipo == 'VIDEO':
            d.update(media_type='VIDEO', video_url=url)
        else:
            d['image_url'] = url
        cid = api('POST', f'{ig}/media', d)['id']
        if tipo == 'VIDEO':
            _esperar(cid, intervalo=intervalo)
        filhos.append(cid)
    c = api('POST', f'{ig}/media', {'media_type': 'CAROUSEL', 'children': ','.join(filhos), 'caption': legenda})['id']
    if on_container:
        on_container(c)
    return _publicar(ig, c, intervalo)


def status_container(container):
    return api('GET', container, {'fields': 'status_code,status'})


def limite_publicacao(ig):
    r = api('GET', f'{ig}/content_publishing_limit', {'fields': 'quota_usage,config'})
    return r.get('data', [r])[0]


# ------------------------------------------------------------------ métricas
METRICAS_REEL = ['views', 'reach', 'saved', 'shares', 'likes', 'comments', 'total_interactions', 'ig_reels_avg_watch_time', 'ig_reels_video_view_total_time']
METRICAS_FEED = ['views', 'reach', 'saved', 'shares', 'likes', 'comments', 'total_interactions']


def _metricas_midia(media_id, lista):
    """tenta a lista inteira e vai tirando a métrica que a API recusar para esse tipo de mídia"""
    lista = list(lista)
    while lista:
        try:
            r = api('GET', f'{media_id}/insights', {'metric': ','.join(lista)})
            return {m['name']: (m['values'][0]['value'] if m.get('values') else m.get('total_value', {}).get('value')) for m in r.get('data', [])}
        except MetaErro as e:
            ruim = [m for m in lista if m in e.mensagem]
            if not ruim:
                return {'erro': e.mensagem}
            lista = [m for m in lista if m not in ruim]
    return {}


def midias(ig, dias=14):
    desde = time.time() - dias * 86400
    r = api('GET', f'{ig}/media', {'fields': 'id,caption,media_type,media_product_type,timestamp,permalink,like_count,comments_count', 'limit': '50'})
    saida = []
    for m in r.get('data', []):
        ts = time.mktime(time.strptime(m['timestamp'][:19], '%Y-%m-%dT%H:%M:%S')) - time.timezone
        if ts < desde:
            continue
        lista = METRICAS_REEL if m.get('media_product_type') == 'REELS' else METRICAS_FEED
        m['insights'] = _metricas_midia(m['id'], lista)
        saida.append(m)
    return saida


def conta(ig, dias=7):
    info = api('GET', ig, {'fields': 'username,followers_count,follows_count,media_count'})
    fim = int(time.time())
    ini = fim - dias * 86400
    met = {}
    for m in ['reach', 'views', 'accounts_engaged', 'total_interactions', 'profile_views', 'follows_and_unfollows']:
        try:
            r = api('GET', f'{ig}/insights', {'metric': m, 'period': 'day', 'metric_type': 'total_value', 'since': str(ini), 'until': str(fim)})
            met[m] = r['data'][0].get('total_value', {}).get('value')
        except MetaErro as e:
            met[m] = f'indisponível ({e.codigo})'
    return dict(info=info, metricas=met, dias=dias)


# ------------------------------------------------------------------ linha de comando
def _main(a):
    if not a:
        print(__doc__)
        return
    cmd = a[0]
    if cmd == 'descobrir':
        achadas = descobrir()
        atual = carregar_contas()
        atual.update(achadas)
        json.dump(atual, open(CONTAS, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        print(json.dumps(achadas, ensure_ascii=False, indent=2))
    elif cmd == 'limite':
        print(json.dumps(limite_publicacao(ig_id(a[1])), ensure_ascii=False, indent=2))
    elif cmd == 'conta':
        print(json.dumps(conta(ig_id(a[1]), int(a[2]) if len(a) > 2 else 7), ensure_ascii=False, indent=2))
    elif cmd == 'midias':
        print(json.dumps(midias(ig_id(a[1]), int(a[2]) if len(a) > 2 else 14), ensure_ascii=False, indent=2))
    elif cmd == 'reel':
        print(json.dumps(publicar_reel(ig_id(a[1]), a[2], a[3], int(a[4]) if len(a) > 4 else None), ensure_ascii=False, indent=2))
    else:
        print(__doc__)


if __name__ == '__main__':
    _main(sys.argv[1:])
