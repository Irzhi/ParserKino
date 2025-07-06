import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime, timezone
import io

# Настройка страницы
st.set_page_config(
    page_title="Кинопоиск Парсер",
    page_icon="🎬",
    layout="wide"
)

# API URLs
API_URL = 'https://api.kinopoisk.dev/v1.4/movie/{}'
API_URL_STAFF = 'https://api.kinopoisk.dev/v1.4/person/search?query={}'
API_URL_REVIEWS = 'https://api.kinopoisk.dev/v1.4/review?movieId={}'

# Unofficial API для каста
UNOFFICIAL_API_STAFF = 'https://kinopoiskapiunofficial.tech/api/v1/staff'

def get_headers(api_key):
    return {
        'X-API-KEY': api_key,
        'Content-Type': 'application/json',
    }

def get_unofficial_headers(api_key):
    return {
        'X-API-KEY': api_key,
        'Content-Type': 'application/json',
    }

def format_money(value):
    if not value or value == '-' or value is None:
        return '-'
    
    if isinstance(value, dict):
        # Новый формат API - объект с валютой
        amount = value.get('value', 0)
        currency = value.get('currency', 'USD')
        if amount and amount > 0:
            formatted = f"{amount:,}".replace(",", " ")
            return f"{formatted} {currency}"
        return '-'
    
    # Обработка старого формата
    parts = str(value).split()
    if not parts or not parts[0].replace(',', '').replace(' ', '').isdigit():
        return value
    try:
        num = int(parts[0].replace(' ', '').replace(',', ''))
        currency = parts[1] if len(parts) > 1 and parts[1] else 'USD'
        formatted = f"{num:,}".replace(",", " ")
        return f"{formatted} {currency}".strip()
    except Exception as e:
        return value

def format_date(date_str):
    if not date_str or date_str == '-':
        return '-'
    try:
        dt = datetime.strptime(date_str[:10], '%Y-%m-%d')
        return dt.strftime('%d.%m.%Y')
    except Exception as e:
        return date_str

def format_duration(duration):
    """Форматирует продолжительность в минутах"""
    if not duration or duration == '-' or duration is None:
        return '-'
    try:
        minutes = int(duration)
        if minutes <= 0:
            return '-'
        return str(minutes)
    except (ValueError, TypeError):
        return str(duration) if duration else '-'

def format_vote_count(vote_count):
    """Форматирует количество голосов"""
    if not vote_count or vote_count == '-' or vote_count is None:
        return '-'
    try:
        count = int(vote_count)
        if count <= 0:
            return '-'
        # Форматируем с разделителями тысяч
        return f"{count:,}".replace(",", " ")
    except (ValueError, TypeError):
        return str(vote_count) if vote_count else '-'

def get_film_info(film_id, api_key):
    url = API_URL.format(film_id)
    try:
        response = requests.get(url, headers=get_headers(api_key), timeout=10)
        if response.status_code == 404:
            return None, f'Фильм с ID {film_id} не найден'
        if response.status_code != 200:
            return None, f'Ошибка: {response.status_code} — {response.text}'
        return response.json(), None
    except Exception as e:
        return None, f'Ошибка запроса: {e}'

def get_staff_from_unofficial_api(film_id, api_key):
    """Получает данные о съемочной группе из unofficial API"""
    try:
        url = f"{UNOFFICIAL_API_STAFF}?filmId={film_id}"
        response = requests.get(url, headers=get_unofficial_headers(api_key), timeout=10)
        
        if response.status_code == 404:
            return [], f'Данные о съемочной группе для фильма {film_id} не найдены'
        if response.status_code != 200:
            return [], f'Ошибка получения данных о съемочной группе: {response.status_code}'
        
        staff_data = response.json()
        return staff_data, None
        
    except Exception as e:
        return [], f'Ошибка при получении данных о съемочной группе: {e}'

def process_unofficial_staff_data(staff_data):
    """Обрабатывает данные о съемочной группе из unofficial API"""
    cast = []
    
    # Исключаемые профессии
    excluded_professions = [
        'монтажер', 'художник', 'editor', 'artist', 
        'монтажёр', 'звукорежиссёр', 'звукооператор',
        'costume designer', 'art director', 'set decorator',
        'EDITOR', 'DESIGN', 'PRODUCER_USSR'  # Добавляем ключи профессий
    ]
    
    for person in staff_data:
        # Получаем ключ профессии
        profession_key = person.get('professionKey', '').upper()
        profession_text = person.get('professionText', '').lower()
        
        # Проверяем исключения
        if profession_key in excluded_professions:
            continue
        if any(x in profession_text for x in excluded_professions):
            continue
        
        # Получаем имя (приоритет русскому)
        name_ru = person.get('nameRu', '').strip()
        name_en = person.get('nameEn', '').strip()
        name = name_ru if name_ru else name_en
        
        if not name:
            continue
        
        # Получаем ID
        staff_id = person.get('staffId')
        
        # Добавляем в список
        if staff_id:
            cast.append(f"{name};{staff_id}")
        else:
            cast.append(name)
    
    return cast

def get_film_cast(data, film_id, unofficial_api_key):
    """Извлекает информацию о съемочной группе"""
    cast = []
    
    # Сначала пробуем получить данные из unofficial API
    if unofficial_api_key:
        staff_data, error = get_staff_from_unofficial_api(film_id, unofficial_api_key)
        if staff_data and not error:
            cast = process_unofficial_staff_data(staff_data)
            if cast:  # Если получили данные из unofficial API, возвращаем их
                return cast, "Данные получены из Unofficial API"
    
    # Если не получилось из unofficial API, используем основной API
    persons = data.get('persons', [])
    
    for person in persons:
        # Получаем профессию на русском и английском
        profession_ru = person.get('profession', '').lower()
        profession_en = person.get('enProfession', '').lower()
        
        # Исключаем монтажеров и художников
        excluded_professions = [
            'монтажер', 'художник', 'editor', 'artist', 
            'монтажёр', 'звукорежиссёр', 'звукооператор',
            'costume designer', 'art director', 'set decorator'
        ]
        
        if any(x in profession_ru for x in excluded_professions) or \
           any(x in profession_en for x in excluded_professions):
            continue
        
        # Приоритет: русское имя, затем английское
        name = person.get('name') or person.get('enName') or '-'
        person_id = person.get('id')
        
        # Добавляем в список
        if person_id:
            cast.append(f"{name};{person_id}")
        else:
            cast.append(name)
    
    return cast, "Данные получены из основного API"

def get_film_boxoffice(data):
    """Извлекает информацию о кассовых сборах из данных фильма"""
    result = {}
    
    # В новом API информация о бюджете может быть в budget
    budget = data.get('budget')
    if budget:
        result['budget'] = format_money(budget)
    
    # Информация о сборах может быть в fees
    fees = data.get('fees', {})
    if fees:
        if 'world' in fees:
            result['world'] = format_money(fees['world'])
        if 'russia' in fees:
            result['russia'] = format_money(fees['russia'])
        if 'usa' in fees:
            result['usa'] = format_money(fees['usa'])
    
    return result

def get_film_premieres(data):
    """Извлекает информацию о премьерах из данных фильма"""
    premiere_rf = '-'
    premiere_world = '-'
    
    # Информация о премьерах в новом API
    premiere = data.get('premiere')
    if premiere:
        # Премьера в России
        if premiere.get('russia'):
            premiere_rf = format_date(premiere['russia'])
        
        # Мировая премьера
        if premiere.get('world'):
            premiere_world = format_date(premiere['world'])
    
    return premiere_rf, premiere_world

def create_excel_file(film_data, cast_data):
    """Создает Excel файл с данными о фильме"""
    output = io.BytesIO()
    
    try:
        # Очищаем данные от проблемных символов
        cleaned_film_data = {}
        for key, value in film_data.items():
            if isinstance(value, str):
                # Удаляем или заменяем проблемные символы
                cleaned_value = value.replace('\x00', '').replace('\ufeff', '')
                # Ограничиваем длину для Excel (максимум 32767 символов в ячейке)
                if len(cleaned_value) > 32000:
                    cleaned_value = cleaned_value[:32000] + "..."
                cleaned_film_data[key] = cleaned_value
            else:
                cleaned_film_data[key] = value
        
        # Основные данные фильма
        df_main = pd.DataFrame([cleaned_film_data])
        
        # Данные о касте
        cast_list = []
        for line in cast_data:
            if ';' in line:
                name, staff_id = line.split(';', 1)
                # Очищаем имя от проблемных символов
                clean_name = name.strip().replace('\x00', '').replace('\ufeff', '')
                if len(clean_name) > 255:  # Ограничение для имен
                    clean_name = clean_name[:255]
                cast_list.append({'Имя': clean_name, 'ID': staff_id.strip()})
            else:
                clean_name = line.strip().replace('\x00', '').replace('\ufeff', '')
                if len(clean_name) > 255:
                    clean_name = clean_name[:255]
                cast_list.append({'Имя': clean_name, 'ID': ''})
        
        df_cast = pd.DataFrame(cast_list)
        
        # Записываем в Excel с правильными настройками
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # Записываем основную информацию
            df_main.to_excel(writer, sheet_name='Основная информация', index=False)
            
            # Записываем данные о касте
            df_cast.to_excel(writer, sheet_name='Актеры и съемочная группа', index=False)
            
            # Получаем workbook и worksheet для настройки
            workbook = writer.book
            worksheet_main = writer.sheets['Основная информация']
            worksheet_cast = writer.sheets['Актеры и съемочная группа']
            
            # Настраиваем ширину столбцов
            worksheet_main.set_column('A:A', 25)  # Названия полей
            worksheet_main.set_column('B:B', 50)  # Значения
            
            worksheet_cast.set_column('A:A', 40)  # Имена
            worksheet_cast.set_column('B:B', 15)  # ID
            
            # Добавляем форматирование заголовков
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#D3D3D3',
                'border': 1
            })
            
            # Применяем форматирование к заголовкам
            for col_num, value in enumerate(df_main.columns.values):
                worksheet_main.write(0, col_num, value, header_format)
            
            for col_num, value in enumerate(df_cast.columns.values):
                worksheet_cast.write(0, col_num, value, header_format)
        
        output.seek(0)
        return output
        
    except Exception as e:
        # Если произошла ошибка, возвращаем улучшенную версию CSV
        st.error(f"Ошибка при создании Excel файла: {e}")
        return create_improved_csv_file(film_data, cast_data)

def create_improved_csv_file(film_data, cast_data):
    """Создает улучшенный CSV файл как альтернатива Excel"""
    output = io.BytesIO()
    
    # Создаем временный файл в памяти
    temp_output = io.StringIO()
    
    try:
        # Очищаем данные
        cleaned_film_data = {}
        for key, value in film_data.items():
            if isinstance(value, str):
                cleaned_value = value.replace('\x00', '').replace('\ufeff', '').replace('\n', ' ').replace('\r', ' ')
                cleaned_film_data[key] = cleaned_value
            else:
                cleaned_film_data[key] = value
        
        # Создаем DataFrame для основной информации
        df_main = pd.DataFrame([cleaned_film_data])
        
        # Создаем DataFrame для актеров
        cast_list = []
        for line in cast_data:
            if ';' in line:
                name, staff_id = line.split(';', 1)
                clean_name = name.strip().replace('\x00', '').replace('\ufeff', '').replace('\n', ' ').replace('\r', ' ')
                cast_list.append({'Имя': clean_name, 'ID': staff_id.strip()})
            else:
                clean_name = line.strip().replace('\x00', '').replace('\ufeff', '').replace('\n', ' ').replace('\r', ' ')
                cast_list.append({'Имя': clean_name, 'ID': ''})
        
        df_cast = pd.DataFrame(cast_list)
        
        # Записываем в CSV с правильной кодировкой
        temp_output.write("=== ОСНОВНАЯ ИНФОРМАЦИЯ ===\n")
        df_main.to_csv(temp_output, index=False, encoding='utf-8', sep=';', quoting=1)
        
        temp_output.write("\n=== АКТЕРЫ И СЪЕМОЧНАЯ ГРУППА ===\n")
        df_cast.to_csv(temp_output, index=False, encoding='utf-8', sep=';', quoting=1)
        
        # Получаем содержимое и кодируем с BOM для Excel
        content = temp_output.getvalue()
        temp_output.close()
        
        # Возвращаем байтовый поток с правильной кодировкой
        final_content = '\ufeff' + content
        output.write(final_content.encode('utf-8'))
        output.seek(0)
        
        return output
        
    except Exception as e:
        st.error(f"Ошибка при создании CSV файла: {e}")
        return None

def create_simple_csv_file(film_data, cast_data):
    """Создает простой CSV файл для универсального использования"""
    output = io.StringIO()
    
    # Создаем DataFrame для основной информации
    df_main = pd.DataFrame([film_data])
    
    # Создаем DataFrame для актеров
    cast_list = []
    for line in cast_data:
        if ';' in line:
            name, staff_id = line.split(';', 1)
            cast_list.append({'Имя': name.strip(), 'ID': staff_id.strip()})
        else:
            cast_list.append({'Имя': line.strip(), 'ID': ''})
    
    df_cast = pd.DataFrame(cast_list)
    
    # Записываем основную информацию
    output.write("=== ОСНОВНАЯ ИНФОРМАЦИЯ ===\n")
    df_main.to_csv(output, index=False, encoding='utf-8')
    
    output.write("\n=== АКТЕРЫ И СЪЕМОЧНАЯ ГРУППА ===\n")
    df_cast.to_csv(output, index=False, encoding='utf-8')
    
    content = output.getvalue()
    output.close()
    
    # Возвращаем с UTF-8 BOM для корректного отображения
    return io.BytesIO(('\ufeff' + content).encode('utf-8'))

# Инициализация сессии
if 'film_data' not in st.session_state:
    st.session_state.film_data = {}
if 'cast_data' not in st.session_state:
    st.session_state.cast_data = []
if 'data_source' not in st.session_state:
    st.session_state.data_source = ""

# Заголовок
st.title("🎬 Кинопоиск Парсер")
st.markdown("Получение информации о фильмах и сериалах через API kinopoisk.dev")

# Боковая панель для настроек
with st.sidebar:
    st.header("⚙️ Настройки")
    # Основной API ключ
    api_key = st.text_input("API-ключ (kinopoisk.dev):", 
                           type="password", 
                           value="MD4HZTA-3QZ4PVN-J8PP4XX-9NJQYFB",
                           help="Введите ваш API-ключ от kinopoisk.dev")

    # Дополнительный API ключ для unofficial API  
    unofficial_api_key = st.text_input("API-ключ (unofficial):", 
                                      type="password", 
                                      value="dbdf4ae6-c300-43ec-a20e-ee12baf53f74",
                                      help="Введите ваш API-ключ от kinopoiskapiunofficial.tech для более полной информации о съемочной группе")
    
    # Настройки получения данных
    st.subheader("📊 Настройки данных")
    use_unofficial_primary = st.checkbox("Приоритет unofficial API для каста", value=True, help="Если включено, данные о съемочной группе будут получаться в первую очередь из unofficial API")
    
    if st.button("ℹ️ Как получить API-ключи?"):
        st.info("""
        **Основной API (kinopoisk.dev):**
        1. Зарегистрируйтесь на kinopoisk.dev
        2. Получите бесплатный API-ключ
        
        **Unofficial API (kinopoiskapiunofficial.tech):**
        1. Зарегистрируйтесь на kinopoiskapiunofficial.tech
        2. Получите API-ключ для более детальной информации о съемочной группе
        
        Unofficial API предоставляет более подробную информацию о ролях актеров!
        """)

# Основной интерфейс
col1, col2 = st.columns([1, 3])

with col1:
    st.header("🔍 Поиск")
    film_id = st.text_input("ID фильма/сериала:", placeholder="Например: 2013")
    
    if st.button("🎯 Получить информацию", type="primary"):
        if not api_key:
            st.error("⚠️ Введите основной API-ключ в боковой панели!")
        elif not film_id.isdigit():
            st.error("⚠️ Введите корректный числовой ID!")
        else:
            with st.spinner("Загрузка данных..."):
                # Получаем основную информацию
                data, error = get_film_info(film_id, api_key)
                
                if error or not data:
                    st.error(f"❌ {error or 'Нет данных'}")
                else:
                    # Собираем всю информацию
                    def safe(val):
                        return '-' if val is None or val == '' else val
                    
                    # Извлекаем рейтинги
                    rating_kp = '-'
                    rating_imdb = '-'
                    votes_kp = '-'
                    
                    if 'rating' in data:
                        rating_data = data['rating']
                        # Округляем рейтинг КП до одного знака после запятой
                        kp_rating = rating_data.get('kp')
                        if kp_rating and kp_rating != '-' and kp_rating is not None:
                            try:
                                rating_kp = str(round(float(kp_rating), 1))
                            except (ValueError, TypeError):
                                rating_kp = safe(kp_rating)
                        else:
                            rating_kp = '-'
                        
                        rating_imdb = safe(rating_data.get('imdb'))
                    
                    # Извлекаем количество голосов из votes.kp
                    if 'votes' in data:
                        votes_data = data['votes']
                        votes_kp = format_vote_count(votes_data.get('kp'))
                    
                    # Извлекаем жанры
                    genres = []
                    if 'genres' in data:
                        for genre in data['genres']:
                            if isinstance(genre, dict) and 'name' in genre:
                                genres.append(genre['name'])
                            elif isinstance(genre, str):
                                genres.append(genre)
                    
                    # Извлекаем страны
                    countries = []
                    if 'countries' in data:
                        for country in data['countries']:
                            if isinstance(country, dict) and 'name' in country:
                                countries.append(country['name'])
                            elif isinstance(country, str):
                                countries.append(country)
                    
                    # Основная информация
                    film_info = {
                        'Название (RU)': safe(data.get('name')),
                        'Оригинальное название': safe(data.get('alternativeName') or data.get('enName')),
                        'Год': safe(data.get('year')),
                        'Жанры': safe(', '.join(genres) if genres else '-'),
                        'Страна': safe(', '.join(countries) if countries else '-'),
                        'Рейтинг IMDB': safe(rating_imdb),
                        'Рейтинг Кинопоиска': safe(rating_kp),
                        'Кол-во оценок КП': safe(votes_kp),
                        'Описание': safe(data.get('description')),
                        'Продолжительность (мин)': format_duration(data.get('movieLength'))
                    }
                    
                    # Касса
                    boxoffice = get_film_boxoffice(data)
                    film_info.update({
                        'Бюджет': boxoffice.get('budget', '-'),
                        'Сборы в мире': boxoffice.get('world', '-'),
                        'Сборы в России': boxoffice.get('russia', '-'),
                        'Сборы в США': boxoffice.get('usa', '-')
                    })
                    
                    # Премьеры
                    premiere_rf, premiere_world = get_film_premieres(data)
                    film_info.update({
                        'Премьера в России': safe(premiere_rf),
                        'Премьера в мире': safe(premiere_world)
                    })
                    
                    # Актеры и съемочная группа
                    cast, data_source = get_film_cast(data, film_id, unofficial_api_key if use_unofficial_primary else None)
                    
                    st.session_state.film_data = film_info
                    st.session_state.cast_data = cast
                    st.session_state.data_source = data_source
                    
                    st.success("✅ Данные успешно загружены!")

with col2:
    st.header("📊 Результаты")
    
    if st.session_state.film_data:
        # Показываем источник данных о съемочной группе
        if st.session_state.data_source:
            st.info(f"ℹ️ {st.session_state.data_source}")
        
        # Основная информация
        st.subheader("🎭 Основная информация")
        
        # Отображаем информацию в виде метрик и полей
        col_info1, col_info2 = st.columns(2)
        
        with col_info1:
            st.metric("Название (RU)", st.session_state.film_data.get('Название (RU)', '-'))
            st.metric("Год", st.session_state.film_data.get('Год', '-'))
            st.metric("Рейтинг IMDB", st.session_state.film_data.get('Рейтинг IMDB', '-'))
            st.metric("Премьера в России", st.session_state.film_data.get('Премьера в России', '-'))
            st.metric("Премьера в мире", st.session_state.film_data.get('Премьера в мире', '-'))
        
        with col_info2:
            st.metric("Оригинальное название", st.session_state.film_data.get('Оригинальное название', '-'))
            st.metric("Страна", st.session_state.film_data.get('Страна', '-'))
            st.metric("Рейтинг Кинопоиска", st.session_state.film_data.get('Рейтинг Кинопоиска', '-'))
            st.metric("Кол-во оценок КП", st.session_state.film_data.get('Кол-во оценок КП', '-'))
            st.metric("Продолжительность (мин)", st.session_state.film_data.get('Продолжительность (мин)', '-'))
        
        # Жанры отдельно на всю ширину
        st.metric("Жанры", st.session_state.film_data.get('Жанры', '-'))
        
        # Описание
        st.subheader("📝 Описание")
        st.write(st.session_state.film_data.get('Описание', '-'))
        
        # Финансы
        st.subheader("💰 Финансы")
        col_money1, col_money2 = st.columns(2)
        
        with col_money1:
            st.metric("Бюджет", st.session_state.film_data.get('Бюджет', '-'))
            st.metric("Сборы в мире", st.session_state.film_data.get('Сборы в мире', '-'))
        
        with col_money2:
            st.metric("Сборы в России", st.session_state.film_data.get('Сборы в России', '-'))
            st.metric("Сборы в США", st.session_state.film_data.get('Сборы в США', '-'))
        
        # Актеры и съемочная группа
        st.subheader("🎬 Актеры и съемочная группа")
        
        if st.session_state.cast_data:
            # Создаем DataFrame для отображения
            cast_display = []
            for line in st.session_state.cast_data:
                if ';' in line:
                    name, staff_id = line.split(';', 1)
                    cast_display.append({'Имя': name.strip(), 'ID': staff_id.strip()})
                else:
                    cast_display.append({'Имя': line.strip(), 'ID': ''})
            
            if cast_display:
                df_cast = pd.DataFrame(cast_display)
                st.dataframe(df_cast, use_container_width=True)
            else:
                st.write("Нет данных о съемочной группе")
        else:
            st.write("Нет данных о съемочной группе")
        
        # Кнопка экспорта
        st.subheader("📥 Экспорт данных")
        
        col_export1, col_export2 = st.columns(2)
        
        with col_export1:
            if st.session_state.film_data and st.session_state.cast_data:
                excel_file = create_excel_file(st.session_state.film_data, st.session_state.cast_data)
                filename = f"film_{film_id}.xlsx"
                st.download_button(
                    label="📊 Скачать Excel файл",
                    data=excel_file,
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="excel_download"
                )
        
        with col_export2:
            if st.session_state.film_data and st.session_state.cast_data:
                # CSV для Excel
                csv_file = create_improved_csv_file(st.session_state.film_data, st.session_state.cast_data)
                filename_csv = f"film_{film_id}.csv"
                st.download_button(
                    label="📄 CSV (для Excel)",
                    data=csv_file,
                    file_name=filename_csv,
                    mime="text/csv",
                    key="csv_download_1"
                )
                # Простой CSV
                csv_simple_file = create_simple_csv_file(st.session_state.film_data, st.session_state.cast_data)
                filename_csv_simple = f"film_{film_id}.csv"
                st.download_button(
                    label="📋 CSV (простой)",
                    data=csv_simple_file,
                    file_name=filename_csv_simple,
                    mime="text/csv",
                    key="csv_download_2"
                )
        
        # Дополнительные советы по экспорту
        with st.expander("💡 Советы по экспорту"):
            st.markdown("""
            **Если возникают проблемы с Excel файлом:**
            1. Попробуйте скачать CSV файл вместо Excel
            2. При открытии CSV в Excel выберите разделитель "точка с запятой" (;)
            3. Убедитесь, что у вас установлены все необходимые библиотеки
            
            **Форматы файлов:**
            - **Excel**: Удобен для просмотра и редактирования
            - **CSV для Excel**: Совместим с Excel, использует точку с запятой
            - **CSV простой**: Универсальный формат для любых программ
            
            **Для установки недостающих библиотек:**
            ```
            pip install xlsxwriter openpyxl
            ```
            """)
        
    else:
        st.info("👈 Введите ID фильма и нажмите 'Получить информацию'")

# Футер
st.markdown("---")
st.markdown("**Создано с помощью Streamlit** • [Kinopoisk.dev API](https://kinopoisk.dev/)")
