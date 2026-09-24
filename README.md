sudo cp -r discord-bot-pro /opt/discord-bot
cd /opt/discord-bot
sudo python3 -m venv .venv
sudo .venv/bin/pip install -r requirements.txt
sudo cp .env.example .env && sudo nano .env
sudo useradd -r -s /bin/false discord
sudo chown -R discord:discord /opt/discord-bot
sudo touch /var/log/discord-bot.log
sudo chown discord:discord /var/log/discord-bot.log
sudo cp discord-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now discord-bot
sudo systemctl status discord-bot