# pylint: disable=locally-disabled, multiple-statements, line-too-long, missing-module-docstring, missing-function-docstring, missing-class-docstring, invalid-name, pointless-string-statement, broad-except
import json
import traceback

import random
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import base64

from google.cloud import storage
from pywebpush import webpush, WebPushException

from syftsession import SyftSession
from autoflex_secrets import BUCKET_NAME, SUBSCRIPTIONS_FILE_NAME, SESSION_FILE_NAME, vapidKeys, VAPID_MAILTO

# Filtering parameters
MAX_OUTBOUND    = 2
MAX_RETURN      = 2
MAX_DAYSFROMNOW = 12


# API keys and clients
storage_client = storage.Client()


def pushToAllSubscribers(data: dict):
    subscriptionsBlob = storage_client.bucket(BUCKET_NAME).blob(SUBSCRIPTIONS_FILE_NAME)

    if subscriptionsBlob.exists():
        subscriptions = json.loads(subscriptionsBlob.download_as_bytes())
        for subscription in subscriptions:
            try:
                response = webpush(
                    subscription_info   =   subscription,
                    data                =   json.dumps(data),
                    vapid_private_key   =   vapidKeys["privateKey"],
                    vapid_claims        =   {"sub": VAPID_MAILTO})
                print(subscription["endpoint"][-5:]," Web Push service response: ", response)

            except WebPushException as e:
                subscriptions.remove(subscription)
                subscriptionsBlob.upload_from_string(json.dumps(subscriptions), content_type="application/json")
                print(subscription["endpoint"][-5:]," Push failed; Subscription removed.", e)
    else:
        print("No subscriptions")


def periodicQuery(event, context):
    """
    Triggered from any message on the 'autoflex-trigger' Cloud Pub/Sub topic.
    """
    global SESSION_FILE_NAME
    DEBUG = False
    calling_parameter = ''

    if 'data' in event:
        calling_parameter = base64.b64decode(event['data']).decode('utf-8')
        if "DEBUG" in calling_parameter:
            DEBUG = True

    if "DEBUGFILE" in calling_parameter:
        SESSION_FILE_NAME = "debug.json"

    if "NOFUZZ" not in calling_parameter:
        # Fuzzing; only do if not debug
        if random.randint(0,2) != 0:
            return
        time.sleep(random.randint(0,30))        

    try:
        # Load session blob into memory.
        session = SyftSession()

        session_blob = storage_client.bucket(BUCKET_NAME).blob(SESSION_FILE_NAME)
        if session_blob.exists():
            existing_session_blob_content = session_blob.download_as_bytes()
            session.loadsession(existing_session_blob_content)
            print(f"Restored session from {SESSION_FILE_NAME}")
        else:
            print(f"No {SESSION_FILE_NAME} found. Creating new session.")
            session.login()

        # Query the syft api for offered jobs.
        session.get_offered()

        # Handle a 401 response if possible, or raise an exception if not.
        if session.offered_response.status_code == 401:
            print("Getting jobs returned 401; attempting to refresh token")
            session.refresh()
            if session.refresh_response.ok:
                session.get_offered()
                session.offered_response.raise_for_status()
            elif session.refresh_response.status_code == 401:
                print("Refresh returned 401; attempting to relogin") # TODO notify
                session.login()
                session.get_offered()
            else:
                session.refresh_response.raise_for_status()  # TODO toplevel exception catach > notify
        else:
            session.offered_response.raise_for_status()

        # Parse and filter the list of shifts. If new workable shifts are
        # available, send a push message with their details.
        session.remove_expired_shifts()
        new_workable_shifts = session.parse_offered(MAX_OUTBOUND,MAX_RETURN, MAX_DAYSFROMNOW)
        if new_workable_shifts:
            pushToAllSubscribers({
                "ok"    : True,
                "title" : "New workable shifts",
                "time"  : datetime.now(ZoneInfo("Europe/London")).isoformat(),
                "shifts": new_workable_shifts,
            })

        # Save the session.
        if session.savesession().encode() == existing_session_blob_content:
            print(f"No changes made to {SESSION_FILE_NAME}.")
        else:
            session_blob.upload_from_string(session.savesession(), content_type="application/json")
            print(f"Saved session to {SESSION_FILE_NAME}")

    # If an uncaught exception occurs, send a push message containing details of
    # the exception.
    except Exception:
        if DEBUG:
            raise
        else:
            pushToAllSubscribers({
                "ok"    : False,
                "title" : "autoflex: uncaught exception",
                "time"  : datetime.now(ZoneInfo("Europe/London")).isoformat(),
                "error" : traceback.format_exc(),
            })
