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

import sys
import socket
import datetime
import feedparser

host = '127.0.0.1'
port = 4201
timeout = 0.5
bot_name = ''
bot_pw = ''
channel_name = ''
news_feed = ''
login = 'connect ' + bot_name + ' ' + bot_pw + '\n'


def get_news():

    print('[+] Getting news...')
    NewsFeed = feedparser.parse(news_feed)
    return NewsFeed.entries


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


def print_news(game_socket, articles):

    print('[-] Printing the news...')
    for article in articles:
        title = replace_chars(article.title)
        link = replace_chars(article.link)

        news_ticker = '+' + channel_name + ' ;:\n'
        game_socket.sendall(news_ticker.encode())
        clear_socket(game_socket)
        news_ticker = '+' + channel_name + ' ;: "' + title + '" -->\n'
        game_socket.sendall(news_ticker.encode())
        clear_socket(game_socket)
        news_ticker = '+' + channel_name + ' ;: [' + link + ']\n'
        game_socket.sendall(news_ticker.encode())
        clear_socket(game_socket)

    news_ticker = '+' + channel_name + ' ;:\n'
    game_socket.sendall(news_ticker.encode())
    clear_socket(game_socket)


def replace_chars(string):

    string = string.replace('‘','\'')
    string = string.replace('’','\'')
    string = string.replace('“','"')
    string = string.replace('”','"')

    return string


def main():

    now = datetime.datetime.now()
    date_string = now.strftime("%B %d, %Y %H:%M:%S")
    print('[-] Starting Paperboy - ' + date_string)
    
    articles = get_news()
    game_socket = connect()
    print_news(game_socket, articles)
    print('[*] Done!')


if __name__ == '__main__':
    sys.exit(main())