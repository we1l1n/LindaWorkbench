from datetime import datetime
import json
from numbers import Number
import urllib
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.test._doctest import _OutputRedirectingPdb
from django.utils.http import urlquote
import requests
from linda_app.models import DatasourceDescription, VocabularyProperty, Query, get_configuration

from linda_app.settings import LINDA_HOME


def designer_defaults():
    params = {
        'datasources': list(DatasourceDescription.objects.all()),
        'RDF2ANY_SERVER': get_configuration().rdf2any_server
    }

    params['datasources'].insert(0,
                                 DatasourceDescription(title="All private data dources", name="all", is_public=False
                                                       , uri=LINDA_HOME + "sparql/all/", createdOn=datetime.today(),
                                                       updatedOn=datetime.today()))

    return params


# Home page
def index(request):
    params = designer_defaults()

    return render(request, "builder_advanced/index.html", params)


# Load an existing design
def load_design(request, pk):
    params = designer_defaults()
    params['query'] = Query.objects.get(pk=pk)

    if not params['query']:
        raise Http404

    return render(request, "builder_advanced/index.html", params)


# API calls


# get endpoint by data source name
def get_endpoint_from_dt_name(dt_name):
    if dt_name != "all":  # search in all private data source
        datasources = DatasourceDescription.objects.filter(name=dt_name)

        if not datasources:  # data source not found by name
            raise Http404

        return datasources[0].get_endpoint()
    else:
        return get_configuration().private_sparql_endpoint


# Execute a SparQL query on an endpoint and return json response
def sparql_query_json(endpoint, query):
    # encode the query
    query_enc = urlquote(query, safe='')

    # get query results and turn them into json
    # with &output=json we support non-standard endpoints like IMDB & World Factbook
    response = requests.get(
        endpoint + "?Accept=" + urlquote(
            "application/sparql-results+json") + "&query=" + query_enc + "&format=json&output=json")

    if response.status_code == 200:
        # return the response
        return HttpResponse(response.text, "application/json")
    else:
        return HttpResponse(response.text, status=response.status_code)


# Get active classes in a data source
def active_classes(request, dt_name):
    # get the endpoint of the query
    endpoint = get_endpoint_from_dt_name(dt_name)

    # editor classes
    if request.GET.get('q'):
        q = request.GET.get('q')
        if request.GET.get('prefix'):
            regex = request.GET.get('prefix') + '(.)*' + q + '(.)*'
        else:
            regex = '^http://(/)*(.)*' + q + '(.)*'

        query = 'select distinct ?Concept where {[] a ?Concept. FILTER regex(str(?Concept), "' + regex + '" , "i")} LIMIT 20'
    else:
        # get page
        p = request.GET.get('p', '0')

        # query to get all classes with at least one instance
        classes_query_paginate_by = 10000
        query = "SELECT DISTINCT ?class WHERE { ?s a ?class } LIMIT " + str(classes_query_paginate_by) + " OFFSET " + str(
            (int(p) - 1) * classes_query_paginate_by)

    return sparql_query_json(endpoint, query)


# Get active classes in a data source
def active_root_classes(request, dt_name):
    # get the endpoint of the query
    endpoint = get_endpoint_from_dt_name(dt_name)

    # query to get all classes with at least one instance
    query = "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nSELECT DISTINCT ?class ((count(?x)) AS ?cnt) WHERE {?x a ?class. FILTER NOT EXISTS {?class rdfs:subClassOf ?parentClass.} } GROUP BY ?class ORDER BY DESC (?cnt)"

    return sparql_query_json(endpoint, query)


# Get active subclasses in a data source
def active_subclasses(request, dt_name):
    # get parent class
    if not request.GET.get('parent_class'):
        raise Http404

    parent_class = urllib.unquote(request.GET.get('parent_class'))

    # get the endpoint of the query
    endpoint = get_endpoint_from_dt_name(dt_name)

    # query to get all classes with at least one instance
    query = "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nSELECT DISTINCT ?class (count(?x) AS ?cnt) WHERE {?x a ?class. ?class rdfs:subClassOf <" + parent_class + ">. } GROUP BY ?class ORDER BY DESC (?cnt)"

    return sparql_query_json(endpoint, query)


# Get active object properties in a data source
def object_properties(request, dt_name):
    # get the endpoint of the query
    endpoint = get_endpoint_from_dt_name(dt_name)

    # query to get all classes with at least one instance
    query = "PREFIX owl: <http://www.w3.org/2002/07/owl#>\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nSELECT DISTINCT ?property ?domain ?range WHERE {?property a owl:ObjectProperty. ?property rdfs:domain ?domain. ?property rdfs:range ?range}"

    return sparql_query_json(endpoint, query)


# Get all properties of class instances in a data source
def active_class_properties(request, dt_name):
    # get class searched
    if not request.GET.get('class_uri'):
        raise Http404

    class_uri = urllib.unquote(request.GET.get('class_uri'))

    # get the endpoint of the query
    endpoint = get_endpoint_from_dt_name(dt_name)

    # get if pagination was set
    if request.GET.get('page'):
        p = int(request.GET['page'])
        offset = (p - 1) * 200
        page_str = " OFFSET " + str(offset) + " LIMIT 200"
    else:
        page_str = ""

    # query to get all properties of a class with at least one instance
    if request.GET.get('order'):
        query = "SELECT DISTINCT ?property (count(?x) AS ?cnt) WHERE {?x a <" + class_uri + ">. ?x ?property ?o } GROUP BY ?property ORDER BY DESC(?cnt)" + page_str
    else:
        query = "SELECT DISTINCT ?property WHERE {?x a <" + class_uri + ">. ?x ?property ?o }" + page_str

    return sparql_query_json(endpoint, query)


# Get all properties in a data source
def active_properties(request, dt_name):
    # get the query string
    q = request.GET.get('q', '')

    # get the endpoint of the query
    endpoint = get_endpoint_from_dt_name(dt_name)

    if request.GET.get('prefix'):
        regex = request.GET.get('prefix') + '(.)*' + q + '(.)*'
    else:
        regex = '^http://(/)*(.)*' + q + '(.)*'

    query = 'SELECT DISTINCT ?property WHERE {?x ?property ?o FILTER regex(str(?property), "' + regex + '" , "i")} LIMIT 20'

    return sparql_query_json(endpoint, query)


# Get the return type of a property
def get_property_type(request, dt_name):
    # get property uri
    if not request.GET.get('property_uri'):
        raise Http404

    property_uri = urllib.unquote(request.GET.get('property_uri'))

    # find type and create json response
    props = VocabularyProperty.objects.filter(uri=property_uri)

    if not props:  # could not detect the property in the vocabulary repository
        tp = ""
    else:  # get the return type (range)
        tp = props[0].range_uri()

    data = json.dumps({'type': tp})

    # return the response
    return HttpResponse(data, "application/json")