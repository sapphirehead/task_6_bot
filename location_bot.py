# Bot on sqlite3
import os
from collections import defaultdict
import telebot
from dotenv import load_dotenv
import sqlite3

load_dotenv()
token = os.getenv('TOKEN')
conn = sqlite3.connect('sqlite_bot.db')
cur = conn.cursor()

try:
    cur.execute("CREATE TABLE locations (id SERIAL PRIMARY KEY, " +
                "user_id VARCHAR(64), location VARCHAR(64))")
    conn.commit()
except sqlite3.Error:
    pass
finally:
    if (conn):
        conn.close()

bot = telebot.TeleBot(token)
START, ADD_NAME, ADD_LOCATION = range(3)
USER_STATE = defaultdict(lambda: START)


def get_state(message):
    return USER_STATE[message.chat.id]


def update_state(message, state):
    USER_STATE[message.chat.id] = state


def write_title_to_sql(message):
    user_id = message.chat.id
    location_title = message.text
    try:
        conn = sqlite3.connect('sqlite_bot.db')
        cur = conn.cursor()
        cur.execute("INSERT INTO locations (user_id, location) VALUES('{}', '{}')".format(user_id, location_title))
        conn.commit()
        cur.close()
    except sqlite3.Error:
        pass
    finally:
        if (conn):
            conn.close()


def write_coords_to_sql(user_id, location):
    lat, lon = location.latitude, location.longitude
    user_id = str(user_id)
    try:
        conn = sqlite3.connect('sqlite_bot.db')
        cur = conn.cursor()
        cur.execute("SELECT location FROM locations WHERE user_id = '{}' ORDER BY id DESC".format(user_id))
        title = cur.fetchone()[0]
        full_location_data = f'{title}&#59;{lat}&#59;{lon}'
        cur.execute("UPDATE locations SET user_id = '{}', location = '{}' WHERE location = '{}' AND user_id = '{}'".format(user_id, full_location_data, title, user_id))
        conn.commit()
        cur.close()
    except sqlite3.Error:
        pass
    finally:
        if (conn):
            conn.close()


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
        write_title_to_sql(message)
        bot.send_message(chat_id=message.chat.id, text='Добавьте локацию:')
        update_state(message, ADD_LOCATION)


@bot.message_handler(
    func=lambda message: get_state(message) == ADD_LOCATION,
    content_types=['location']
)
def handle_confirmation(message):
    if message.location:
        update_state(message, START)
        write_coords_to_sql(message.chat.id, message.location)
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
        try:
            conn = sqlite3.connect('sqlite_bot.db')
            cur = conn.cursor()
            cur.execute("DELETE FROM locations WHERE user_id = '{}'".format(str(user_id)))
            cur.close()
        except sqlite3.Error:
            pass
        finally:
            if (conn):
                conn.close()
    else:
        try:
            conn = sqlite3.connect('sqlite_bot.db')
            cur = conn.cursor()
            cur.execute("SELECT location FROM locations ORDER BY id DESC LIMIT 10")
            last_locations = cur.fetchall()
            cur.close()
        except sqlite3.Error:
            pass
        finally:
            if (conn):
                conn.close()
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
    try:
        conn = sqlite3.connect('sqlite_bot.db')
        cur = conn.cursor()
        cur.execute("DELETE FROM locations WHERE user_id = '{}'".format(str(user_id)))
        conn.commit()
        cur.close()
    except sqlite3.Error:
        pass
    finally:
        if (conn):
            conn.close()
    bot.send_message(chat_id=message.chat.id, text='Данные очищены')


@bot.message_handler(func=lambda x: True, commands=['start'])
def handle_confirmation(message):
    bot.send_message(chat_id=message.chat.id, text='/add -- добавляет локацию\n'
                                                   '/list -- выводит 10 последних локаций\n'
                                                   '/reset -- удаляет все данные')


bot.polling()
