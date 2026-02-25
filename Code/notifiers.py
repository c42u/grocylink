import smtplib
import json
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


class BaseNotifier:
    def __init__(self, config):
        self.config = config if isinstance(config, dict) else json.loads(config)

    def send(self, title, message):
        raise NotImplementedError

    def test(self):
        return self.send("Grocylink - Test", "Dies ist eine Testnachricht von Grocylink.")


class EmailNotifier(BaseNotifier):
    def send(self, title, message):
        cfg = self.config
        msg = MIMEMultipart()
        msg['From'] = cfg.get('from_email', cfg['username'])
        msg['To'] = cfg['to_email']
        msg['Subject'] = title
        msg.attach(MIMEText(message, 'plain', 'utf-8'))

        server = smtplib.SMTP(cfg['smtp_host'], int(cfg.get('smtp_port', 587)))
        server.ehlo()
        if cfg.get('use_tls', True):
            server.starttls()
        if cfg.get('username') and cfg.get('password'):
            server.login(cfg['username'], cfg['password'])
        server.sendmail(msg['From'], cfg['to_email'], msg.as_string())
        server.quit()
        return True


class PushoverNotifier(BaseNotifier):
    def send(self, title, message):
        resp = requests.post('https://api.pushover.net/1/messages.json', data={
            'token': self.config['api_token'],
            'user': self.config['user_key'],
            'title': title,
            'message': message,
            'priority': int(self.config.get('priority', 0)),
        }, timeout=10)
        resp.raise_for_status()
        return True


class TelegramNotifier(BaseNotifier):
    def send(self, title, message):
        text = f"<b>{title}</b>\n\n{message}"
        resp = requests.post(
            f"https://api.telegram.org/bot{self.config['bot_token']}/sendMessage",
            json={
                'chat_id': self.config['chat_id'],
                'text': text,
                'parse_mode': 'HTML',
            },
            timeout=10
        )
        resp.raise_for_status()
        return True


class SlackNotifier(BaseNotifier):
    def send(self, title, message):
        resp = requests.post(
            self.config['webhook_url'],
            json={'text': f"*{title}*\n{message}"},
            timeout=10
        )
        resp.raise_for_status()
        return True


class DiscordNotifier(BaseNotifier):
    def send(self, title, message):
        resp = requests.post(
            self.config['webhook_url'],
            json={'content': f"**{title}**\n{message}"},
            timeout=10
        )
        resp.raise_for_status()
        return True


class GotifyNotifier(BaseNotifier):
    def send(self, title, message):
        resp = requests.post(
            f"{self.config['server_url'].rstrip('/')}/message",
            json={
                'title': title,
                'message': message,
                'priority': int(self.config.get('priority', 5)),
            },
            headers={'X-Gotify-Key': self.config['app_token']},
            timeout=10
        )
        resp.raise_for_status()
        return True


NOTIFIER_CLASSES = {
    'email': EmailNotifier,
    'pushover': PushoverNotifier,
    'telegram': TelegramNotifier,
    'slack': SlackNotifier,
    'discord': DiscordNotifier,
    'gotify': GotifyNotifier,
}


def get_notifier(channel_type, config):
    cls = NOTIFIER_CLASSES.get(channel_type)
    if not cls:
        raise ValueError(f"Unbekannter Kanal-Typ: {channel_type}")
    return cls(config)
