from virtual_persona.services.weather import WeatherService


def test_normalize_weather_clear():
    assert WeatherService.normalize_condition("Clear", 10) == "clear"


def test_normalize_weather_cloudy():
    assert WeatherService.normalize_condition("Clouds", 90) == "cloudy"


def test_normalize_weather_rain():
    assert WeatherService.normalize_condition("Rain", 50, rain_mm=1.2) == "rain_light"
