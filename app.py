import asyncio
import json
import math
import os
import sqlite3
import sys
from datetime import datetime

import discord
import requests
from discord.ext import commands, tasks
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

ops = Options()
ops.add_argument('--headless')
ops.add_argument('--ignore-certificate-errors')
ops.add_argument('--ignore-ssl-errors')
driver = webdriver.Chrome(options=ops)
client = commands.Bot(command_prefix='!')
BOT_TOKEN = 'TOKEN'  # This is the TOKEN of the bot user that you created

DM_ALLOWED = True  # Set this to True or False (case sensitive) if you want to allow or deny DM notifications for tracking
ROLE_ALLOWED_TO_TRACK = 'Market'

s = requests.sessions.Session()
email = ("XXX")
password = ("YYY")
launched=0

def to_json():
    original = driver.find_element_by_tag_name('pre').text
    return json.loads(original)


def main():
    mygames_login()


def update_server_info(message):
    found_flag = False
    con, cur = get_db_con()
    guild_id = message.guild.id
    cur.execute(f'DELETE FROM server_info WHERE guild_id="{guild_id}"')
    for channel in client.get_guild(guild_id).channels:
        if str(channel).lower() == 'reports':
            reports_channel_id = channel.id
            found_flag = True
            break
    if found_flag is False:
        reports_channel_id = str(644620899055829031)
    con.commit()

    cur.execute('INSERT INTO server_info VALUES(?, ?);', (guild_id, reports_channel_id))
    con.commit()
    con.close()


# discord has limitation per sending message (aprox: 2000, but for safety 1000)
def check_2000LIMIT(string):
    splited = []
    temp = ''
    for i in string:
        temp = "%s%s" % (temp, i)
        if len(temp) > 1000:
            splited.append("".join(temp))
            temp = ''
    if len(temp) > 0:
        splited.append("".join(temp))
    return splited


# check if response is valid, and add header footer
def header_footer(string, types=None):
    if types is None:
        head = 'ITEM'
    else:
        head = str(types).upper()
    if type(string) is list and len(string) >= 1:
        total = len(string)
        if types != 'weapon':
            string = string[:2]
        string[0] = "\nINDEX     {}".format(head) + string[0]

        if types != 'weapon' and total > 2:
            string[-1] = string[
                             -1] + "\n\nYour keyword doesn't appear for a specific item, just showing 2 pages of {} pages because there are too many records.".format(
                total)
        else:
            string[-1] = string[-1] + "\n\nReply with the index to show the picture within 20 seconds"
    else:
        string = "Could not find anything you search. Item is not in the market yet"
    return string


# Search for all kind of items
mp_list = {}


def search_all(name, types=None, user_id=None):
    global mp_list, result_list
    try:
        x = s.get('https://wf.my.com/minigames/marketplace/api/all')
        mp_list.update({user_id: {'search': x.json(), 'result_list': [], 'date': datetime.now()}})
    except Exception as e:
        print("error when retrieve from browser", e)
    finally:
        getList = mp_list.get(user_id).get('search')
        if types is None:
            allofthings = [[i, val] for i, val in enumerate(getList['data'])]
        else:
            allofthings = [[i, val] for i, val in enumerate(getList['data']) if str(types).lower() in val['kind']]
        result = {}
        print(name)
        for i, val in allofthings:
            if str(name).lower() in str(val['title']).lower():
                temp = result.get(val['title'], None)

                if types == 'weapon':
                    result.update({val['title']: [val['title'], val['min_cost'], val]})
                elif temp is None or temp[1] > val['min_cost']:
                    result.update({val['title']: [val['title'], val['min_cost'], val]})
        result_list = []
        for i in result.keys():
            result_list.append(result.get(i))
        result = result_list
        mp_list.get(user_id).update({'result_list': result})
        if len(result) > 0:
            result = ["\n{0: <10}{1} = {2:.2f} credits".format(i + 1, val[0], val[1] * 1.05) for i, val in
                      enumerate(result)]
            return check_2000LIMIT(result)
        return "Could not find anything you search. Item is not in the market yet"


@client.event
async def on_message(message):
    if message.content.startswith('!search'):
        update_server_info(message)
        user = normalize_name(message.author)
        print(f'Request for a search from {user} in channel {message.channel.id}')
        content_ = str(message.content).split(" ")[1:]
        content_ = " ".join(content_)
        result = search_all(content_, user_id=message.author.id)
        result = header_footer(result)
        if type(result) == list:
            for i in result:
                await send_to_user(message.author.id, message.channel.id, "```\n%s```" % i)
        else:
            await send_to_user(message.author.id, message.channel.id, "```\n%s```" % result)
    elif message.content.split(" ")[0] in ['!weapon', '!appearance', '!equipment', '!other', '!camouflage',
                                           '!achievement']:
        update_server_info(message)
        user = normalize_name(message.author)
        content_ = str(message.content).split(" ")[1:]
        content_ = " ".join(content_)
        head = message.content.split(" ")[0][1:]
        result = search_all(content_, head, user_id=message.author.id)
        result = header_footer(result, head)
        if type(result) == list:
            for i in result:
                await send_to_user(message.author.id, message.channel.id, "```\n%s```" % i)
        else:
            await send_to_user(message.author.id, message.channel.id, "```\n%s```" % result)


    elif message.content.startswith('!track'):
        update_server_info(message)
        user = normalize_name(message.author)
        print(f'Request for a track from {user} in channel {message.channel.id}')
        if check_role(message.author.id):
            print('Approved')
        else:
            print('Denied')
            await send_to_user(message.author.id, message.channel.id, 'Access denied, unauthorized user.')
            return
        index_price = str(message.content).index('--price=')
        if index_price < 0:
            await send_to_user(message.author.id, message.channel.id,
                               'Please input the expected price like:\n!track ACR --price=200')
            return
        create_new_search(user, message.author.id, track=True)
        index_price += 8
        update_record(user, 'matching', 'title')
        price = int(message.content[index_price:])
        update_record(user, 'budget', price)
        title = message.content[6:index_price - 8].strip()
        update_record(user, 'match_value', title)

        await send_to_user(message.author.id, message.channel.id,
                           'Confirmed. How do you want to be notified? (!DM/!Report)')

    elif message.content.lower().startswith('!dm') or message.content.lower().startswith('!DM'):
        user = normalize_name(message.author)
        if check_active_session(user):
            if DM_ALLOWED:
                update_record(user, 'tracking_notif_type', 'DM')
                update_record(user, 'track', True)
                await send_to_user(message.author.id, message.channel.id, 'Confirmed.')
            else:
                await send_to_user(message.author.id, message.channel.id,
                                   'DM option has been disabled by the admin. Please use !report.')

    elif message.content.lower().startswith('!report') or message.content.lower().startswith('!REPORT'):
        user = normalize_name(message.author)
        print('report')
        if check_active_session(user):
            update_record(user, 'tracking_notif_type', 'Reports')
            update_record(user, 'track', True)
            await send_to_user(message.author.id, message.channel.id, 'Confirmed.')

    elif message.content.lower().startswith('!help'):
        await send_to_user(message.author.id, message.channel.id, '```\n'
                                                                  '1. !search name-item\n'
                                                                  'Search for items\n'
                                                                  '2. !weapon name-weapon\n'
                                                                  'Search for weapon\n'
                                                                  '3. !appearance\n'
                                                                  'Search for appearance\n'
                                                                  '4. !equipment\n'
                                                                  'Search for equipment\n'
                                                                  '5. !camouflage\n'
                                                                  'Search for camouflage\n'
                                                                  '6. !achievement\n'
                                                                  'Search for achievement\n'
                                                                  '7. !track name --price=VALUE\n'
                                                                  'Track an item with spesific name and expected price value\n'
                                                                  '8. !dm\n'
                                                                  'Inform the user about tracking result through DM\n'
                                                                  '9. !report\n'
                                                                  'Inform the user about tracking result through report\n'
                                                                  '```')


    elif message.content.lower().startswith('!'):  # If we get here, they're either entering a budget or item id
        value = message.content.strip('!')
        user_id = message.author.id

        if str(value).isdigit() and mp_list.get(user_id, None) is not None:
            update_server_info(message)
            user = normalize_name(message.author)
            print(f'Request for a index from {user} in channel {message.channel.id}')
            result_list = mp_list.get(user_id, None)
            if result_list is None:
                await send_to_user(message.author.id, message.channel.id, "Search an item first!")
                return
            elif math.fabs((result_list.get('date') - datetime.now()).total_seconds()) > 20:
                await send_to_user(message.author.id, message.channel.id, "Item detail timeout.")
                mp_list.pop(user_id, None)
                return
            else:
                indexs = value
                if len(indexs) == 0 and not indexs.isdigit():
                    await send_to_user(message.author.id, message.channel.id, "index is not a number")
                    return
                elif indexs.isdigit() and int(indexs) - 1 >= len(result_list.get('result_list')):
                    await send_to_user(message.author.id, message.channel.id, "index is overlap")
                    return
                indexs = int(indexs) - 1

                val = result_list.get('result_list')[indexs][-1]
                embed = discord.Embed(title='Item detail')
                embed.set_image(
                    url="https://wf.cdn.gmru.net/static/wf.mail.ru/img/main/items/{}.png".format(val['item']['id']))

                result = f"```\ntitle : {val['title']}\nitem_id : {val['item']['id']}\n```"
                # embed.add_field(name='Message', value=result)
                channel = client.get_channel(message.channel.id)
                await channel.send(f"<@{message.author.id}> {result}", embed=embed)
        else:
            await send_to_user(message.author.id, message.channel.id, f'Command not found: {value}')


def check_role(user_id):
    user = (int(user_id))
    if user == 458640561667047434:  ## Reyzeal id, for development purpose only
        return True
    user = client.get_user(int(user_id))

    con, cur = get_db_con()
    cur.execute(f'SELECT * FROM server_info')
    guild_id = cur.fetchall()[0][0]
    guild = client.get_guild(int(guild_id))
    if guild is None:
        return False
    for role in guild.roles:
        print(role.name)
        if role.name.lower() == ROLE_ALLOWED_TO_TRACK.lower():
            print('Found correct role')
            print(role.members)
            if user in role.members:
                print('User has the needed role to track')
                return True

    return False


def check_tracking(user):
    con, cur = get_db_con()
    cur.execute(f'SELECT * FROM sessions WHERE user="{user}"')
    record = cur.fetchall()[0]
    print(type(record[1]))
    if record[1] == 0:
        return False
    if record[1] == 1:
        return True


def delete_record(user):
    con, cur = get_db_con()
    cur.execute(f'DELETE FROM sessions WHERE user="{user}"')
    con.commit()
    con.close()


# Background task is to denote whether this is a background check
# If it is, we don't want to return that it's not found again
async def search_mygames(user, background_task=False):
    # Gets details of the requested search from the database
    con, cur = get_db_con()
    cur.execute(f'SELECT * FROM sessions WHERE user="{user}";')
    record = cur.fetchall()[0]
    matching = record[2]
    item = record[3]
    budget = record[4]
    # This should only be possible if someone calls !recheck before setting matching, id, budget, etc
    if record is None or matching is None or budget is None:
        if background_task is False:
            return f'Not all search criteria have been defined'
        if background_task is True:
            return None
    print(f'Searching mygames for {item} in budget {budget}')

    try:
        x = s.get('https://wf.my.com/minigames/marketplace/api/all')
        mp_lists = x.json()
        for x in mp_lists['data']:
            if item.lower() in x[matching].lower() and x['min_cost'] * 1.05 <= int(budget):
                price = x['min_cost']
                eid = x['entity_id']
                item_type = x['type']
                data_to_buy = {
                    'entity_id': eid,
                    'cost': price,
                    'type': item_type
                }
                return f'Item {item} is now being offered for ' + str(x['min_cost'] * 1.05) + ' Kredits.'
            elif x[matching].lower() == item.lower() and x['min_cost'] * 1.05 > int(budget):
                if background_task is False:
                    return f'The price for {item} is ' + str(int(x['min_cost'] * 1.05)) + ' Kredits.'
                if background_task is True:
                    return None
        # If we make it here, the item didn't exist
        if background_task is False:
            return f'{item} was not found on the marketplace'
        if background_task is True:
            return None
    except (KeyError, ValueError, TypeError, requests.exceptions.ChunkedEncodingError, json.decoder.JSONDecodeError,
            requests.exceptions.ConnectionError):
        print('error')
        return None
        # mygames_login()


####################RELOGIN FUNCTION###########################
@tasks.loop(minutes=10)
async def periodic_login():
    global launched
    print("relogin")
    if launched == 0:
        launched+=1
        return
    mygames_login()

@tasks.loop(seconds=15)
async def periodic_check():
    print('Checking periodicially')
    con, cur = get_db_con()
    cur.execute('SELECT * FROM sessions;')
    records = cur.fetchall()
    con.close()

    for record in records:
        if record[1] == 'True':  # Only tracked entries should be checked periodically
            print(f'Background task searching for user {record[0]}')
            response = await search_mygames(record[0], background_task=True)

            if response != '' and response is not None:
                if record[6].lower() == 'dm':
                    print('Messaging user by dm')
                    await dm_user(record[5], response)
                    update_record(record[0], 'track', False)
                elif record[6].lower() == 'reports':
                    print('Messaging user by reports')
                    await send_to_reports(record[5], response)
                    update_record(record[0], 'track', False)


async def send_to_reports(user_id, response):
    print('Sending to reports')
    con, cur = get_db_con()
    cur.execute(f'SELECT * FROM server_info')
    reports_channel_id = cur.fetchall()[0][1]
    print(f'Retrieved reports channel id is {reports_channel_id}')
    # First we get the reports channel
    reports_channel = client.get_channel(644620899055829031)  # Was int(reports_channel_id)
    await reports_channel.send(f'<@{user_id}> {response}')


def stop():
    task.cancel()


def check_for_match_value(user):
    con, cur = get_db_con()
    cur.execute(f'SELECT * FROM sessions WHERE user="{user}";')
    all_records = cur.fetchall()
    if all_records[0][3] is None:
        return False
    else:
        return True


# Updates the passed in record in the database with the value that is also passed in
def update_record(user, column, value):
    con, cur = get_db_con()
    cur.execute(f'UPDATE sessions SET {column}="{value}" where user="{user}";')
    con.commit()
    con.close()


# Checks the database for an active open session for a particular passed in user
def check_active_session(user):
    con, cur = get_db_con()
    cur.execute(f'SELECT * from sessions where user="{user}";')
    all_records = cur.fetchall()
    if len(all_records) == 1:
        return True
    else:
        return False


async def dm_user(user_id, message):
    print(f'User id is 0{user_id}')
    user = client.get_user(int(user_id))
    print(user)
    await user.send(message)


# Sends simple message mentioning a user
async def send_to_user(user, channel_id, message):
    channel = client.get_channel(channel_id)
    await channel.send(f'<@{user}> {message}')


def create_new_search(user, user_id, track=False):
    con, cur = get_db_con()

    # Attempts to delete any currently active session in the db from this user. Does not error if none are found
    cur.execute('DELETE FROM sessions WHERE user=(?);', (user,))
    # Then recreates it
    cur.execute("INSERT INTO sessions VALUES(?, ?, ?, ?, ?, ?, ?);", (user, track, None, None, None, user_id, None))
    con.commit()
    con.close()


# Checks for the existence of the database
# Creates it with the correct structure if not
def check_db():
    if not os.path.isfile('sessions.db'):
        create_command = '''
        CREATE TABLE sessions ( 
        user VARCHAR(40) PRIMARY KEY,
        track BOOLEAN,
        matching VARCHAR(30),
        match_value VARCHAR(40),
        budget INTEGER,
        user_id VARCHAR(40),
        tracking_notif_type VARCHAR(10)
        )
        '''

        con, cur = get_db_con()
        cur.execute(create_command)

        create_command = '''
        CREATE TABLE server_info (
        guild_id VARCHAR(40) PRIMARY KEY,
        reports_channel_id VARCHAR(40)
        )
        '''

        cur.execute(create_command)
        con.commit()
        con.close()


# Returns a database connection object and cursor object for sessions.db
def get_db_con():
    con = sqlite3.connect('sessions.db')
    cur = con.cursor()

    return con, cur


# Takes off everything after the # in the name for simplicity and database sanitization
def normalize_name(author):
    user = str(author)
    user = user[:user.find('#')]
    return user


@client.event
async def on_ready():
    print(f'Discord bot logged in as {client.user.name} and awaiting commands')
    print(f'Using discord version {discord.__version__}')
    periodic_check.start()
    periodic_login.start()
    print('-----------------')


# Code written beforehand
def mygames_login():
    print('loading')
    driver.get('https://account.my.games/login')
    try:
        print('try to login')
        element = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".ph-form__input")))
        element = driver.find_element_by_css_selector('.ph-form__input[name=email]')
        element.send_keys(email)
        element = driver.find_element_by_css_selector('.ph-form__input[name=password]')
        element.send_keys(password)
        element = driver.find_element_by_css_selector('[type=submit]')
        element.click()
        print('login submitted')
        element = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".ph-form__input")))
        driver.get(
            'https://account.my.games/oauth2/?redirect_uri=https%3A%2F%2Fpc.warface.com%2Fdynamic%2Fauth%2F%3Fo2%3D1&client_id=wf.my.com&response_type=code&signup_method=email,phone&signup_social=mailru%2Cfb%2Cvk%2Cg%2Cok%2Ctwitch%2Ctw%2Cps%2Cxbox%2Csteam&lang=en_US')
        print('logged in')
        driver.get('https://pc.warface.com/minigames/user/info')
        print('getting token')
    finally:
        get_token = to_json()
        for i in driver.get_cookies():
            s.cookies.set(i['name'], i['value'], domain=i['domain'], path=i['path'])
        print('done', get_token['data']['token'])


def get_mg_token():
    driver.get('https://pc.warface.com/minigames/user/info')
    get_token = to_json()
    s.cookies['mg_token'] = get_token['data']['token']


# Class for color and text customization
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def signal_handler(signal, frame):
    print('\n' + bcolors.WARNING + "Crate Manager was interrupted!" + bcolors.ENDC)
    sys.exit(0)


def res_count():
    driver.get("https://wf.my.com/minigames/craft/api/user-info")
    main_json = to_json()
    level1 = main_json['data']['user_resources'][0]['amount']
    level2 = main_json['data']['user_resources'][1]['amount']
    level3 = main_json['data']['user_resources'][2]['amount']
    level4 = main_json['data']['user_resources'][3]['amount']
    level5 = main_json['data']['user_resources'][4]['amount']
    output = "\033[92m\nCurrent resources\033[0m \nLevel 1: %d | Level 2: %d | Level 3: %d | Level 4: %d | Level 5: %d \n" % (
        level1, level2, level3, level4, level5)
    return output


print(bcolors.OKGREEN + bcolors.HEADER + "\nMarketplace Monitor" + bcolors.ENDC)

# LOGIN AND CHECK USER
mygames_login()
driver.get('https://wf.my.com/minigames/bp/user-info')
user_check_json = to_json()
try:
    print("Mygames logged in as {}".format(user_check_json['data']['username']))
except KeyError:
    print("Login failed.")
    sys.exit(0)

if __name__ == '__main__':
    # mygames_login()
    check_db()
    client.run(BOT_TOKEN)
    print('OUTSPOKEN')
    # The rest is to handle the periodic checking
    loop = asyncio.get_event_loop()
    loop.call_later(5, stop)
    task = loop.create_task(periodic_check())

    try:
        loop.run_until_complete(task)
    except asyncio.CancelledError:
        pass
