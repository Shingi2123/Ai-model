from virtual_persona.utils.time_utils import infer_time_of_day


def test_infer_time_of_day():
    assert infer_time_of_day(6) == "morning"
    assert infer_time_of_day(13) == "afternoon"
    assert infer_time_of_day(19) == "evening"
    assert infer_time_of_day(23) == "night"
