"""The assistant sends people to this portal's own pages, never to the airline's website."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
SOURCES = [ROOT / "domain.yml", ROOT / "actions" / "actions.py", ROOT / "actions" / "forms.py"]
PAGE_LINK = re.compile(r"page:([a-z-]+\.html)(?:#([a-z-]+))?")


def test_replies_do_not_send_people_to_the_airline_website():
    for source in SOURCES:
        assert not re.search(r"kenya-?airways\.com", source.read_text(encoding="utf8"), re.I), source.name


def test_every_link_in_a_reply_points_to_a_real_page_and_section():
    links = [link for source in SOURCES for link in PAGE_LINK.findall(source.read_text(encoding="utf8"))]
    assert links
    for page, section in links:
        html = (FRONTEND / page).read_text(encoding="utf8")
        assert not section or f'id="{section}"' in html, f"{page}#{section}"


def test_email_question_does_not_promise_a_confirmation():
    assert "should we use for this booking" in (ROOT / "domain.yml").read_text(encoding="utf8")
