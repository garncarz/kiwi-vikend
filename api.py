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
    result = None

    src = request.args.get('src')
    dst = request.args.get('dst')
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    if src and dst and date:
        result = engine.get_routes(src, dst, date)

    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    if date_from and date_to:
        result = engine.get_routes_between(date_from, date_to)

    price = request.args.get('price')
    if price:
        result = filter(lambda route: route['price'] <= price,
                        filter(lambda route: 'price' in route, result))

    seats = request.args.get('seats')
    if seats:
        result = filter(lambda route: route['seats'] >= seats,
                        filter(lambda route: 'seats' in route, result))

    sort = request.args.get('sort')
    if sort in ['price', 'departure']:
        result = sorted(result, key=lambda route: route[sort])
    elif sort == 'alphabetical':
        result = sorted(result, key=lambda route: (route['from_name'],
                                                   route['to_name']))
    else:
        abort(400)

    result = list(result)

    if 'min_price' in request.args:
        result = min(filter(lambda route: 'price' in route, result),
                     key=lambda route: route['price'])

    if result is not None:
        return json.dumps(result)
    else:
        abort(400)


if __name__ == '__main__':
    app.run(threaded=True)
