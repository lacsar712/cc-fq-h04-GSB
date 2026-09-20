from app.StageOrderPolicy import create_order_index, order_stages


class _S:
    def __init__(self, name, order):
        self.actor_name = name
        self.stage_order = order


def test_create_reversed():
    assert create_order_index(4, 0) == 3


def test_read_desc():
    rows = [_S("ParseActor", 0), _S("ReportActor", 3)]
    assert order_stages(rows)[0].actor_name == "ReportActor"
