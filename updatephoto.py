import os
import datetime
import asyncio
from PIL import Image, ImageDraw, ImageFont
from collections import OrderedDict
from apscheduler.schedulers.blocking import BlockingScheduler

from telethon import TelegramClient, events, sync
from telethon.tl.functions.channels import EditPhotoRequest, GetFullChannelRequest
from telethon.tl.types import InputChatUploadedPhoto
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest
from telethon.utils import get_input_photo

STRIP_WIDTH, STRIP_HEIGHT = 500, 500
WEATHER_APPID = os.environ.get('WEATHER_APPID')
TELEGRAM_API_ID = int(os.environ.get('TELEGRAM_API_ID'))
TELEGRAM_API_HASH = os.environ.get('TELEGRAM_API_HASH')
CHANNEL_NAME = os.environ.get('CHANNEL_NAME')
PHONE = os.environ.get('PHONE')


def delete_file(filepath):
    try:
        os.remove(filepath)
    except OSError:
        pass


def generate_key(args):
    return hash(args)


def memoize(*, size=float('inf')):
    def memoize_decorator(f):
        cache = OrderedDict()
        
        def wrapper(*args):
            nonlocal cache
            key = generate_key(args)
            val = cache.get(key)

            if val:
                return val        

            res = f(*args)

            if len(cache) >= size:
                file = cache.popitem()
                delete_file(file[0])

            cache[key] = res
            return res

        return wrapper
    return memoize_decorator
    

@memoize(size=100)
def create_photo(degrees):
    """
    returns path to file
    """
    img = Image.new("RGB", (STRIP_WIDTH, STRIP_HEIGHT), color="black")
    font = ImageFont.truetype('ComicSans.ttf', 120)
    text = f'{"{:+.2f}".format(degrees)}°'

    file_link = f'photos/{str(degrees)}.png'
    center_text(img, font, text, (255,96,55)).save(file_link)

    return file_link


def center_text(img, font, text, color=(255, 255, 255)):
    draw = ImageDraw.Draw(img)
    text_width, text_height = draw.textsize(text, font)
    position = ((STRIP_WIDTH-text_width)/2,(STRIP_HEIGHT-text_height)/2)
    draw.text(position, text, color, font=font)
    return img


def get_weather():
    import requests

    params = {
        'appid': WEATHER_APPID,
        'id': 703448,
        'units': 'metric',
    }
    url = f'http://api.openweathermap.org/data/2.5/weather'

    data = requests.get(url, params=params).json()

    return data.get('main').get('temp')


async def update_channel_photo(photo, channel_link):
    client = TelegramClient('upd phototemp',
                            TELEGRAM_API_ID,
                            TELEGRAM_API_HASH,
                        )

    if not client.is_connected():
        await client.start(PHONE)

    dialogs = await client.get_dialogs()
    channel_entity = await client.get_entity(channel_link)
    upload_file_result = await client.upload_file(file=photo)

    try:        
        result = await client(EditPhotoRequest(channel=channel_entity, 
            photo=upload_file_result))
    except BaseException as e:
        print(e)

    await client.disconnect()

    print('finish')


async def update_user_photo(photo):
    client = TelegramClient('upd phototemp',
                            TELEGRAM_API_ID,
                            TELEGRAM_API_HASH,
                        )

    if not client.is_connected():
        await client.start(PHONE)
    
    await client(DeletePhotosRequest(await client.get_profile_photos('me')))
    await client(UploadProfilePhotoRequest(
        await client.upload_file(photo)
    ))

    await client.disconnect()

    print('finish')


# @SCHED.scheduled_job('interval', minutes=1)
def change_photo():
    deg = get_weather()
    new_img = create_photo(deg)
    print(create_photo.__closure__[0].cell_contents)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # asyncio.get_event_loop().run_until_complete(update_channel_photo(
    #     new_img,
    #     CHANNEL_NAME,
    # ))
    asyncio.get_event_loop().run_until_complete(update_user_photo(
        new_img,
    ))
    loop.close()

    print(new_img)


if __name__ == "__main__":
    scheduler = BlockingScheduler()
    scheduler.add_job(change_photo, 'interval', minutes=30)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass

    photo_dir = 'photos/'
    for file in os.listdir(photo_dir):
        delete_file(photo_dir + file)