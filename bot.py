import os
from collections import defaultdict
import telebot
from dotenv import load_dotenv
import psycopg2
import psycopg2.sql as sql
#from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


load_dotenv()
token = os.getenv('TOKEN')
password = os.getenv('PASSWORD')

# conn = psycopg2.connect(user='postgres', password=password,
#                         host='127.0.0.1', port=5432)
#
# conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
# # Курсор для выполнения операций с базой данных
# cursor = conn.cursor()
# sql_create_database = 'CREATE DATABASE postgres_db'
# cursor.execute(sql_create_database)

conn = psycopg2.connect(user="postgres",
                        # пароль, который указали при установке PostgreSQL
                        password=password,
                        host="127.0.0.1",
                        port="5432",
                        database="postgres_db")


# with conn:
#     with conn.cursor() as cur:
#         cur.execute("CREATE TABLE locations (id SERIAL PRIMARY KEY, " +
#                     "user_id VARCHAR(64), location VARCHAR(64))")


bot = telebot.TeleBot(token)
START, ADD_NAME, ADD_LOCATION = range(3)
USER_STATE = defaultdict(lambda: START)


def get_state(message):
    return USER_STATE[message.chat.id]


def update_state(message, state):
    USER_STATE[message.chat.id] = state


def write_title_to_redis(message):
    user_id = message.chat.id
    location_title = message.text
    with conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO locations (user_id, location) VALUES(%s, %s)",
                        (user_id, location_title))


def write_coords_to_redis(user_id, location):
    lat, lon = location.latitude, location.longitude
    user_id = str(user_id)
    with conn:
        with conn.cursor() as cur:
            cur.execute(sql.SQL("SELECT location FROM locations WHERE user_id = {} ORDER BY id DESC")
                        .format(sql.Literal(user_id)))
            title = cur.fetchone()[0]
            full_location_data = f'{title}&#59;{lat}&#59;{lon}'
            cur.execute(sql.SQL("UPDATE locations SET user_id = %s, location = %s WHERE location = %s AND user_id = %s"),
                        (user_id, full_location_data, title, user_id))


@bot.message_handler(
    func=lambda message: get_state(message) == START, commands=['add']
)
def handle_title(message):
    bot.send_message(chat_id=message.chat.id, text='Введите название места:')
    update_state(message, ADD_NAME)


@bot.message_handler(
    func=lambda message: get_state(message) == ADD_NAME)
def handle_location(message):
    if message.text in ('/add', '/list', '/reset'):
        bot.send_message(chat_id=message.chat.id, text='Неверный формат ввода')
        update_state(message, START)
    else:
        write_title_to_redis(message)
        bot.send_message(chat_id=message.chat.id, text='Добавьте локацию:')
        update_state(message, ADD_LOCATION)


@bot.message_handler(
    func=lambda message: get_state(message) == ADD_LOCATION,
    content_types=['location']
)
def handle_confirmation(message):
    if message.location:
        update_state(message, START)
        write_coords_to_redis(message.chat.id, message.location)
        bot.send_message(
            chat_id=message.chat.id,
            text=f'Локация добавлена'
        )
    else:
        bot.send_message(chat_id=message.chat.id, text='Локация не задана')
        update_state(message, ADD_LOCATION)


@bot.message_handler(
    func=lambda x: True, commands=['list']
)
def handle_list(message):
    if get_state(message) != START:
        update_state(message, START)
        user_id = str(message.chat.id)
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql.SQL("DELETE FROM locations WHERE user_id = {}")
                            .format(sql.Literal(str(user_id))))
    else:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT location FROM locations ORDER BY id DESC LIMIT 10")
                last_locations = cur.fetchall()
        if last_locations:
            bot.send_message(chat_id=message.chat.id, text='Из последних 10 сохранённых локаций:')
            for location in last_locations:
                for s in location:
                    if '&#59;' in s:
                        title, lat, lon = s.split('&#59;')
                        bot.send_message(chat_id=message.chat.id, text=title)
                        bot.send_location(message.chat.id, lat, lon)
                    else:
                        bot.send_message(chat_id=message.chat.id, text=s)
        else:
            bot.send_message(chat_id=message.chat.id, text='Список локаций пуст')


@bot.message_handler(func=lambda x: True, commands=['reset'])
def handle_delete(message):
    user_id = str(message.chat.id)
    with conn:
        with conn.cursor() as cur:
            cur.execute(sql.SQL("DELETE FROM locations WHERE user_id = {}")
                        .format(sql.Literal(str(user_id))))
    bot.send_message(chat_id=message.chat.id, text='Данные очищены')


@bot.message_handler(func=lambda x: True, commands=['start'])
def handle_confirmation(message):
    bot.send_message(chat_id=message.chat.id, text='/add -- добавляет локацию')
    bot.send_message(chat_id=message.chat.id,
                     text='/list -- выводит 10 последних локаций')
    bot.send_message(chat_id=message.chat.id,
                     text='/reset -- удаляет все данные')


bot.polling()
