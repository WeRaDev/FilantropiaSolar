"""Post-init hooks for the Filantropia Solar public module."""

from __future__ import annotations

import logging

_logger = logging.getLogger(__name__)

LEGACY_URL = "/filantropia-solar"
HOME_URL = "/inicio"

_BLOG_XMLID = "filantropia_solar_public.blog_casos_sucesso"

_POSTS_PT = [
    {
        "xmlid": "filantropia_solar_public.blog_post_braga",
        "name": "Abrigo dos Animais de Braga",
        "subtitle": "Braga — 64.93 kWp",
        "content": (
            "<section><p>O Abrigo dos Animais de Braga foi uma das primeiras "
            "organizações a integrar a rede Filantropia Solar. Com uma instalação "
            "de 64.93 kWp, a organização reporta uma redução superior a 80% na "
            "fatura elétrica.</p>"
            "<p>Os fundos poupados são agora aplicados em alimentação, cuidados "
            "veterinários e melhorias das instalações para os animais. Este caso "
            "ilustra o impacto direto da doação em espécie — equipamento e "
            "instalação — no dia a dia de um abrigo de animais, prioridade do "
            "programa.</p>"
            "<p><em>A doação Filantropia Solar não inclui manutenção continuada; "
            "a organização beneficiária assume a operação corrente do sistema."
            "</em></p></section>"
        ),
        "en": {
            "name": "Braga Animal Shelter",
            "subtitle": "Braga — 64.93 kWp",
            "content": (
                "<section><p>The Braga Animal Shelter was among the first "
                "organisations to join the Filantropia Solar network. With a "
                "64.93 kWp installation, the organisation reports an "
                "electricity-bill reduction of more than 80%.</p>"
                "<p>Savings are now applied to food, veterinary care and facility "
                "improvements for the animals. This case shows the direct impact "
                "of an in-kind donation — equipment and installation — on the "
                "daily life of an animal shelter, a programme priority.</p>"
                "<p><em>Filantropia Solar does not include ongoing maintenance; "
                "the beneficiary organisation operates the system day to day."
                "</em></p></section>"
            ),
        },
    },
    {
        "xmlid": "filantropia_solar_public.blog_post_tavira",
        "name": "Associação de Proteção Animal de Tavira",
        "subtitle": "Tavira — 46 kWp",
        "content": (
            "<section><p>Na Associação de Proteção Animal de Tavira, a "
            "instalação de 46 kWp reduziu os custos operacionais em mais de "
            "60%.</p>"
            "<p>Com a poupança energética, a associação conseguiu expandir o "
            "número de animais resgatados e reforçar os cuidados veterinários. "
            "O caso mostra como a energia solar doada liberta orçamento para a "
            "missão social da organização.</p></section>"
        ),
        "en": {
            "name": "Tavira Animal Protection Association",
            "subtitle": "Tavira — 46 kWp",
            "content": (
                "<section><p>At the Tavira Animal Protection Association, a "
                "46 kWp installation cut operating costs by more than 60%.</p>"
                "<p>Energy savings allowed the association to expand the number "
                "of animals rescued and strengthen veterinary care. The case "
                "shows how donated solar energy frees budget for the "
                "organisation's social mission.</p></section>"
            ),
        },
    },
    {
        "xmlid": "filantropia_solar_public.blog_post_lisboa",
        "name": "Centro Comunitário de Lisboa",
        "subtitle": "Lisboa — 46 kWp",
        "content": (
            "<section><p>O Centro Comunitário de Lisboa cobre agora mais de 70% "
            "do seu consumo elétrico com energia solar, graças a uma instalação "
            "de 46 kWp apoiada pela Filantropia Solar.</p>"
            "<p>O orçamento libertado é canalizado para programas sociais e "
            "atividades comunitárias. A história reforça o valor de uma doação "
            "em espécie (equipamento + instalação) face a apoios pontuais em "
            "dinheiro.</p></section>"
        ),
        "en": {
            "name": "Lisbon Community Centre",
            "subtitle": "Lisbon — 46 kWp",
            "content": (
                "<section><p>The Lisbon Community Centre now covers more than "
                "70% of its electricity use with solar energy, thanks to a "
                "46 kWp installation supported by Filantropia Solar.</p>"
                "<p>Freed budget is channelled into social programmes and "
                "community activities. The story reinforces the value of an "
                "in-kind donation (equipment + installation) versus one-off "
                "cash support.</p></section>"
            ),
        },
    },
]


def _ensure_legacy_redirect(env):
    rewrite = env["website.rewrite"].search([("url_from", "=", LEGACY_URL)], limit=1)
    if not rewrite:
        env["website.rewrite"].create(
            {
                "name": "filantropia-solar legacy home",
                "redirect_type": "301",
                "url_from": LEGACY_URL,
                "url_to": HOME_URL,
            }
        )
        _logger.info(
            "filantropia_solar_public: 301 %s -> %s registered",
            LEGACY_URL,
            HOME_URL,
        )


def _ensure_languages(env):
    """Activate pt_PT + en_US; set filantropiasolar website default to Portuguese."""
    Lang = env["res.lang"]
    for code in ("pt_PT", "en_US"):
        lang = Lang.search([("code", "=", code)], limit=1)
        if lang and not lang.active:
            lang.active = True
            _logger.info("filantropia_solar_public: activated language %s", code)

    pt = Lang.search([("code", "=", "pt_PT"), ("active", "=", True)], limit=1)
    en = Lang.search([("code", "=", "en_US"), ("active", "=", True)], limit=1)
    if not pt:
        _logger.warning("filantropia_solar_public: pt_PT not available")
        return

    for website in env["website"].search([]):
        to_add = []
        if pt not in website.language_ids:
            to_add.append(pt.id)
        if en and en not in website.language_ids:
            to_add.append(en.id)
        if to_add:
            website.language_ids = [(4, lid) for lid in to_add]
        name = (website.name or "").lower()
        if (
            "filantropia" in name
            or website == env["website"].search([], order="id desc", limit=1)
        ) and (website.default_lang_id != pt):
            website.default_lang_id = pt
            _logger.info(
                "filantropia_solar_public: website %s default lang -> pt_PT",
                website.id,
            )


def _external_id(env, module: str, name: str, record):
    """Create or update ir.model.data for a record."""
    Imd = env["ir.model.data"].sudo()
    existing = Imd.search(
        [("module", "=", module), ("name", "=", name)],
        limit=1,
    )
    if existing:
        return env[record._name].browse(existing.res_id)
    Imd.create(
        {
            "name": name,
            "module": module,
            "model": record._name,
            "res_id": record.id,
            "noupdate": True,
        }
    )
    return record


def _ensure_blog_posts(env):
    """Seed Casos de Sucesso blog + 3 published posts (PT) and EN translations."""
    Blog = env["blog.blog"].sudo()
    Post = env["blog.post"].sudo()

    blog = env.ref(_BLOG_XMLID, raise_if_not_found=False)
    if not blog:
        blog = Blog.create(
            {
                "name": "Casos de Sucesso",
                "subtitle": "Histórias reais da rede Filantropia Solar",
            }
        )
        _external_id(env, "filantropia_solar_public", "blog_casos_sucesso", blog)
        _logger.info(
            "filantropia_solar_public: created blog Casos de Sucesso id=%s", blog.id
        )

    # EN blog name
    blog.with_context(lang="en_US").write(
        {
            "name": "Success Stories",
            "subtitle": "Real stories from the Filantropia Solar network",
        }
    )

    for spec in _POSTS_PT:
        xml_name = spec["xmlid"].split(".", 1)[1]
        post = env.ref(spec["xmlid"], raise_if_not_found=False)
        vals = {
            "name": spec["name"],
            "subtitle": spec["subtitle"],
            "content": spec["content"],
            "blog_id": blog.id,
            "is_published": True,
        }
        if not post:
            post = Post.create(vals)
            _external_id(env, "filantropia_solar_public", xml_name, post)
            _logger.info("filantropia_solar_public: created post %s", spec["name"])
        # keep published; refresh content if empty
        elif not post.content:
            post.write(vals)
        post.with_context(lang="en_US").write(spec["en"])


def post_init_hook(env):
    """Run after module install/update."""
    _ensure_legacy_redirect(env)
    _ensure_languages(env)
    _ensure_blog_posts(env)
