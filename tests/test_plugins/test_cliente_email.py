"""Testes da logica de intervalo de datas do cliente de e-mail (IMAP).

Foco na logica pura (parse/validacao/criterios/ordenacao) e nas funcoes de
busca, sem depender de um servidor IMAP real — MailBox e AND sao mockados.
"""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
import pytz

import cliente_email as c


# ---------------------------------------------------------------------------
# Fakes / helpers de mock
# ---------------------------------------------------------------------------
class FakeAttachment:
    def __init__(self, filename: str, payload: bytes) -> None:
        self.filename = filename
        self.payload = payload


class FakeMsg:
    def __init__(self, subject, dt, attachments) -> None:
        self.subject = subject
        self.date = dt
        self.attachments = attachments


def _install_mailbox(monkeypatch, messages):
    """Instala um MailBox mockado que devolve `messages` no fetch.

    Retorna (captured, mailbox) onde captured['criteria'] recebe os kwargs
    passados para AND(...) e mailbox permite inspecionar o fetch.
    """
    mailbox = MagicMock()
    mailbox.fetch.return_value = iter(messages)

    ctx = MagicMock()
    ctx.__enter__.return_value = mailbox
    ctx.__exit__.return_value = False

    mb_instance = MagicMock()
    mb_instance.login.return_value = ctx

    monkeypatch.setattr(c, "MailBox", MagicMock(return_value=mb_instance))

    captured: dict = {}

    def fake_and(**kwargs):
        captured["criteria"] = kwargs
        return ("AND", kwargs)

    monkeypatch.setattr(c, "AND", fake_and)
    return captured, mailbox


def _dt(y, m, d, h=0, mi=0, tz=timezone.utc):
    return datetime(y, m, d, h, mi, tzinfo=tz)


# ---------------------------------------------------------------------------
# parse_email_date_param
# ---------------------------------------------------------------------------
def test_parse_valid_date() -> None:
    assert c.parse_email_date_param("2026-08-31") == date(2026, 8, 31)


@pytest.mark.parametrize("value", [None, ""])
def test_parse_none_and_empty(value) -> None:
    assert c.parse_email_date_param(value) is None


@pytest.mark.parametrize("value", ["30/08/2026", "2026-13-01", "abc", "2026/08/31"])
def test_parse_invalid_format_raises(value) -> None:
    with pytest.raises(ValueError) as exc:
        c.parse_email_date_param(value, "data_inicial")
    assert "data_inicial" in str(exc.value)
    assert "YYYY-MM-DD" in str(exc.value)


# ---------------------------------------------------------------------------
# resolve_email_date_range
# ---------------------------------------------------------------------------
def test_resolve_none_none() -> None:
    assert c.resolve_email_date_range(None, None) == (None, None)


def test_resolve_start_only() -> None:
    assert c.resolve_email_date_range("2026-08-01", None) == (date(2026, 8, 1), None)


def test_resolve_end_only() -> None:
    assert c.resolve_email_date_range(None, "2026-08-31") == (None, date(2026, 8, 31))


def test_resolve_both() -> None:
    assert c.resolve_email_date_range("2026-08-01", "2026-08-31") == (
        date(2026, 8, 1),
        date(2026, 8, 31),
    )


def test_resolve_equal() -> None:
    assert c.resolve_email_date_range("2026-08-30", "2026-08-30") == (
        date(2026, 8, 30),
        date(2026, 8, 30),
    )


def test_resolve_start_after_end_raises() -> None:
    with pytest.raises(ValueError) as exc:
        c.resolve_email_date_range("2026-08-31", "2026-08-01")
    assert "nao pode ser posterior" in str(exc.value)


def test_resolve_invalid_date_raises() -> None:
    with pytest.raises(ValueError):
        c.resolve_email_date_range("31-08-2026", None)


# ---------------------------------------------------------------------------
# build_date_criteria (semantica IMAP: SINCE inclusivo, BEFORE exclusivo)
# ---------------------------------------------------------------------------
def test_criteria_none_uses_today() -> None:
    today = c._today()
    assert c.build_date_criteria() == {"date": today}


def test_criteria_target_date_single_day() -> None:
    assert c.build_date_criteria(target_date=date(2026, 8, 31)) == {
        "date": date(2026, 8, 31)
    }


def test_criteria_range_inclusive_both_ends() -> None:
    # end recebe +1 dia para que BEFORE inclua o proprio end.
    assert c.build_date_criteria(
        start_date=date(2026, 8, 1), end_date=date(2026, 8, 31)
    ) == {"date_gte": date(2026, 8, 1), "date_lt": date(2026, 9, 1)}


def test_criteria_equal_range_is_single_day() -> None:
    assert c.build_date_criteria(
        start_date=date(2026, 8, 30), end_date=date(2026, 8, 30)
    ) == {"date_gte": date(2026, 8, 30), "date_lt": date(2026, 8, 31)}


def test_criteria_start_only() -> None:
    assert c.build_date_criteria(start_date=date(2026, 8, 1)) == {
        "date_gte": date(2026, 8, 1)
    }


def test_criteria_end_only_inclusive() -> None:
    assert c.build_date_criteria(end_date=date(2026, 8, 31)) == {
        "date_lt": date(2026, 9, 1)
    }


def test_criteria_range_takes_precedence_over_target() -> None:
    assert c.build_date_criteria(
        target_date=date(2020, 1, 1), start_date=date(2026, 8, 1)
    ) == {"date_gte": date(2026, 8, 1)}


# ---------------------------------------------------------------------------
# describe_date_range
# ---------------------------------------------------------------------------
def test_describe_variants() -> None:
    assert (
        c.describe_date_range(start_date=date(2026, 8, 1), end_date=date(2026, 8, 31))
        == "de 2026-08-01 ate 2026-08-31"
    )
    assert c.describe_date_range(start_date=date(2026, 8, 1)).startswith(
        "de 2026-08-01 ate a data atual"
    )
    assert c.describe_date_range(end_date=date(2026, 8, 31)) == "ate 2026-08-31"
    assert c.describe_date_range(target_date=date(2026, 8, 31)) == "da data 2026-08-31"
    assert c.describe_date_range().startswith("do dia atual")


# ---------------------------------------------------------------------------
# _message_sort_key
# ---------------------------------------------------------------------------
def test_sort_key_naive_gets_project_tz() -> None:
    msg = FakeMsg("s", datetime(2026, 8, 1, 10, 0), [])
    key = c._message_sort_key(msg)
    assert key.tzinfo is not None


def test_sort_key_mixed_naive_and_aware_comparable() -> None:
    naive = c._message_sort_key(FakeMsg("s", datetime(2026, 8, 1, 10, 0), []))
    aware = c._message_sort_key(FakeMsg("s", _dt(2026, 8, 1, 10, 0), []))
    # Nao deve levantar TypeError ao comparar.
    assert (naive < aware) or (naive >= aware)


# ---------------------------------------------------------------------------
# fetch_email_with_zip
# ---------------------------------------------------------------------------
def test_zip_requires_subject_or_suffix() -> None:
    with pytest.raises(ValueError):
        c.fetch_email_with_zip("srv", "e", "p", "from", None)


def test_zip_none_none_uses_today_criteria(monkeypatch) -> None:
    captured, _ = _install_mailbox(monkeypatch, [])
    c.fetch_email_with_zip("srv", "e", "p", "from", "assunto")
    assert captured["criteria"]["date"] == c._today()
    assert captured["criteria"]["from_"] == "from"
    assert captured["criteria"]["subject"] == "assunto"


def test_zip_range_criteria(monkeypatch) -> None:
    captured, _ = _install_mailbox(monkeypatch, [])
    c.fetch_email_with_zip(
        "srv",
        "e",
        "p",
        "from",
        "assunto",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 31),
    )
    assert captured["criteria"]["date_gte"] == date(2026, 8, 1)
    assert captured["criteria"]["date_lt"] == date(2026, 9, 1)


def test_zip_returns_only_zip_attachments(monkeypatch) -> None:
    msg = FakeMsg(
        "assunto",
        _dt(2026, 8, 1),
        [FakeAttachment("a.zip", b"ZIP"), FakeAttachment("b.csv", b"CSV")],
    )
    _install_mailbox(monkeypatch, [msg])
    result = c.fetch_email_with_zip("srv", "e", "p", "from", "assunto")
    assert result == [b"ZIP"]


def test_zip_sorted_oldest_to_newest(monkeypatch) -> None:
    msgs = [
        FakeMsg("s", _dt(2026, 8, 5, 17, 45), [FakeAttachment("c.zip", b"C")]),
        FakeMsg("s", _dt(2026, 8, 1, 8, 30), [FakeAttachment("a.zip", b"A")]),
        FakeMsg("s", _dt(2026, 8, 2, 9, 10), [FakeAttachment("b.zip", b"B")]),
    ]
    _install_mailbox(monkeypatch, msgs)
    result = c.fetch_email_with_zip("srv", "e", "p", "from", "s")
    assert result == [b"A", b"B", b"C"]


def test_zip_same_day_sorted_by_time(monkeypatch) -> None:
    msgs = [
        FakeMsg("s", _dt(2026, 8, 1, 14, 20), [FakeAttachment("late.zip", b"LATE")]),
        FakeMsg("s", _dt(2026, 8, 1, 8, 30), [FakeAttachment("early.zip", b"EARLY")]),
    ]
    _install_mailbox(monkeypatch, msgs)
    result = c.fetch_email_with_zip("srv", "e", "p", "from", "s")
    assert result == [b"EARLY", b"LATE"]


def test_zip_subject_suffix_filters_messages(monkeypatch) -> None:
    msgs = [
        FakeMsg("relatorio_x", _dt(2026, 8, 1), [FakeAttachment("x.zip", b"X")]),
        FakeMsg("outro_assunto", _dt(2026, 8, 2), [FakeAttachment("y.zip", b"Y")]),
    ]
    captured, _ = _install_mailbox(monkeypatch, msgs)
    result = c.fetch_email_with_zip(
        "srv", "e", "p", "from", None, subject_suffix="relatorio_x"
    )
    assert result == [b"X"]
    # subject exato NAO deve entrar no filtro IMAP quando ha suffix.
    assert "subject" not in captured["criteria"]


# ---------------------------------------------------------------------------
# fetch_email_with_csv
# ---------------------------------------------------------------------------
def test_csv_returns_only_csv_attachments(monkeypatch) -> None:
    msg = FakeMsg(
        "assunto",
        _dt(2026, 8, 1),
        [FakeAttachment("a.csv", b"CSV"), FakeAttachment("b.zip", b"ZIP")],
    )
    _install_mailbox(monkeypatch, [msg])
    result = c.fetch_email_with_csv("srv", "e", "p", "from", "assunto")
    assert result == [b"CSV"]


def test_csv_range_criteria_and_ordering(monkeypatch) -> None:
    msgs = [
        FakeMsg("assunto", _dt(2026, 8, 10), [FakeAttachment("b.csv", b"B")]),
        FakeMsg("assunto", _dt(2026, 8, 3), [FakeAttachment("a.csv", b"A")]),
    ]
    captured, _ = _install_mailbox(monkeypatch, msgs)
    result = c.fetch_email_with_csv(
        "srv", "e", "p", "from", "assunto", start_date=date(2026, 8, 1)
    )
    assert result == [b"A", b"B"]
    assert captured["criteria"]["date_gte"] == date(2026, 8, 1)
