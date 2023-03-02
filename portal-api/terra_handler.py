#!/usr/bin/env python3

""" terra_handler.py - Functions that aid in creating the JSON structure needed to send data to the Terra platform."""

import json
import uuid
import requests
import sys

from collections import defaultdict
from flask import make_response
from conf import neo4j_ip, neo4j_bolt, neo4j_un, neo4j_pw
from config_utils import load_config

from query import get_manifest_data, get_metadata, extract_manifest_urls, get_all_property_keys_for_node_type
from lib.neo4j_connector import Neo4jConnector
from manifest_handler import ManifestHandler

# Code -> https://github.com/BICCN/terra-import-builder
TERRA_FXN_URL = 'https://us-central1-broad-nemo-handoff-prod.cloudfunctions.net/build-terra-import'

def create_file_entity(file_data):
    """Create JSON-based file entity structure to push into overall JSON structure."""
    file_entity = {
        "attributes": {},
        "entityType": "file",
    }
    for attr in file_data:
        if attr == "file_name":
            # File Name needs its periods replaced for JSON schema to validate
            valid_value = file_data[attr].replace('.', '-')
            file_entity["name"] = valid_value
            continue

        if attr == "urls":
            urls = file_data[attr].split(",")   # Should be HTTPS url, and potentially a GCP one as well

            # Take 1st url in list, but if GCP url exists, take that instead
            file_data[attr] = urls[0]
            for url in urls:
                if "gs:" in url:
                    file_data[attr]
                    continue
        
        if attr == 'size':
            file_data[attr] = str(file_data[attr])

        file_entity["attributes"][attr] = file_data[attr]
    return file_entity

def create_sample_entity(sample_data):
    """Create JSON-based sample entity structure to push into overall JSON structure."""
    sample_entity = {
        "attributes": {},
        "entityType": "sample",
    }
    for attr in sample_data:
        if attr == "sample_id":
            # Sample entity needs a top-level 'name'. Add it here.
            sample_entity["name"] = sample_data[attr]
            continue
        
        sample_entity["attributes"][attr] = sample_data[attr]
    return sample_entity

def determine_component_files(filetype):
    """Determine component file names, given file type provided."""
    if filetype == "FASTQ":
        return ["r1_fastq", "r2_fastq", "r3_fastq", "i1_fastq", "i2_fastq", "pacbio_fastq"]
    elif filetype == "BAM":
        return ["bam", "bam_index"]
    elif filetype == "TSV":
        return ["tsv", "tsv_index"]
    elif filetype == "H5AD":
        return ["h5ad", "h5ad_json"]
    elif filetype == "SNAP":
        return ["snap", "snap_qc"]
    elif filetype == "MEX":
        return ["mex_matrix", "mex_barcodes", "mex_genes"]
    elif filetype == "FPKM":
        return ["isoforms_fpkm", "genes_fpkm"]
    elif filetype == "TABcounts":
        return ["col_counts", "row_counts", "matrix_counts", "counts_json"]
    elif filetype == "TABanalysis":
        return ["col_analysis", "row_analysis", "dimred_analysis"]

class TerraHandler(ManifestHandler):

    """Given a file ID list, queries neo4j for file and sample data. Then converts the data into a JSON data structure that will be sent to the Terra platform."""

    def __init__(self, bundle_id=None, **kwargs):
       # initialize baseClass first
        super(TerraHandler, self).__init__(**kwargs)

        if bundle_id is None:
            bundle_id = str(uuid.uuid4())
        self.bundle_id = bundle_id

        # TerraHandler only needs a 'cart' portion of the config 
        self.config = load_config(file_name='config.json')['cart']

        # Establish connection to Neo4j
        self.neo4j_connection = Neo4jConnector(neo4j_ip, neo4j_bolt, neo4j_un, neo4j_pw)

    def build_json(self, file_data, sample_data):
        """Build JSON entity structure based on various manifest data."""
        entities = []    # Overall structure

        # Group files by file format
        files_by_type = defaultdict(list)
        for file in file_data:
            files_by_type[file['filetype']].append(file)

        # Create file-set entities for each filetype present (still work in progress)
        for filetype, files in files_by_type.items():
            for file in files:
                entities.append(create_file_entity(file))

        samp_name = []
        for sample in sample_data:
            samp_name.append(sample['sample_id'])
            # Add counter to sample name if sample_name is duplicated across non-unique sample metadata
            if samp_name.count(sample['sample_id']) > 1:
                # Sample IDs that appear multiple times will be excluded.
                # A sample can have multiple files associated with it, so instead of renaming the sample
                # as a duplicate, we are going to exclude any duplicates.

                # sample['sample_id'] = "{}-{}".format(sample['sample_id'], samp_name.count(sample['sample_id']))
                continue

            entities.append(create_sample_entity(sample))

        json_entity = {"entities":entities, "cohortName":self.bundle_id}
        #print(json_entity)
        # JSON structure is complete
        return json_entity

    def download_file(self, request, file_data):
        """Write data to downloadable file."""
        filename = self.file_name
        response = make_response(file_data)

       # If we've processed the data, reset the cookie key for the cart.
        cookie = request.form.get('downloadCookieKey')
        if cookie:
            response.set_cookie(cookie,'',expires=0)

            response.headers["Content-Disposition"] = "attachment; filename={0}_{1}.tsv".format(filename, cookie)
        else:
            response.headers["Content-Disposition"] = "attachment; filename={0}.tsv".format(filename)
        return response

    def get_terra_data(self, request):
        """Given an array of File IDs, query neo4j, and return file and sample data lists """
        if request.is_json:
            # IDs need to be in JSON
            ids = json.loads(request.data)['ids']
        else:
            ids = request.form.getlist('ids')

        #Parameterize id list
        cquery = "UNWIND $ids AS file_id MATCH (file:file{id:file_id})-[:derived_from]->(sample:sample)-[:extracted_from]-(subject:subject)"

        # Use the config to build a few things:
        # 1. Dynamically build the RETURN portion of the cypher query - we only want the information we need.
        # 2. As we add properties to the RETURN cypher, keep track of them so they can later be split into 
        #    primitive file & sample entities.
        # 3. Also track properties that lack a node-type. These properties are derived and post-query
        #    processing is required.
        return_props = [] 
        file_attributes = []
        sample_attributes = ["sample_id"] #prepopulate sample_id. Cypher breaks on duplicated result names (file and sample entity need sample_id)
        na_props = [] 
        for entity_type in self.config['export-to-terra']:
            for item in self.config['export-to-terra'][entity_type]['attributes']:
                attr = item['attribute']
                node_type = item['node-type']
                prop = item['prop']

                if entity_type == 'file' and attr not in file_attributes:
                    file_attributes.append(attr)
                
                if entity_type == 'sample' and attr not in sample_attributes:
                    sample_attributes.append(attr)
            
                if node_type == '' or node_type == 'null':
                    # Column is not stored in neo4j. 
                    # This will be populated later (ie. urls)
                    na_props.append(attr)

                    # Add 'NA' value and the property's cypher equivalent to RETURN
                    return_props.append("'NA' AS " + attr)
                else:
                    # Add property to cypher's equivalent RETURN.
                    return_props.append(node_type + "." + prop + " AS " + attr)

        # Add any missing file properties to RETURN cypher.
        # Ensures we are getting all component files. Post-query processing 
        # will filter out unnecessary component files (based on filetype)
        all_file_props = get_all_property_keys_for_node_type('file')
        for prop in all_file_props:
            if prop not in file_attributes:
                return_props.append("file." + prop + " AS " + prop)

        return_cy = " RETURN " + ", ".join(return_props)
        
        # Finish building cypher statement
        cquery = cquery + return_cy

        # Submit query to neo4j
        results = self.neo4j_connection.execute_safe_query(cquery, ids=ids)


        # Process derived properties(urls and component files) &
        # split data into raw, unfinished file entity and sample entitiy lists
        file_data = []
        sample_data = []
        for result in results:
            raw_file_entity = {}
            raw_sample_entity = {}

            # Derive urls and determine what component files make up this particular filetype
            result['urls'] = extract_manifest_urls(result)
            component_files = determine_component_files(result['filetype'])

            # Split the data into primitive file and sample entities
            # Only keep the properties we are interested in
            for attr in result:
                if attr in file_attributes or attr in component_files:
                    raw_file_entity[attr] = result[attr]
                
                if attr in sample_attributes:
                    raw_sample_entity[attr] = result[attr]
            
            file_data.append(raw_file_entity)
            sample_data.append(raw_sample_entity)

        return (file_data, sample_data)

    def handle_manifest(self, request):
        """Given IDs, return dict of file manifest information."""
        ids = ''
        if request.is_json:
            # IDs need to be in JSON
            ids = json.loads(request.data)['ids']
        else:
            ids = request.form.getlist('ids')
        return get_manifest_data(ids) # get all the relevant properties for this file

    def handle_metadata(self, request):
        """Given IDs, return dict of metadata information."""
        ids = ''
        if request.is_json:
            # IDs need to be in a list
            ids = json.dumps(json.loads(request.data)['ids'])
        else:
            filters = json.loads(request.form.get('filters')) # use json lib to parse the nested dict
            ids = json.dumps(filters['content'][0]['content']['value'])
        return get_metadata(ids)

    def post_json_to_terra(self, json_entities):
        """Send JSON payload to Terra servers via POST."""
        terra_fxn_url = TERRA_FXN_URL
        #print(json.dumps(json_entities))
        response = requests.post(terra_fxn_url, data=json.dumps(json_entities), headers={'Content-Type': 'application/json'})

        try:
            response_json = json.loads(response.text)
            #print(response_json)
            if "url" not in response_json:
                err_response = make_response(response_json["message"], 422)
                return err_response
            response_url = response_json["url"]
            return response_url
        except:
            print("Terra encountered an error: ", response.text, "status code: ", response.status_code, file=sys.stderr)
            return make_response(response.text, response.status_code)
