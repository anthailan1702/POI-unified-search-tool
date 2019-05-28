from flask import Flask, jsonify
from marshmallow import Schema, fields
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

from config import Config
from app.decorators import parse_args_with

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)
db = SQLAlchemy(app)
migrate = Migrate(app, db)

from app.models import *
from app.api_dispatcher import APIDispatcher
from app import parameter_parser
from app.data_aggregator import DataAggregator
from app.data_preprocessor import DataPreprocessor
from app.cache import Cache
from app.cache_result_filter import CacheResultFilter


class FindPlaceSchema(Schema):
    location = fields.String(required=True)
    keyword = fields.String(missing=None)
    radius = fields.Integer(missing=None)
    categories = fields.String(missing=None)


@app.route('/places/explore')
@parse_args_with(FindPlaceSchema)
def explore_places(args):
    arguments = parameter_parser.parse_parameters(raw_params=args)
    cache_results = Cache.get_from_location(args['location'])
    if cache_results is None:
        responses = APIDispatcher(args=arguments).dispatch_api_calls()
        preprocessed_data = DataPreprocessor(data=responses).process_data()
        results = DataAggregator(data=preprocessed_data).aggregate_data()
        Cache.set_cache_with_location(args['location'], results)
    else:
        results, remaining_categories = CacheResultFilter.filter_cache_results(args, cache_results)
        if len(remaining_categories) > 0:
            args['categories'] = ','.join(remaining_categories)
            arguments = parameter_parser.parse_parameters(raw_params=args)
            responses = APIDispatcher(args=arguments).dispatch_api_calls()
            preprocessed_data = DataPreprocessor(data=responses).process_data()
            results.extend(DataAggregator(data=preprocessed_data).aggregate_data())
            Cache.set_cache_with_location(args['location'], results)

    returned_results = []
    for item in results:
        if len(item.keys()) == 1:
            returned_results.append(item)

    return jsonify(returned_results)
