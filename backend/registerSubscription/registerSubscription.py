# pylint: disable=locally-disabled, multiple-statements, line-too-long, missing-module-docstring, missing-function-docstring, missing-class-docstring, invalid-name, pointless-string-statement, broad-except
import json

import functions_framework
from google.cloud import storage
from flask_cors import cross_origin

from autoflex_secrets import BUCKET_NAME, SUBSCRIPTIONS_FILE_NAME

@functions_framework.http
@cross_origin(allow_headers=['Content-Type'])
def registerSubscription(request):
    #print("Recieved request", request.json)
    
    # Return 400 if the request is not structured the way we expect it to be.
    if not request.json or not "endpoint" in request.json or not "keys" in request.json:
        return "Invalid request", 400

    # Initialise the gcloud storage client and get a reference to the 
    # autoflex-storage bucket, and the subscriptions.json blob inside it.
    subscriptionsBlob = storage.Client().bucket(BUCKET_NAME).blob(SUBSCRIPTIONS_FILE_NAME)

    # If susbcriptions.json doesn't exist, create a new blob called with its name
    # and write the JSON representation of a list containing the key-value pair
    # from request.json.
    if not subscriptionsBlob.exists():
        print("Creating subscriptions.json with subscription", request.json["endpoint"][-5:])
        subscriptionsBlob.upload_from_string(json.dumps([request.json]), content_type="application/json")

    # If susbcriptions.json exists, download it as a string, parse it as JSON (resulting in a list),
    # append the key-value pair from request.json to that list, dump it to a,
    # JSON string, and upload it, overwriting thr blob's contents.       
    else:
        subscriptions = json.loads(subscriptionsBlob.download_as_bytes())
        
        # Check if the subscription already exists, using the endpoint URL as a similarity key.
        # Only create a new subscription if no existing subscription has the new endpoint URL.
        if not request.json in subscriptions:
            print("Creating new subscription ", request.json["endpoint"][-5:])
            subscriptions.append(request.json)
            subscriptionsBlob.upload_from_string(json.dumps(subscriptions), content_type="application/json")
        else:
            print("Subscription ", request.json["endpoint"][-5:]," already exists")
            return 'Subscription already exists', 200

    return 'Subscription created', 201
