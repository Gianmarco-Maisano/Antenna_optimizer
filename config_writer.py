import configparser
import os

BASE_DIR = os.path.dirname((os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, 'config.ini')
print(CONFIG_PATH)

def update_config(section, key, value):
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    config.set(section, key, str(value))
    with open(CONFIG_PATH, 'w') as configfile:
        config.write(configfile)
