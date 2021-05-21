import os
from collections import defaultdict
import telebot
import redis
from dotenv import load_dotenv

load_dotenv()
token = os.getenv('TOKEN')
bot = telebot.TeleBot(token)
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
r = redis.from_url(redis_url, db=0, decode_responses=True)
START, ADD_NAME, ADD_LOCATION = range(3)
USER_STATE = defaultdict(lambda: START)


def get_state(message):
    return USER_STATE[message.chat.id]


def update_state(message, state):
    USER_STATE[message.chat.id] = state


def write_title_to_redis(message):
    user_id = message.chat.id
    location_title = message.text
    r.lpush(user_id, location_title)


def write_coords_to_redis(user_id, location):
    lat, lon = location.latitude, location.longitude
    title = r.lpop(user_id)
    full_location_data = f'{title}&#59;{lat}&#59;{lon}'
    r.lpush(user_id, full_location_data)


def delete_location(user_id):
    r.lpop(user_id)


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
        r.lpop(message.chat.id)
    else:
        last_locations = r.lrange(message.chat.id, 0, 10)
        if last_locations:
            bot.send_message(chat_id=message.chat.id, text='Из последних 10 сохранённых локаций:')
            for location in last_locations:
                if '&#59;' in location:
                    title, lat, lon = location.split('&#59;')
                    bot.send_message(chat_id=message.chat.id, text=title)
                    bot.send_location(message.chat.id, lat, lon)
                else:
                    bot.send_message(chat_id=message.chat.id, text=location)
        else:
            bot.send_message(chat_id=message.chat.id, text='Список локаций пуст')


@bot.message_handler(func=lambda x: True, commands=['reset'])
def handle_confirmation(message):
    r.flushdb()
    bot.send_message(chat_id=message.chat.id, text='Данные очищены')


@bot.message_handler(func=lambda x: True, commands=['start'])
def handle_confirmation(message):
    bot.send_message(chat_id=message.chat.id, text='/add -- добавляет локацию')
    bot.send_message(chat_id=message.chat.id,
                     text='/list -- выводит 10 последних локаций')
    bot.send_message(chat_id=message.chat.id,
                     text='/reset -- удаляет все данные')


bot.polling()

