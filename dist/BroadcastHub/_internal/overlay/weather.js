const WEATHER_API_KEY = "3fb5ee649521ecdf2c43089cdf52d21e";
const CITY = "Seoul";

function isNight(now, sunrise, sunset) {
  return now < sunrise || now > sunset;
}

function getWeatherIcon(code, night) {
  if (code >= 200 && code < 600) return "🌧️";   // 비
  if (code >= 600 && code < 700) return "❄️";   // 눈
  if (code >= 700 && code < 800) return "🌫️";   // 안개
  if (code === 800) return night ? "🌙" : "☀️"; // 맑음
  if (code > 800) return "☁️";                  // 구름
  return "❓";
}

async function loadWeather() {
  try {
    // 현재 + 예보
    const currentRes = await fetch(
      `https://api.openweathermap.org/data/2.5/weather?q=${CITY}&units=metric&lang=kr&appid=${WEATHER_API_KEY}`
    );
    const forecastRes = await fetch(
      `https://api.openweathermap.org/data/2.5/forecast?q=${CITY}&units=metric&lang=kr&appid=${WEATHER_API_KEY}`
    );

    const current = await currentRes.json();
    const forecast = await forecastRes.json();

    const now = current.dt;
    const sunrise = current.sys.sunrise;
    const sunset = current.sys.sunset;

    const night = isNight(now, sunrise, sunset);
    const icon = getWeatherIcon(current.weather[0].id, night);

    // 오늘
    document.getElementById("weather-icon").innerText = icon;
    document.getElementById("weather-temp").innerText =
      `${Math.round(current.main.temp)}°C`;
    document.getElementById("weather-desc").innerText =
      current.weather[0].description;

    document.getElementById("today-min").innerText =
      Math.round(current.main.temp_min);
    document.getElementById("today-max").innerText =
      Math.round(current.main.temp_max);

    // 내일 (forecast 중 날짜 기준)
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const tDate = tomorrow.getDate();

    const tomorrowItems = forecast.list.filter(item =>
      new Date(item.dt * 1000).getDate() === tDate
    );

    const temps = tomorrowItems.map(i => i.main.temp);
    const codes = tomorrowItems.map(i => i.weather[0].id);

    document.getElementById("tomorrow-min").innerText =
      Math.round(Math.min(...temps));
    document.getElementById("tomorrow-max").innerText =
      Math.round(Math.max(...temps));
    document.getElementById("tomorrow-icon").innerText =
      getWeatherIcon(codes[0], false);

  } catch {
    document.getElementById("weather-temp").innerText = "--°C";
  }
}

loadWeather();
setInterval(loadWeather, 10 * 60 * 1000);

