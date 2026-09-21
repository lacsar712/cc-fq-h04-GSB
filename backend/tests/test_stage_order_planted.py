from app.StageOrderPolicy import create_order_index, order_stages


class _S:
    def __init__(self, name, order):
        self.actor_name = name
        self.stage_order = order


def test_create_index_follows_chain():
    assert create_order_index(4, 0) == 0
    assert create_order_index(4, 3) == 3


def test_read_ascending():
    rows = [
        _S("NContentActor", 2),
        _S("ReportActor", 3),
        _S("ParseActor", 0),
        _S("QualityHistActor", 1),
    ]
    ordered = order_stages(rows)
    assert [s.actor_name for s in ordered] == [
        "ParseActor",
        "QualityHistActor",
        "NContentActor",
        "ReportActor",
    ]
    assert [s.stage_order for s in ordered] == [0, 1, 2, 3]
