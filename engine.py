from datetime import datetime, timedelta
import dateutil.parser
import json
import logging
import re
import uuid

from grab import Grab
from lxml import etree
from redis import StrictRedis
from slugify import slugify
import unidecode

import settings
from settings import REDIS_EXPIRE, REDIS_CONFIG


logger = logging.getLogger(__name__)

redis = StrictRedis(**REDIS_CONFIG)
# TODO all .get() & .set() should be encapsulated, using json.dumps/loads()

sa_date_regex = re.compile(r'.* (?P<day>\d+)\.(?P<month>\d+)\.(?P<year>\d+)')


def download_cities():
    resp = Grab().go(
        'https://www.studentagency.cz/data/wc/ybus-form/destinations-cs.json'
    )
    dest_resp = json.loads(resp.body.decode('utf-8'))
    cities = []
    for country in dest_resp['destinations']:
        cities.extend(country['cities'])
    return cities


def cache_cities():
    logger.info('Downloading cities & saving them into Redis...')
    cities = download_cities()
    with redis.pipeline() as pipe:
        for city in cities:
            pipe.set('city_id_%s' % slugify(city['name']), city['id'],
                     ex=REDIS_EXPIRE)
        pipe.execute()


def get_destination_id(name):
    key = 'city_id_%s' % slugify(name)
    _id = redis.get(key)
    if _id is None:
        cache_cities()
        _id = redis.get(key)
        if _id is None:
            raise ValueError('Unknown city: %s' % name)
    return _id.decode('utf-8')

    # legacy:
    # return next(filter(lambda d: d['name'] == name, cities))['id']


def download_routes(_from, to, departure):
    logger.info('Downloading & parsing route: %s -> %s @ %s'
                % (_from, to, departure))

    session = Grab()
    session.go('https://www.studentagency.cz')

    from_id = get_destination_id(_from)
    to_id = get_destination_id(to)
    departure_sa = departure.replace('-', '')

    url = (
        'https://jizdenky.regiojet.cz/Booking'
        '/from/%(src)s/to/%(dest)s'
        '/tarif/REGULAR'
        '/departure/%(departure)s/retdep/%(retdep)s/return/false'
        % {'src': from_id,
           'dest': to_id,
           'departure': departure_sa,
           'retdep': departure_sa,
          }
    )
    resp = session.go(url)
    resp = session.go('%s%s' %
        (url,
         '?0-1.IBehaviorListener.0-mainPanel-routesPanel',
        )
    )

    # with open('out.html', 'wb') as out:
    #     out.write(resp.body)

    tree = etree.fromstring(resp.body.decode('utf-8'),
                            parser=etree.HTMLParser())

    # parse routes:
    results = []
    for result_xml in tree.xpath('//div[contains(@class, "routeSummary")]'):
        s = lambda string: unidecode.unidecode(string).strip()
        val = lambda column: s(result_xml.xpath(
               './div[contains(@class, "%s")]/text()' % column
            )[0])

        date_str = result_xml.xpath(
            #'./preceding-sibling::h2[contains(@class, "overflow_h1")]/text()'
            './preceding-sibling::h2/text()'
        )[-1]
        date_m = sa_date_regex.match(date_str)
        day = int(date_m.group('day'))
        month = int(date_m.group('month'))
        year = int(date_m.group('year')) + 2000

        _departs = val('col_depart').split(':')
        departure = datetime(day=day, month=month, year=year,
                             hour=int(_departs[0]), minute=int(_departs[1]))
        _arrivals = val('col_arival').split(':')
        arrival = datetime(day=day, month=month, year=year,
                           hour=int(_arrivals[0]), minute=int(_arrivals[1]))
        if arrival < departure:
            arrival = arrival + timedelta(days=1)

        result = {
            'from': from_id,
            'to': to_id,
            'from_name': _from,
            'to_name': to,
            'departure': departure.strftime('%Y-%m-%d %H:%M'),
            'arrival': arrival.strftime('%Y-%m-%d %H:%M'),
            'seats': val('col_space'),
        }

        price = result_xml.xpath(
            './div['
                'contains(@class, "col_price_no_basket_image") '
                'or contains(@class, "col_price")'
            ']/span/text()'
        )
        if len(price):
            result['price'] = s(price[0]).split()[0]

        _type = result_xml.xpath(
            'div[contains(@class, "col_icon")]//img/@alt'
        )[0]
        if _type == 'Autobus':
            result['type'] = 'bus'
        elif _type == 'Vlak':
            result['type'] = 'train'
        else:
            logger.warning('Unknown type: %s' % _type)
            continue

        results.append(result)

    return results


def get_routes(_from, to, departure):
    from_id = get_destination_id(_from)
    to_id = get_destination_id(to)
    key = 'connection_%s_%s_%s' % (from_id, to_id, departure)
    routes = redis.get(key)
    if routes is None:
        routes = download_routes(_from, to, departure)
        redis.set(key, json.dumps(routes), ex=REDIS_EXPIRE)
        return routes
    return json.loads(routes.decode('utf-8'))


def get_routes_between(date_from, date_to):
    date_min = dateutil.parser.parse(date_from)
    date_max = dateutil.parser.parse(date_to) + timedelta(days=1)
    routes = []
    for conn_key in redis.scan_iter('connection_*'):
        conn_b = redis.get(conn_key)
        if conn_b:
            connections = json.loads(conn_b.decode())
            for route in connections:
                departure = dateutil.parser.parse(route['departure'])
                arrival = dateutil.parser.parse(route['arrival'])
                if date_min <= departure <= date_max \
                        or date_min <= arrival <= date_max:
                    routes.append(route)
    return routes


def add_margin(route):
    if 'price' in route:
        route['price'] = float(route['price']) \
                         * (1 + settings.dynamic['margin'])
    return route


def create_booking(conn_spec, count, user_id):
    """
    Example of conn_spec: 10202000_10202002_2016-09-25_13:30
    """
    conn_key = conn_spec[:-17]
    departure = conn_spec[-16:].replace('_', ' ')

    for conn_key in redis.scan_iter('connection_%s_*' % conn_key):
        conn_b = redis.get(conn_key)
        if conn_b:
            connections = json.loads(conn_b.decode())
            route = next(filter(lambda route: route['departure'] == departure,
                                connections))
            if route and 'price' in route:
                _id = str(uuid.uuid4())
                price = add_margin(route)['price'] * count
                redis.set('booking_%s' % _id, json.dumps({
                    'status': 'success',
                    'user_id': user_id,
                    'price': price,
                }))

                return {
                    'id': _id,
                    'status': 'success',
                    'price': price,
                }

    return {'status': 'failed'}


def list_bookings(user_id=None):
    bookings = []
    for book_key in redis.scan_iter('booking_*'):
        book_b = redis.get(book_key)
        if book_b:
            _id = book_key[8:].decode()
            booking = json.loads(book_b.decode())
            if not user_id or booking['user_id'] == user_id:
                bookings.append({
                    'id': _id,
                    'status': booking['status'],
                    'price': booking['price'],
                })
    return bookings
