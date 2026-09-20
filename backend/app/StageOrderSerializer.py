from app.StageOrderPolicy import order_stages


def stages_for_response(stages):
    return order_stages(list(stages or []))
