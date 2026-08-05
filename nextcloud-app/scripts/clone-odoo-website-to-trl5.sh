#!/usr/bin/env bash
# Clone LOCAL Odoo website views/pages/menus/params to TRL5 for a true content match.
#
# Usage:
#   bash nextcloud-app/scripts/clone-odoo-website-to-trl5.sh
#   TRL5_HOST=root@100.82.252.18 bash nextcloud-app/scripts/clone-odoo-website-to-trl5.sh
#
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HOST="${TRL5_HOST:-root@100.82.252.18}"
DB="${ODOO_DB:-filantropia_public}"
TMPDIR="${TMPDIR:-/tmp}/fs-website-clone-$$"
mkdir -p "$TMPDIR"

echo "[1/4] Export website payload from local Odoo..."
docker exec -i filantropia-odoo odoo shell -d "$DB" \
  --db_host=odoo-db --db_user=odoo --db_password=odoo_dev_password --no-http <<'PY' > "$TMPDIR/website_payload.json"
import json
from odoo.tools.safe_eval import safe_eval

def view_rec(v):
    return {
        'key': v.key,
        'name': v.name,
        'type': v.type,
        'arch_db': v.arch_db or '',
        'active': bool(v.active),
        'priority': v.priority,
        'website_id': bool(v.website_id),
        'inherit_id_key': v.inherit_id.key if v.inherit_id else None,
    }

views = env['ir.ui.view'].with_context(active_test=False).search([
    '|', '|',
    ('key', 'ilike', 'filantropia_solar_public'),
    ('name', 'ilike', 'filantropia'),
    ('key', 'in', [
        'website.layout',  # skip generic unless website-specific COW
    ]),
])
# Only module + website-specific pages we care about
views = views.filtered(lambda v: v.key and (
    'filantropia_solar_public' in (v.key or '') or
    (v.website_id and v.key and v.key.startswith('website.'))
))
# Prefer filantropia keys primarily
views = env['ir.ui.view'].with_context(active_test=False).search([
    ('key', 'ilike', 'filantropia_solar_public')
])

pages = []
for p in env['website.page'].search([]):
    pages.append({
        'url': p.url,
        'name': p.name,
        'website_published': bool(getattr(p, 'is_published', getattr(p, 'website_published', False))),
        'view_key': p.view_id.key if p.view_id else None,
    })

menus = []
for m in env['website.menu'].search([]):
    menus.append({
        'name': m.name,
        'url': m.url or False,
        'sequence': m.sequence,
        'parent_url': m.parent_id.url if m.parent_id else False,
        'parent_name': m.parent_id.name if m.parent_id else False,
        'is_visible': bool(getattr(m, 'is_visible', True)),
    })

w = env['website'].search([], limit=1)
website = {
    'name': w.name if w else None,
    'domain': w.domain if w else None,
    'default_lang': w.default_lang_id.code if w and w.default_lang_id else None,
    'langs': w.language_ids.mapped('code') if w else [],
}

ICP = env['ir.config_parameter'].sudo()
params = {
    'web.base.url': ICP.get_param('web.base.url'),
    'web.base.url.freeze': ICP.get_param('web.base.url.freeze'),
}

# blog if present
posts = []
if 'blog.post' in env:
    for b in env['blog.post'].search([('website_published','=',True)]):
        posts.append({
            'name': b.name,
            'subtitle': getattr(b, 'subtitle', False) or False,
            'content': b.content or '',
            'website_meta_title': getattr(b, 'website_meta_title', False) or False,
            'website_meta_description': getattr(b, 'website_meta_description', False) or False,
        })

mod = env['ir.module.module'].search([('name','=','filantropia_solar_public')])
payload = {
    'module_version': mod.installed_version,
    'website': website,
    'params': params,
    'views': [view_rec(v) for v in views],
    'pages': pages,
    'menus': menus,
    'blog_posts': posts,
}
print(json.dumps(payload, ensure_ascii=False))
PY

python3 - <<PY
import json
from pathlib import Path
p=Path("$TMPDIR/website_payload.json")
# odoo shell may print logs to stdout — extract last JSON object
text=p.read_text('utf-8','replace')
start=text.rfind('{')
# find first { that begins JSON with module_version
idx=text.find('{"module_version"')
if idx<0:
    idx=text.find('{\n')
    # brute: last line-balanced
    idx=text.find('{')
while idx>=0:
    try:
        data=json.loads(text[idx:])
        break
    except Exception:
        idx=text.find('{', idx+1)
else:
    raise SystemExit('failed to parse JSON payload from odoo shell output')
Path("$TMPDIR/website_payload.clean.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
print('views', len(data.get('views',[])), 'pages', len(data.get('pages',[])), 'menus', len(data.get('menus',[])), 'ver', data.get('module_version'))
PY

echo "[2/4] Copy payload to TRL5..."
scp -o BatchMode=yes "$TMPDIR/website_payload.clean.json" "$HOST:/tmp/fs_website_payload.json"

echo "[3/4] Ensure P2 addon on TRL5 + import payload..."
# sync addon from this repo (latest website)
git archive HEAD nextcloud-app/odoo/addons/filantropia_solar_public \
  | ssh -o BatchMode=yes "$HOST" "tar -C /opt/FilantropiaSolar -xf -"

ssh -o BatchMode=yes -o ServerAliveInterval=30 "$HOST" 'bash -s' <<'REMOTE'
set +e
cd /opt/FilantropiaSolar/nextcloud-app
export COMPOSE_FILE=docker-compose.yml:docker-compose.trl5.yml
export FS_PUBLIC_API_TOKEN=$(tr -d '\r\n' < /opt/FilantropiaSolar/.secrets/filantropia_public_api_token 2>/dev/null)

grep version odoo/addons/filantropia_solar_public/__manifest__.py
docker exec filantropia-odoo odoo -d filantropia_public \
  -u filantropia_solar_public \
  --db_host=odoo-db --db_user=odoo --db_password=odoo_dev_password \
  --stop-after-init 2>&1 | tail -25
docker compose --profile odoo up -d odoo
sleep 8

docker cp /tmp/fs_website_payload.json filantropia-odoo:/tmp/fs_website_payload.json
docker exec -i filantropia-odoo odoo shell -d filantropia_public \
  --db_host=odoo-db --db_user=odoo --db_password=odoo_dev_password --no-http <<'PY'
import json
payload=json.load(open('/tmp/fs_website_payload.json', encoding='utf-8'))
print('importing module_version', payload.get('module_version'), 'views', len(payload.get('views',[])))

ICP=env['ir.config_parameter'].sudo()
for k,v in (payload.get('params') or {}).items():
    if v is not None:
        ICP.set_param(k, v)

w=env['website'].search([], limit=1)
ws=payload.get('website') or {}
if w and ws:
    vals={}
    if ws.get('name'): vals['name']=ws['name']
    if ws.get('domain'): vals['domain']=ws['domain']
    # langs
    codes=ws.get('langs') or []
    Lang=env['res.lang']
    lang_ids=[]
    for code in codes:
        lang=Lang.search([('code','=',code)], limit=1)
        if not lang:
            try:
                Lang._activate_lang(code)
            except Exception:
                pass
            lang=Lang.search([('code','=',code)], limit=1)
        if lang:
            lang_ids.append(lang.id)
    if lang_ids:
        w.write({'language_ids': [(6, 0, lang_ids)]})
    if ws.get('default_lang'):
        dl=Lang.search([('code','=',ws['default_lang'])], limit=1)
        if dl and 'default_lang_id' in w._fields:
            vals['default_lang_id']=dl.id
    if vals:
        w.write(vals)

# Apply view arches by key
View=env['ir.ui.view'].with_context(active_test=False)
for item in payload.get('views') or []:
    key=item.get('key')
    if not key:
        continue
    v=View.search([('key','=',key)], limit=1)
    arch=item.get('arch_db') or ''
    if not v:
        print('MISSING view key', key, 'skip create')
        continue
    # write arch on all records with this key (COW duplicates)
    twins=View.search([('key','=',key)])
    twins.write({'arch_db': arch, 'active': item.get('active', True)})
    print('updated', key, 'n=', len(twins), 'arch_len', len(arch))

# Pages publish flags / names
Page=env['website.page']
for item in payload.get('pages') or []:
    url=item.get('url')
    if not url:
        continue
    pages=Page.search([('url','=',url)])
    if not pages and item.get('view_key'):
        v=View.search([('key','=',item['view_key'])], limit=1)
        if v:
            pages=Page.search([('view_id','=',v.id)])
    if not pages:
        print('no page for', url)
        continue
    vals={'name': item.get('name') or pages[:1].name}
    if 'is_published' in pages._fields:
        vals['is_published']=bool(item.get('website_published'))
    elif 'website_published' in pages._fields:
        vals['website_published']=bool(item.get('website_published'))
    pages.write(vals)
    print('page', url, vals)

# Menus: match by URL then name
Menu=env['website.menu']
for item in payload.get('menus') or []:
    url=item.get('url') or ''
    name=item.get('name')
    m=Menu.search([('url','=',url)], limit=1) if url else Menu.browse()
    if not m and name:
        m=Menu.search([('name','=',name)], limit=1)
    if not m:
        # create top-level
        parent=False
        if item.get('parent_url'):
            parent=Menu.search([('url','=',item['parent_url'])], limit=1)
        vals={
            'name': name,
            'url': url or False,
            'sequence': item.get('sequence') or 10,
            'website_id': w.id if w else False,
            'parent_id': parent.id if parent else False,
        }
        m=Menu.create(vals)
        print('created menu', name, url)
    else:
        vals={'name': name, 'sequence': item.get('sequence') or m.sequence}
        if url:
            vals['url']=url
        m.write(vals)
        print('updated menu', name, url)

# Blog posts (best-effort by name)
if payload.get('blog_posts') and 'blog.post' in env:
    Blog=env['blog.blog'].search([], limit=1)
    if not Blog:
        Blog=env['blog.blog'].create({'name': 'Filantropia Solar', 'subtitle': False})
    Post=env['blog.post']
    for item in payload['blog_posts']:
        p=Post.search([('name','=',item['name'])], limit=1)
        vals={
            'name': item['name'],
            'content': item.get('content') or '',
            'blog_id': Blog.id,
            'is_published': True,
        }
        if 'subtitle' in Post._fields and item.get('subtitle'):
            vals['subtitle']=item['subtitle']
        if 'website_meta_title' in Post._fields and item.get('website_meta_title'):
            vals['website_meta_title']=item['website_meta_title']
        if 'website_meta_description' in Post._fields and item.get('website_meta_description'):
            vals['website_meta_description']=item['website_meta_description']
        if p:
            p.write(vals)
            print('blog update', item['name'])
        else:
            Post.create(vals)
            print('blog create', item['name'])

env.cr.commit()
print('IMPORT_OK')
# verify
for key in ['filantropia_solar_public.page_inicio','filantropia_solar_public.page_candidatura']:
    v=env['ir.ui.view'].search([('key','=',key)], limit=1)
    arch=v.arch_db or ''
    print(key, 'len', len(arch), 'faq', 'faq' in arch.lower(), 'accordion', 'accordion' in arch.lower())
print('web.base.url', env['ir.config_parameter'].sudo().get_param('web.base.url'))
w=env['website'].search([], limit=1)
print('website', w.name, w.domain, w.default_lang_id.code if w.default_lang_id else None)
PY

docker compose --profile odoo restart odoo
sleep 8
for path in /inicio /candidatura /contacto /instalacoes; do
  curl -sS -o /dev/null -w "$path %{http_code} bytes=%{size_download}\n" -m 15 \
    -H 'Accept-Language: pt-PT' -H 'Cookie: frontend_lang=pt_PT' \
    "http://127.0.0.1:8069$path"
done
REMOTE

echo "[4/4] Public probe..."
sleep 3
for path in /inicio /candidatura /contacto /instalacoes; do
  /usr/bin/curl -sS -o /dev/null -w "https://filantropiasolar.wera.global$path %{http_code} bytes=%{size_download}\n" --max-time 25 \
    -H 'Accept-Language: pt-PT' -H 'Cookie: frontend_lang=pt_PT' \
    "https://filantropiasolar.wera.global$path"
done

rm -rf "$TMPDIR"
echo DONE_CLONE
