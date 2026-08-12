"""Post-init hooks for the Filantropia Solar public module."""

from __future__ import annotations

import logging

_logger = logging.getLogger(__name__)

LEGACY_URL = "/filantropia-solar"
HOME_URL = "/inicio"
SITE_NAME = "Filantropia Solar"
COMPANY_NAME = "Filantropia Solar"

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


def _ensure_site_identity(env):
    """Brand all websites + company as Filantropia Solar; PT default; /inicio home."""
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

    # Company display name (appears in some layouts)
    company = env.ref("base.main_company", raise_if_not_found=False)
    if company and "Filantropia" not in (company.name or ""):
        company.name = COMPANY_NAME
        _logger.info("filantropia_solar_public: company renamed to %s", COMPANY_NAME)

    for website in env["website"].search([]):
        vals = {}
        if website.name != SITE_NAME:
            vals["name"] = SITE_NAME
        if "homepage_url" in website._fields and website.homepage_url != HOME_URL:
            vals["homepage_url"] = HOME_URL
        if vals:
            website.write(vals)

        # languages
        to_add = []
        if pt not in website.language_ids:
            to_add.append(pt.id)
        if en and en not in website.language_ids:
            to_add.append(en.id)
        if to_add:
            website.language_ids = [(4, lid) for lid in to_add]
        if website.default_lang_id != pt:
            website.default_lang_id = pt
            _logger.info(
                "filantropia_solar_public: website %s default lang -> pt_PT",
                website.id,
            )

        _logger.info(
            "filantropia_solar_public: website id=%s name=%s default=%s",
            website.id,
            website.name,
            website.default_lang_id.code,
        )


def _external_id(env, module: str, name: str, record):
    Imd = env["ir.model.data"].sudo()
    existing = Imd.search([("module", "=", module), ("name", "=", name)], limit=1)
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


def _editorial_teasers():
    """Curated PT/EN teasers and SEO for success-story posts."""
    return {
        "blog_post_braga": {
            "teaser_pt": (
                "Com 64.93 kWp, o abrigo reduziu a fatura elétrica em mais de 80%. "
                "A poupança financia alimentação, veterinária e melhores instalações para os animais."
            ),
            "teaser_en": (
                "With 64.93 kWp, the shelter cut its electricity bill by more than 80%. "
                "Savings fund food, veterinary care and better facilities for the animals."
            ),
            "meta_pt": "Caso de sucesso Filantropia Solar: Abrigo dos Animais de Braga (64.93 kWp).",
            "meta_en": "Filantropia Solar success story: Braga Animal Shelter (64.93 kWp).",
        },
        "blog_post_tavira": {
            "teaser_pt": (
                "A instalação de 46 kWp baixou custos operacionais em mais de 60%, "
                "permitindo resgatar mais animais e reforçar cuidados veterinários."
            ),
            "teaser_en": (
                "The 46 kWp installation cut operating costs by more than 60%, "
                "enabling more rescues and stronger veterinary care."
            ),
            "meta_pt": "Caso de sucesso Filantropia Solar: Associação de Proteção Animal de Tavira.",
            "meta_en": "Filantropia Solar success story: Tavira Animal Protection Association.",
        },
        "blog_post_lisboa": {
            "teaser_pt": (
                "O centro cobre mais de 70% do consumo com solar (46 kWp), "
                "libertando orçamento para programas sociais e atividades comunitárias."
            ),
            "teaser_en": (
                "The centre covers more than 70% of electricity use with solar (46 kWp), "
                "freeing budget for social programmes and community activities."
            ),
            "meta_pt": "Caso de sucesso Filantropia Solar: Centro Comunitário de Lisboa.",
            "meta_en": "Filantropia Solar success story: Lisbon Community Centre.",
        },
    }


def _ensure_blog_posts(env):
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
    else:
        # Keep PT as source values
        blog.with_context(lang="pt_PT").write(
            {
                "name": "Casos de Sucesso",
                "subtitle": "Histórias reais da rede Filantropia Solar",
            }
        )

    blog.with_context(lang="en_US").write(
        {
            "name": "Success Stories",
            "subtitle": "Real stories from the Filantropia Solar network",
        }
    )

    for spec in _POSTS_PT:
        xml_name = spec["xmlid"].split(".", 1)[1]
        post = env.ref(spec["xmlid"], raise_if_not_found=False)
        vals_pt = {
            "name": spec["name"],
            "subtitle": spec["subtitle"],
            "content": spec["content"],
            "blog_id": blog.id,
            "is_published": True,
        }
        if not post:
            post = Post.create(vals_pt)
            _external_id(env, "filantropia_solar_public", xml_name, post)
            _logger.info("filantropia_solar_public: created post %s", spec["name"])
        else:
            post.with_context(lang="pt_PT").write(vals_pt)
        post.with_context(lang="en_US").write(spec["en"])

        # Editorial teaser + SEO (animal-shelter-first order via creation order)
        tip = _editorial_teasers().get(xml_name, {})
        if tip:
            pt_vals = {
                "website_meta_title": spec["name"],
                "website_meta_description": tip["meta_pt"],
            }
            en_vals = {
                "website_meta_title": spec["en"]["name"],
                "website_meta_description": tip["meta_en"],
            }
            if "teaser_manual" in post._fields:
                pt_vals["teaser_manual"] = tip["teaser_pt"]
                en_vals["teaser_manual"] = tip["teaser_en"]
            post.with_context(lang="pt_PT").write(pt_vals)
            post.with_context(lang="en_US").write(en_vals)




_FS_VIEW_KEYS = (
    "filantropia_solar_public.page_inicio",
    "filantropia_solar_public.page_instalacoes",
    "filantropia_solar_public.page_contacto",
    "filantropia_solar_public.page_candidatura",
    "filantropia_solar_public.snippet_leaflet_map",
    "filantropia_solar_public.snippet_steps",
)


def _reset_website_cows(env):
    """Drop website-editor COW copies so module XML remains source of truth."""
    View = env["ir.ui.view"].sudo()
    cows = View.search([
        ("website_id", "!=", False),
        ("key", "in", list(_FS_VIEW_KEYS)),
    ])
    if cows:
        keys = sorted({c.key for c in cows})
        n = len(cows)
        cows.unlink()
        _logger.info(
            "filantropia_solar_public: removed %s website COW view(s): %s",
            n,
            ", ".join(keys),
        )


def post_init_hook(env):
    """Run after module install/update."""
    _ensure_legacy_redirect(env)
    _ensure_site_identity(env)
    _ensure_blog_posts(env)
    _reset_website_cows(env)
