import sys
import requests

from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from icalendar import Calendar, Event, Alarm
from datetime import datetime
from datetime import datetime, timedelta
from math import *

sys.stdout.reconfigure(encoding='utf-8')

# Словарь для сдвига дней относительно понедельника
DAYS_MAP = {
    'Понедельник': 0, 'Вторник': 1, 'Среда': 2, 
    'Четверг': 3, 'Пятница': 4, 'Суббота': 5, 'Воскресенье': 6
}

# Задаем понедельник текущей учебной недели (21 сентября 2026 года)
# FIXME: преобразовать логику (автоподбор ближайших недель и распределение их по четной и нечетной)
START_DATE_ODD = datetime(2026, 9, 28)
START_DATE_EVEN = datetime(2026, 10, 5)
WEEKDAY_NOW = datetime.now().weekday() + 1

current_week = 'нижняя' if WEEKDAY_NOW % 2 == 0 else 'верхняя'

def text_to_datetime(day_name, time_str, basedate):
    hours, minutes = map(int, time_str.split(':'))
    day_offset = DAYS_MAP.get(day_name, 0)
    target_date = basedate + timedelta(days=day_offset)
    
    # Жестко фиксируем часовой пояс (MSK)
    return target_date.replace(
        hour=hours, 
        minute=minutes, 
        second=0, 
        tzinfo=ZoneInfo("Europe/Moscow")
    )

sys.stdout.reconfigure(encoding='utf-8')

def get_schedule_html(url):
    # Скачиваем страницу
    response = requests.get(url)
    response.raise_for_status()
    response.encoding = 'utf-8'
    return response.text

def parse_and_create_ics(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    cal = Calendar()

    cal.add('prodid', '-//Schedule Bot//')
    cal.add('version', '2.0')
    
    lessons = soup.find_all('div', class_='mb-3 py-2 d-flex gap-2')
    previous_day = None

    for lesson in lessons:
        # Ищем день недели: смотрим на ближайший заголовок h4 ПЕРЕД парой
        day_block = lesson.find_previous_sibling('h4')
        day_name = day_block.text.strip() if day_block else "-"

        title = lesson.find('div', class_='lead lh-sm').text.strip()
        description = lesson.find('div', class_='fs-6 lh-sm opacity-50').text.strip()
        location = lesson.find('a').text.strip()

        attr_title = lesson.find('div', class_='week1').get('title')\
            if lesson.find('div', class_='week1')\
                else lesson.find('div', class_='week2').get('title')\
                    if lesson.find('div', class_='week2') else '-'

        week = attr_title.split()[0] if attr_title != '-' else '-'

        if week == 'нижняя':
            current_base = START_DATE_EVEN
            repeat_interval = 2
        elif week == 'верхняя':
            current_base = START_DATE_ODD
            repeat_interval = 2
        else:
            current_base = START_DATE_ODD
            repeat_interval = 1

        time_block = lesson.find_previous_sibling('div', class_='mt-3 text-danger')
        start_time, end_time = "-", "-"

        if time_block:
            time_small = time_block.find('small', class_='opacity-50')

            if time_small:
                # Срезаем круглые скобки
                raw_time = time_small.text.strip()[1:-1]
                times = raw_time.split('—')

                if len(times) == 2:
                    start_time = text_to_datetime(day_name, times[0].strip(), current_base)
                    end_time = text_to_datetime(day_name, times[1].strip(), current_base)

        if "Вне сетки" in day_name or start_time == "-":
            continue
    
        event = Event()
        
        event.add('summary', title)
        event.add('description', description)
        event.add('location', location)
        event.add('dtstart', start_time)
        event.add('dtend', end_time)

        event.add('rrule', {
            'freq': 'weekly',
            'interval': repeat_interval,
            'until': datetime(2026, 12, 20)
            })

        if day_name != previous_day and day_name != "-":
            alarm = Alarm()
            alarm.add('action', 'DISPLAY')
            alarm.add('description', f'Первая пара: {title}')
            
            # Устанавливаем уведомление за 45 минут до начала (можно изменить)
            alarm.add('trigger', timedelta(minutes=-75))
            
            event.add_component(alarm)
            
            # Обновляем память скрипта, чтобы на следующих парах этого дня будильник не ставился
            previous_day = day_name

        cal.add_component(event)
    
    # Сохраняем в файл .ics
    with open('schedule.ics', 'wb') as f:
        f.write(cal.to_ical())
    print("Файл schedule.ics успешно создан!")

# Запуск парсера
url = "https://guap.ru/rasp?gr=7852"
html = get_schedule_html(url)
parse_and_create_ics(html)