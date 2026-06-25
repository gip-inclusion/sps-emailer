from sps.template import render_richblock, tension_badge, default_intro

def test_richblock_markdown_to_html():
    html = render_richblock({"format": "markdown", "content": "**Hi** there"})
    assert "<strong>Hi</strong>" in html

def test_richblock_html_passthrough():
    html = render_richblock({"format": "html", "content": "<b>x</b>"})
    assert html == "<b>x</b>"

def test_richblock_none():
    assert render_richblock(None) == ""

def test_tension_badge_colors():
    assert "Service très sollicité" in tension_badge("rouge")
    assert "Places disponibles" in tension_badge("vert")
    assert tension_badge(None) == ""

def test_default_intro_interpolates_first_name():
    assert "Jane" in default_intro({"nom": "DOE Jane", "email": "j@x.fr"})

def test_default_intro_handles_multi_token_surname():
    # noms conseiller = nom-de-famille d'abord (composé possible), prénom en dernier
    assert "Alex" in default_intro({"nom": "MARTIN DUPONT Alex", "email": "a@x.fr"})
    assert "Bonjour Alex," in default_intro({"nom": "MARTIN DUPONT Alex", "email": "a@x.fr"})
