# trunk-ignore-begin(pyright/reportMissingImports): conftest.py puts the scripts folder on sys.path
from fakes import FakeSession
from publish_article import ZendeskHelpCenter, attachment_ids, find_orphans

# trunk-ignore-end(pyright/reportMissingImports)

LIST = "/help_center/articles/42/attachments.json"


def client(routes) -> ZendeskHelpCenter:
    return ZendeskHelpCenter("z", "e", "t", session=FakeSession(routes))


def test_attachment_ids_reads_full_short_and_locale_forms():
    html = (
        '<img src="https://z.zendesk.com/hc/article_attachments/101/a.png">'
        '<img src="/hc/article_attachments/102">'
        '<img src="https://z.zendesk.com/hc/en-us/article_attachments/103/b.png">'
        '<img src="images/local.png">'
    )
    assert attachment_ids(html) == {101, 102, 103}


def test_orphans_are_attachments_the_body_does_not_reference():
    c = client(
        {
            ("GET", LIST): (
                200,
                {
                    "article_attachments": [{"id": 101}, {"id": 102}, {"id": 103}],
                    "next_page": None,
                },
            )
        }
    )
    body = (
        '<img src="/hc/article_attachments/101">'
        '<img src="/hc/en-us/article_attachments/103/x.png">'
    )
    assert find_orphans(c, 42, body) == [102]


def test_orphans_follow_next_page():
    c = client(
        {
            ("GET", LIST): (
                200,
                {
                    "article_attachments": [{"id": 1}],
                    "next_page": f"https://z.zendesk.com/api/v2{LIST}?page=2",
                },
            ),
            ("GET", f"{LIST}?page=2"): (
                200,
                {"article_attachments": [{"id": 2}], "next_page": None},
            ),
        }
    )
    assert find_orphans(c, 42, "") == [1, 2]


def test_download_attachments_are_not_orphans():
    c = client(
        {
            ("GET", LIST): (
                200,
                {
                    "article_attachments": [
                        {"id": 101, "inline": True},
                        {"id": 102, "inline": False},
                        {"id": 103},
                    ],
                    "next_page": None,
                },
            )
        }
    )
    assert find_orphans(c, 42, "") == [101, 103]


def test_user_segments_and_permission_groups_follow_next_page():
    base = "https://z.zendesk.com/api/v2"
    c = client(
        {
            ("GET", "/help_center/user_segments.json"): (
                200,
                {
                    "user_segments": [{"id": 1}],
                    "next_page": f"{base}/help_center/user_segments.json?page=2",
                },
            ),
            ("GET", "/help_center/user_segments.json?page=2"): (
                200,
                {"user_segments": [{"id": 2}], "next_page": None},
            ),
            ("GET", "/guide/permission_groups.json"): (
                200,
                {
                    "permission_groups": [{"id": 3}],
                    "next_page": f"{base}/guide/permission_groups.json?page=2",
                },
            ),
            ("GET", "/guide/permission_groups.json?page=2"): (
                200,
                {"permission_groups": [{"id": 4}], "next_page": None},
            ),
        }
    )
    assert [s["id"] for s in c.user_segments()] == [1, 2]
    assert [g["id"] for g in c.permission_groups()] == [3, 4]
