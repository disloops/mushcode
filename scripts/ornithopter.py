#!/usr/bin/env python

# MIT License
# Copyright (c) 2022 Matt Westfall (@disloops)

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

__author__ = 'Matt Westfall'
__version__ = '0.1'
__email__ = 'disloops@gmail.com'

# This script monitors Twitter accounts for new tweets and prints them into a
# chat channel. It runs as a systemd service locally. This is the correct way
# to install twint:
#
# pip3 install --user --upgrade git+https://github.com/twintproject/twint.git@origin/master#egg=twint

import sys
import time
import twint
import socket
from datetime import datetime
from datetime import timedelta

host = '127.0.0.1'
port = 4201
timeout = 0.5
bot_name = ''
bot_pw = ''
channel_name = ''
users = []
interval = 5
login = 'connect ' + bot_name + ' ' + bot_pw + '\n'


def get_tweets(user, since):

    c = twint.Config()
    c.Username = user
    c.Store_object = True
    c.Since = since
    c.Hide_output = True

    twint.run.Search(c)
    tweets = twint.output.tweets_list
    twint.output.clean_lists()

    return tweets


def print_tweets(game_socket, tweets):

    print('[+] Printing new tweets...')
    for tweet in tweets:
        user = replace_chars(tweet.username)
        text = replace_chars(tweet.tweet)

        twit_feed = '@cemit/noisy/noeval ' + channel_name + '=@' + user + ': ' + text + '\n'
        game_socket.sendall(twit_feed.encode())
        clear_socket(game_socket)


def connect():

    print('[+] Connecting to game...')
    game_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    game_socket.connect((host, port))
    game_socket.settimeout(timeout)
    game_socket.sendall(login.encode())
    clear_socket(game_socket)
    print('[*] Connected to ' + host + ':' + str(port) + ' as ' + bot_name + '.')
    return game_socket


def clear_socket(game_socket):

    try:
        socket_file = game_socket.makefile(mode='rb')
        while True:
            socket_file.readline()
    except socket.timeout:
        return


def replace_chars(string):

    string = string.replace('‘','\'')
    string = string.replace('’','\'')
    string = string.replace('“','"')
    string = string.replace('”','"')

    return string


def main():

    now = datetime.now()
    date_string = now.strftime("%B %d, %Y %H:%M:%S")
    print('[-] Starting Ornithopter Bot - ' + date_string)

    game_socket = connect()

    start_time = time.time()
    last_interval = (datetime.now() - timedelta(minutes=interval))
    since = last_interval.strftime("%Y-%m-%d %H:%M:%S")

    while True:
        
        for user in users:
            tweets = get_tweets(user, since)
            if tweets:
    	        print_tweets(game_socket, tweets)

        time.sleep((interval * 60) - ((time.time() - start_time) % (interval * 60)))
        last_interval = (last_interval + timedelta(minutes=interval))
        since = last_interval.strftime("%Y-%m-%d %H:%M:%S")


if __name__ == '__main__':
    sys.exit(main())