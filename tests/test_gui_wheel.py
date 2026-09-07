"""マウスホイールの配送先決定のテスト（tkinter なしで動く）。"""

from __future__ import annotations

from cisetup import wheel_routing as wheel


class FakeScrollable:
    """yview / yview_scroll を持つウィジェットの代役。"""

    def __init__(self, first: float = 0.0, last: float = 1.0, master=None, is_log: bool = False):
        self._view = (first, last)
        self.master = master
        self.scrolled: list[int] = []
        if is_log:
            setattr(self, wheel.LOG_WIDGET_FLAG, True)

    def yview(self):
        return self._view

    def yview_scroll(self, units: int, _what: str) -> None:
        self.scrolled.append(units)


def test_scroll_widget_moves_when_room_remains():
    w = FakeScrollable(0.2, 0.6)
    assert wheel.scroll_widget(w, 3) is True
    assert w.scrolled == [3]


def test_scroll_widget_stops_at_top_and_bottom():
    top = FakeScrollable(0.0, 0.5)
    assert wheel.scroll_widget(top, -1) is False
    assert top.scrolled == []

    bottom = FakeScrollable(0.5, 1.0)
    assert wheel.scroll_widget(bottom, 1) is False
    assert bottom.scrolled == []


def test_scroll_widget_ignores_widgets_without_view():
    class NoView:
        def yview(self):
            raise RuntimeError("not scrollable")

    assert wheel.scroll_widget(NoView(), 1) is False
    assert wheel.scroll_widget(None, 1) is False


def test_find_log_widget_walks_up_from_child():
    log = FakeScrollable(is_log=True)
    child = FakeScrollable(master=log)
    grandchild = FakeScrollable(master=child)
    assert wheel.find_log_widget(grandchild) is log


def test_find_log_widget_returns_none_outside_a_log():
    plain = FakeScrollable(master=FakeScrollable())
    assert wheel.find_log_widget(plain) is None


def test_route_scrolls_the_log_under_the_pointer():
    log = FakeScrollable(0.2, 0.6, is_log=True)
    page = FakeScrollable()
    assert wheel.route(log, page, 2) == wheel.TARGET_LOG
    assert log.scrolled == [2]
    assert page.scrolled == []


def test_route_falls_through_to_the_page_at_the_log_edge():
    # ログの末尾まで来たらページを送る（行き止まりにしない）
    log = FakeScrollable(0.4, 1.0, is_log=True)
    page = FakeScrollable()
    assert wheel.route(log, page, 1) == wheel.TARGET_PAGE
    assert log.scrolled == []
    assert page.scrolled == [1]


def test_route_scrolls_the_page_outside_a_log():
    # ログにフォーカスが残っていても、ポインタがページ上ならページを送る
    page = FakeScrollable()
    assert wheel.route(FakeScrollable(), page, -1) == wheel.TARGET_PAGE
    assert page.scrolled == [-1]


def test_route_handles_pointer_outside_the_window():
    page = FakeScrollable()
    assert wheel.route(None, page, 1) == wheel.TARGET_PAGE
    assert page.scrolled == [1]


def test_route_does_nothing_without_movement_or_page():
    log = FakeScrollable(0.2, 0.6, is_log=True)
    assert wheel.route(log, FakeScrollable(), 0) == wheel.TARGET_NONE
    assert log.scrolled == []
    assert wheel.route(FakeScrollable(), None, 1) == wheel.TARGET_NONE
