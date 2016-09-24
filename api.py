#!/usr/bin/env python3

from datetime import datetime
import json
import logging

from flask import Flask, request, abort

import engine


logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.config['DEBUG'] = True


@app.route('/')
def index():
    return 'It works'


@app.route('/search')
def search():
    src = request.args.get('src')
    dst = request.args.get('dst')
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    if src and dst and date:
        return json.dumps(engine.get_routes(src, dst, date))

    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    if date_from and date_to:
        return json.dumps(engine.get_routes_between(date_from, date_to))

    abort(400)


if __name__ == '__main__':
    app.run(threaded=True)
